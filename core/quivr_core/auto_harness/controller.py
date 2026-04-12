from __future__ import annotations

import argparse
import csv
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from quivr_core.auto_harness.candidate_service import CandidateRecord, CandidateService
from quivr_core.auto_harness.contracts import (
    Decision,
    DecisionResult,
    LoopStatus,
    ReviewOutcome,
    RuntimeState,
)
from quivr_core.auto_harness.keep_integration import integrate_keep_from_worktree
from quivr_core.auto_harness.launcher import ExecutionLauncher
from quivr_core.auto_harness.keep_integration import integrate_keep_from_worktree
from quivr_core.auto_harness.observer import refresh_observer_summary
from quivr_core.auto_harness.planner import Planner
from quivr_core.auto_harness.recorder import Recorder
from quivr_core.auto_harness.reflector import reflect_round
from quivr_core.auto_harness.render_views import (
    render_plan_review_markdown,
    render_round_plan_markdown,
    render_runtime_state_markdown,
)
from quivr_core.auto_harness.reviewer import Reviewer
from quivr_core.auto_harness.run_benchmark import run_primary_benchmark
from quivr_core.auto_harness.run_quality_guard import run_quality_guard
from quivr_core.auto_harness.run_shadow_e2e import run_shadow_e2e
from quivr_core.auto_harness.state_store import StateStore
from quivr_core.auto_harness.verifier import verify_round
from quivr_core.auto_harness.vsg import evaluate_vsg
from quivr_core.auto_harness.worktree import WorktreeManager


WorkerRunner = Callable[[Any, Any, RuntimeState], dict[str, Any]]
VerifierRunner = Callable[[Any, Any], dict[str, Any]]
VsgRunner = Callable[[dict[str, Any]], dict[str, Any]]
KeepIntegrator = Callable[[Any, str, str], dict[str, Any]]


class PartialVerifierFailure(RuntimeError):
    def __init__(self, message: str, verify_payload: dict[str, Any]):
        super().__init__(message)
        self.verify_payload = verify_payload


@dataclass
class _ExecutionContext:
    runtime_state: RuntimeState
    candidate: CandidateRecord
    round_id: str


class AutoHarnessController:
    def __init__(
        self,
        repo_root: str | Path,
        docs_root: str | Path | None = None,
        planner: Planner | None = None,
        reviewer: Reviewer | Any | None = None,
        worktree_manager: WorktreeManager | Any | None = None,
        launcher: ExecutionLauncher | None = None,
        worker_runner: WorkerRunner | None = None,
        verifier_runner: VerifierRunner | None = None,
        vsg_runner: VsgRunner | None = None,
        reflector_runner: Callable[..., dict[str, Any]] | None = None,
        observer_runner: Callable[[str | Path], dict[str, Any]] | None = None,
        recorder: Recorder | None = None,
        round_id_factory: Callable[[], str] | None = None,
        keep_integrator: KeepIntegrator | None = None,
    ):
        self.repo_root = Path(repo_root)
        self.docs_root = Path(docs_root) if docs_root is not None else self.repo_root / "docs" / "auto-harness"
        self.state_store = StateStore(self.docs_root)
        self.candidate_registry_path = self.docs_root / "candidate-registry.tsv"
        self.experiment_ledger_path = self.docs_root / "experiment-ledger.tsv"
        self.reflection_log_path = self.docs_root / "reflection-log.md"
        self.planner = planner or Planner()
        self.reviewer = reviewer or Reviewer(
            candidate_registry_path=self.candidate_registry_path,
            experiment_ledger_path=self.experiment_ledger_path,
            reflection_log_path=self.reflection_log_path,
        )
        self.worktree_manager = worktree_manager or WorktreeManager(self.repo_root)
        self.launcher = launcher or ExecutionLauncher(self.repo_root, self.state_store)
        self.worker_runner = worker_runner or self._default_worker_runner
        self.verifier_runner = verifier_runner or self._default_verifier_runner
        self.vsg_runner = vsg_runner or self._default_vsg_runner
        self.reflector_runner = reflector_runner or reflect_round
        self.observer_runner = observer_runner or refresh_observer_summary
        self.recorder = recorder or Recorder(self.docs_root)
        self.round_id_factory = round_id_factory
        self.keep_integrator = keep_integrator or self._default_keep_integrator

    def run_once(self) -> dict[str, Any]:
        runtime_state = self._load_runtime_state()
        candidate = CandidateService(self.candidate_registry_path).select_candidate()
        if candidate is None:
            runtime_state = runtime_state.model_copy(
                update={
                    "loop_status": LoopStatus.CANDIDATE_POOL_EMPTY,
                    "active_round_id": None,
                    "active_execution_worktree": None,
                    "human_wait_reason": "candidate_pool_empty",
                }
            )
            self._write_runtime_state(runtime_state)
            return {"status": "candidate_pool_empty", "round_id": None}

        round_id = self._next_round_id()
        context = _ExecutionContext(
            runtime_state=runtime_state,
            candidate=candidate,
            round_id=round_id,
        )
        self._update_candidate_status(candidate.candidate_id, "active")
        runtime_state = runtime_state.model_copy(
            update={
                "loop_status": LoopStatus.PLANNING,
                "active_round_id": round_id,
                "human_wait_reason": "none",
            }
        )
        self._write_runtime_state(runtime_state)

        round_state = self.planner.plan_round(candidate, runtime_state, round_id)
        self.state_store.write_round_state(round_state)
        self._render_round_plan(round_state)

        review_result = self.reviewer.review(round_state)
        self.state_store.write_review_result(review_result)
        self._render_plan_review(review_result)

        if review_result.review_outcome == ReviewOutcome.REVISE:
            self._update_candidate_status(candidate.candidate_id, "ready")
            runtime_state = runtime_state.model_copy(
                update={
                    "loop_status": LoopStatus.PLANNING,
                    "active_round_id": None,
                    "active_execution_worktree": None,
                    "human_wait_reason": "none",
                }
            )
            self._write_runtime_state(runtime_state)
            return {"status": "review_revise", "round_id": round_id}

        if review_result.review_outcome == ReviewOutcome.REJECT:
            next_status = "exhausted" if review_result.repeat_check == "repeated_direction" else "blocked"
            self._update_candidate_status(candidate.candidate_id, next_status)
            runtime_state = runtime_state.model_copy(
                update={
                    "loop_status": LoopStatus.PLANNING,
                    "active_round_id": None,
                    "active_execution_worktree": None,
                    "human_wait_reason": "none",
                }
            )
            self._write_runtime_state(runtime_state)
            return {"status": "review_reject", "round_id": round_id}

        worktree_created = False
        expected_worktree_path = self.worktree_manager.path_for_round(round_id)
        try:
            try:
                execution_worktree = self.worktree_manager.create_round_worktree(
                    round_id=round_id,
                    current_best_commit=runtime_state.current_best_commit,
                )
            except Exception:  # noqa: BLE001
                if expected_worktree_path.exists():
                    self.worktree_manager.remove_round_worktree(round_id)
                raise
            worktree_created = True
            round_state = round_state.model_copy(update={"execution_worktree": execution_worktree})
            self.state_store.write_round_state(round_state)
            runtime_state = runtime_state.model_copy(
                update={
                    "loop_status": LoopStatus.EXECUTING,
                    "active_execution_worktree": execution_worktree,
                    "active_round_id": round_id,
                }
            )
            self._write_runtime_state(runtime_state)

            worker_launch = self.launcher.launch_worker(round_state)
            verifier_launch = self.launcher.launch_verifier(round_state)

            try:
                worker_result = self.worker_runner(round_state, worker_launch, runtime_state)
            except Exception as exc:  # noqa: BLE001
                verify_payload = self._synthetic_failure_verify_payload(round_id, benchmark_status="worker_crash")
                return self._finalize_round(
                    context=context,
                    round_state=round_state,
                    runtime_state=runtime_state,
                    verify_payload=verify_payload,
                    worker_result={
                        "change_note": {
                            "round_id": round_id,
                            "agent_id": worker_launch.manifest.agent_id,
                            "changed_files": [],
                            "summary": str(exc),
                        },
                        "end_commit": runtime_state.current_best_commit,
                    },
                    decision_name="reset",
                    notes=str(exc),
                    failure_class="worker_crash",
                    worktree_created=worktree_created,
                )

            self._write_change_note(round_id, worker_result.get("change_note", {}))
            if worker_result.get("tool_handoff"):
                self.recorder.record_tool_handoff(worker_result["tool_handoff"])

            runtime_state = runtime_state.model_copy(update={"loop_status": LoopStatus.VERIFYING})
            self._write_runtime_state(runtime_state)

            try:
                verifier_bundle = self.verifier_runner(round_state, verifier_launch)
                verify_payload = self._normalize_verify_payload(round_id, verifier_bundle)
            except PartialVerifierFailure as exc:
                verify_payload = self._normalize_failure_verify_payload(round_id, exc.verify_payload)
                return self._finalize_round(
                    context=context,
                    round_state=round_state,
                    runtime_state=runtime_state,
                    verify_payload=verify_payload,
                    worker_result=worker_result,
                    decision_name="reset",
                    notes=str(exc),
                    failure_class="verifier_partial_failure",
                    worktree_created=worktree_created,
                )
            except Exception as exc:  # noqa: BLE001
                verify_payload = self._synthetic_failure_verify_payload(round_id, benchmark_status="verifier_crash")
                return self._finalize_round(
                    context=context,
                    round_state=round_state,
                    runtime_state=runtime_state,
                    verify_payload=verify_payload,
                    worker_result=worker_result,
                    decision_name="reset",
                    notes=str(exc),
                    failure_class="verifier_crash",
                    worktree_created=worktree_created,
                )

            if verifier_bundle.get("tool_handoff"):
                self.recorder.record_tool_handoff(verifier_bundle["tool_handoff"])
            if verifier_bundle.get("api_handoff"):
                self.recorder.record_api_handoff(verifier_bundle["api_handoff"])

            vsg_result = self.vsg_runner(verify_payload)
            verify_payload["benchmark_gain_pct"] = float(vsg_result.get("gain", 0.0))
            self._write_json(self.state_store.verify_result_path(round_id), verify_payload)

            decision_name = str(vsg_result["decision"])
            if decision_name == "needs_review":
                self._write_decision(round_id, Decision.NEEDS_REVIEW, "VSG flagged the round for manual review.")
                self._append_ledger_row(
                    round_state=round_state,
                    start_commit=context.runtime_state.current_best_commit,
                    end_commit=worker_result.get("end_commit", context.runtime_state.current_best_commit),
                    verify_payload=verify_payload,
                    gate=int(vsg_result.get("gate", 0)),
                    gain=float(vsg_result.get("gain", 0.0)),
                    decision_name=decision_name,
                    failure_class="needs_review",
                    notes="vsg escalation",
                )
                self._update_candidate_status(candidate.candidate_id, "blocked")
                runtime_state = runtime_state.model_copy(
                    update={
                        "loop_status": LoopStatus.AWAIT_HUMAN,
                        "active_round_id": round_id,
                        "active_execution_worktree": None,
                        "human_wait_reason": "needs_review from vsg",
                    }
                )
                self._write_runtime_state(runtime_state)
                self._archive_round(round_id)
                self.recorder.record_event_handoff(
                    {
                        "event_id": f"evt-{round_id}-await-human",
                        "round_id": round_id,
                        "kind": "round_status",
                        "payload": {"status": "await_human", "reason": "needs_review"},
                        "recorded_at": self._timestamp(),
                        "origin_role": "Conductor",
                    }
                )
                self.observer_runner(self.docs_root)
                return {"status": "await_human", "round_id": round_id}

            return self._finalize_round(
                context=context,
                round_state=round_state,
                runtime_state=runtime_state,
                verify_payload=verify_payload,
                worker_result=worker_result,
                decision_name=decision_name,
                notes="completed",
                failure_class="none" if decision_name == "keep" else verify_payload["benchmark_status"],
                worktree_created=worktree_created,
                gate=int(vsg_result.get("gate", 0)),
                gain=float(vsg_result.get("gain", 0.0)),
            )
        finally:
            if worktree_created:
                self.worktree_manager.remove_round_worktree(round_id)

    def _finalize_round(
        self,
        context: _ExecutionContext,
        round_state,
        runtime_state: RuntimeState,
        verify_payload: dict[str, Any],
        worker_result: dict[str, Any],
        decision_name: str,
        notes: str,
        failure_class: str,
        worktree_created: bool,
        gate: int = 0,
        gain: float = 0.0,
    ) -> dict[str, Any]:
        round_id = context.round_id
        self._write_json(self.state_store.verify_result_path(round_id), verify_payload)
        decision_enum = Decision.KEEP if decision_name == "keep" else Decision.RESET
        start_commit = context.runtime_state.current_best_commit
        proposed_end_commit = worker_result.get("end_commit", start_commit)
        keep_integration = None
        end_commit = proposed_end_commit
        decision_summary = f"{decision_name} round based on verify and VSG outcomes."
        if decision_name == "keep":
            keep_integration = self.keep_integrator(round_state, start_commit, proposed_end_commit)
            end_commit = str(keep_integration["end_commit"])
            decision_summary = str(keep_integration["summary"])

        self._write_decision(round_id, decision_enum, decision_summary)
        reflection_result = self.reflector_runner(
            docs_root=self.docs_root,
            round_id=round_id,
            decision=decision_name,
            worker_change_note=worker_result.get("change_note", {}).get("summary", notes),
            verify_payload=verify_payload,
            recent_ledger_entries=self._load_ledger_rows(),
            candidate_lifecycle={
                "candidate_id": context.candidate.candidate_id,
                "status": "active",
            },
        )

        self._append_ledger_row(
            round_state=round_state,
            start_commit=start_commit,
            end_commit=end_commit,
            verify_payload=verify_payload,
            gate=gate,
            gain=gain,
            decision_name=decision_name,
            failure_class=failure_class,
            notes=decision_summary if decision_name == "keep" else notes,
        )
        self._update_candidate_status(
            context.candidate.candidate_id,
            "kept" if decision_name == "keep" else "reset",
        )

        if decision_name == "keep":
            runtime_state = runtime_state.model_copy(
                update={
                    "loop_status": LoopStatus.PLANNING,
                    "current_best_commit": end_commit,
                    "current_best_round_id": round_id,
                    "current_best_candidate_id": context.candidate.candidate_id,
                    "active_round_id": None,
                    "active_execution_worktree": None,
                    "human_wait_reason": "none",
                }
            )
        else:
            runtime_state = runtime_state.model_copy(
                update={
                    "loop_status": LoopStatus.PLANNING,
                    "active_round_id": None,
                    "active_execution_worktree": None,
                    "human_wait_reason": "none",
                }
            )
        self._write_runtime_state(runtime_state)

        self.recorder.record_event_handoff(
            {
                "event_id": f"evt-{round_id}-complete",
                "round_id": round_id,
                "kind": "round_complete",
                "payload": {"decision": decision_name, "failure_class": failure_class},
                "recorded_at": self._timestamp(),
                "origin_role": "Conductor",
            }
        )
        self.observer_runner(self.docs_root)
        self._archive_round(round_id)
        return {
            "status": decision_name,
            "round_id": round_id,
            "reflection": reflection_result["reflection"],
        }

    def _load_runtime_state(self) -> RuntimeState:
        path = self.state_store.runtime_state_path()
        if path.exists():
            return self.state_store.load_runtime_state()
        head_commit = self._git_output(["git", "rev-parse", "--short", "HEAD"], fallback="unknown")
        branch_name = self._git_output(["git", "branch", "--show-current"], fallback="quivr-auto-harness")
        return RuntimeState(
            loop_status=LoopStatus.DESIGN_ONLY,
            current_best_commit=head_commit,
            current_best_round_id="none",
            current_best_candidate_id="none",
            control_branch=branch_name,
            control_worktree=self.repo_root,
            active_round_id=None,
            active_execution_worktree=None,
            human_wait_reason="none",
            last_updated=self._timestamp(),
        )

    def _next_round_id(self) -> str:
        if self.round_id_factory is not None:
            return self.round_id_factory()

        prefix = datetime.now().strftime("r-%Y%m%d-")
        existing = {path.name for path in (self.docs_root / "state" / "rounds").glob(f"{prefix}*")}
        sequence = 1
        while True:
            round_id = f"{prefix}{sequence:03d}"
            if round_id not in existing:
                return round_id
            sequence += 1

    def _write_runtime_state(self, runtime_state: RuntimeState) -> None:
        runtime_state = runtime_state.model_copy(update={"last_updated": self._timestamp()})
        self.state_store.write_runtime_state(runtime_state)
        (self.docs_root / "runtime-state.md").write_text(
            render_runtime_state_markdown(runtime_state) + "\n",
            encoding="utf-8",
        )

    def _render_round_plan(self, round_state) -> None:
        (self.docs_root / "round-plan.md").write_text(
            render_round_plan_markdown(round_state) + "\n",
            encoding="utf-8",
        )

    def _render_plan_review(self, review_result) -> None:
        (self.docs_root / "plan-review.md").write_text(
            render_plan_review_markdown(review_result) + "\n",
            encoding="utf-8",
        )

    def _write_change_note(self, round_id: str, change_note: dict[str, Any]) -> None:
        path = self.state_store.round_state_path(round_id).parent / "change_note.json"
        self._write_json(path, change_note)

    def _write_decision(self, round_id: str, decision: Decision, summary: str) -> None:
        result = DecisionResult(round_id=round_id, decision=decision, summary=summary)
        self.state_store.write_decision_result(result)

    def _normalize_verify_payload(self, round_id: str, verifier_bundle: dict[str, Any]) -> dict[str, Any]:
        verify_payload = dict(verifier_bundle["verify"])
        verify_payload["round_id"] = round_id
        benchmark_summary = verifier_bundle.get("benchmark_summary", {})
        verify_payload["benchmark_summary"] = benchmark_summary
        verify_payload["benchmark_gain_pct"] = 0.0
        verify_payload.setdefault("api_event_id", None)
        return verify_payload

    def _normalize_failure_verify_payload(self, round_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        verify_payload = dict(payload)
        verify_payload["round_id"] = round_id
        verify_payload.setdefault("benchmark_summary", {})
        verify_payload.setdefault("benchmark_gain_pct", 0.0)
        verify_payload.setdefault("api_event_id", None)
        return verify_payload

    def _synthetic_failure_verify_payload(self, round_id: str, benchmark_status: str) -> dict[str, Any]:
        return {
            "round_id": round_id,
            "tests_passed": False,
            "quality_passed": False,
            "benchmark_status": benchmark_status,
            "shadow_status": "needs_execution",
            "benchmark_summary": {},
            "benchmark_gain_pct": 0.0,
            "api_event_id": None,
        }

    def _append_ledger_row(
        self,
        round_state,
        start_commit: str,
        end_commit: str,
        verify_payload: dict[str, Any],
        gate: int,
        gain: float,
        decision_name: str,
        failure_class: str,
        notes: str,
    ) -> None:
        fieldnames = [
            "round_id",
            "candidate_id",
            "candidate_family",
            "direction",
            "round_type",
            "failure_class",
            "worktree_id",
            "start_commit",
            "end_commit",
            "tests_passed",
            "quality_guard_passed",
            "benchmark_status",
            "baseline_full_session_p50_ms",
            "new_full_session_p50_ms",
            "baseline_session_p90_ms",
            "new_session_p90_ms",
            "gate",
            "gain",
            "decision",
            "notes",
        ]
        self.experiment_ledger_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.experiment_ledger_path.exists():
            with self.experiment_ledger_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
                writer.writeheader()
        benchmark_summary = verify_payload.get("benchmark_summary", {})
        with self.experiment_ledger_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
            writer.writerow(
                {
                    "round_id": round_state.round_id,
                    "candidate_id": round_state.candidate_id,
                    "candidate_family": round_state.candidate_family,
                    "direction": round_state.direction,
                    "round_type": round_state.round_type,
                    "failure_class": failure_class,
                    "worktree_id": Path(round_state.execution_worktree).name if round_state.execution_worktree else "none",
                    "start_commit": start_commit,
                    "end_commit": end_commit,
                    "tests_passed": str(verify_payload.get("tests_passed", False)).lower(),
                    "quality_guard_passed": str(verify_payload.get("quality_passed", False)).lower(),
                    "benchmark_status": verify_payload.get("benchmark_status", "unknown"),
                    "baseline_full_session_p50_ms": 100.0,
                    "new_full_session_p50_ms": benchmark_summary.get("full_session_p50_ms", ""),
                    "baseline_session_p90_ms": 100.0,
                    "new_session_p90_ms": benchmark_summary.get("session_p90_ms", ""),
                    "gate": gate,
                    "gain": gain,
                    "decision": decision_name,
                    "notes": notes,
                }
            )

    def _load_ledger_rows(self) -> list[dict[str, str]]:
        if not self.experiment_ledger_path.exists():
            return []
        with self.experiment_ledger_path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle, delimiter="\t"))

    def _update_candidate_status(self, candidate_id: str, new_status: str) -> None:
        fieldnames: list[str] = []
        rows: list[dict[str, str]] = []
        if self.candidate_registry_path.exists():
            with self.candidate_registry_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                fieldnames = list(reader.fieldnames or [])
                rows = list(reader)
        if not fieldnames:
            fieldnames = [
                "candidate_id",
                "candidate_family",
                "direction",
                "candidate_class",
                "source",
                "target_path",
                "evidence",
                "verification",
                "status",
                "last_result",
                "do_not_repeat",
                "notes",
            ]
        for row in rows:
            if row["candidate_id"] == candidate_id:
                row["status"] = new_status
        with self.candidate_registry_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

    def _archive_round(self, round_id: str) -> None:
        archive_root = self.docs_root / "rounds" / round_id
        archive_root.mkdir(parents=True, exist_ok=True)
        round_root = self.state_store.round_state_path(round_id).parent
        if self.state_store.round_state_path(round_id).exists():
            (archive_root / "plan.md").write_text(
                (self.docs_root / "round-plan.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        if self.state_store.review_result_path(round_id).exists():
            (archive_root / "plan-review.md").write_text(
                (self.docs_root / "plan-review.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        if self.state_store.verify_result_path(round_id).exists():
            verify_payload = json.loads(self.state_store.verify_result_path(round_id).read_text(encoding="utf-8"))
            (archive_root / "verify.md").write_text(
                "\n".join(
                    [
                        "# Verify",
                        "",
                        f"- `round_id`: `{round_id}`",
                        f"- `tests_passed`: `{str(verify_payload.get('tests_passed', False)).lower()}`",
                        f"- `quality_passed`: `{str(verify_payload.get('quality_passed', False)).lower()}`",
                        f"- `benchmark_status`: `{verify_payload.get('benchmark_status', 'unknown')}`",
                        f"- `shadow_status`: `{verify_payload.get('shadow_status', 'unknown')}`",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
        if self.state_store.decision_result_path(round_id).exists():
            decision_payload = json.loads(self.state_store.decision_result_path(round_id).read_text(encoding="utf-8"))
            (archive_root / "decision.md").write_text(
                "\n".join(
                    [
                        "# Decision",
                        "",
                        f"- `round_id`: `{round_id}`",
                        f"- `decision`: `{decision_payload['decision']}`",
                        f"- `summary`: {decision_payload['summary']}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
        artifacts = {
            "round_id": round_id,
            "state_root": str(round_root),
            "archive_root": str(archive_root),
        }
        self._write_json(archive_root / "artifacts.json", artifacts)
        (archive_root / "summary.md").write_text(
            "\n".join(
                [
                    "# Round Summary",
                    "",
                    f"- `round_id`: `{round_id}`",
                    f"- `state_root`: `{round_root}`",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    def _git_output(self, cmd: list[str], fallback: str) -> str:
        try:
            return subprocess.check_output(cmd, cwd=self.repo_root, text=True).strip() or fallback
        except Exception:  # noqa: BLE001
            return fallback

    def _default_worker_runner(self, round_state, launch_result, runtime_state: RuntimeState) -> dict[str, Any]:
        return {
            "change_note": {
                "round_id": round_state.round_id,
                "agent_id": launch_result.manifest.agent_id,
                "changed_files": round_state.allowed_files,
                "summary": "default worker simulation completed",
            },
            "tool_handoff": {
                "event_id": f"tool-{round_state.round_id}-worker",
                "round_id": round_state.round_id,
                "agent_id": launch_result.manifest.agent_id,
                "origin_role": "Worker",
                "tools": ["worker_runner"],
                "recorded_at": self._timestamp(),
            },
            "end_commit": f"{runtime_state.current_best_commit}-changed-{round_state.round_id}",
        }

    def _default_verifier_runner(self, round_state, launch_result) -> dict[str, Any]:
        worktree = Path(round_state.execution_worktree)
        core_worktree = worktree / "core"
        benchmark_sessions = [
            {"full_session_ms": 95.0, "turns_ms": [30.0, 30.0, 35.0]},
            {"full_session_ms": 92.0, "turns_ms": [30.0, 30.0, 32.0]},
            {"full_session_ms": 90.0, "turns_ms": [28.0, 30.0, 32.0]},
            {"full_session_ms": 89.0, "turns_ms": [28.0, 29.0, 32.0]},
            {"full_session_ms": 91.0, "turns_ms": [29.0, 30.0, 32.0]},
        ]
        quality_answers = [
            "Project Atlas keeps notes in Paris.",
            "The release codename is Orchid and the timeline is Q3 2026.",
            "Project Atlas uses Orchid and keeps notes in Paris.",
        ]
        result = verify_round(
            round_id=round_state.round_id,
            round_root=self.state_store.round_state_path(round_state.round_id).parent,
            tests_runner=lambda: {
                "command": round_state.tests_command,
                "returncode": 0,
                "stdout": "dry-run-safe deterministic pass",
                "stderr": "",
                "tests_passed": True,
            },
            quality_runner=lambda: run_quality_guard(worktree=core_worktree, scripted_answers=quality_answers),
            benchmark_runner=lambda: run_primary_benchmark(
                worktree=core_worktree,
                measured_sessions=benchmark_sessions,
                warmup_session={"full_session_ms": 120.0, "turns_ms": [40.0, 40.0, 40.0]},
            ),
            shadow_runner=lambda: run_shadow_e2e(worktree=core_worktree, env={}),
        )
        return {
            "verify": result["verify"],
            "benchmark_summary": result["benchmark_summary"],
            "tool_handoff": {
                "event_id": f"tool-{round_state.round_id}-verifier",
                "round_id": round_state.round_id,
                "agent_id": launch_result.manifest.agent_id,
                "origin_role": "Verifier",
                "tools": ["run_tests", "run_quality_guard", "run_benchmark", "run_shadow_e2e"],
                "recorded_at": self._timestamp(),
            },
            "api_handoff": result["api_summary"],
        }

    def _default_vsg_runner(self, verify_payload: dict[str, Any]) -> dict[str, Any]:
        return evaluate_vsg(
            baseline_full_session_p50_ms=100.0,
            verify_payload=verify_payload,
            baseline_session_p90_ms=100.0,
        )

    def _default_keep_integrator(
        self,
        round_state,
        start_commit: str,
        proposed_end_commit: str,
    ) -> dict[str, Any]:
        return integrate_keep_from_worktree(
            round_state=round_state,
            start_commit=start_commit,
            proposed_end_commit=proposed_end_commit,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--real-keep", action="store_true")
    args = parser.parse_args()
    if not args.once:
        return 2

    repo_root = Path(__file__).resolve().parents[3]
    controller = AutoHarnessController(
        repo_root=repo_root,
        keep_integrator=integrate_keep_from_worktree if args.real_keep else None,
    )
    result = controller.run_once()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
