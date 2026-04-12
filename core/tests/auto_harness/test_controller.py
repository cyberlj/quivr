import csv
import json
import shutil
from pathlib import Path

import pytest

from quivr_core.auto_harness.contracts import LoopStatus, ReviewOutcome, ReviewResult, RuntimeState
from quivr_core.auto_harness.controller import AutoHarnessController, PartialVerifierFailure
from quivr_core.auto_harness.state_store import StateStore


class FakeWorktreeManager:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.created: list[tuple[str, str]] = []
        self.removed: list[str] = []

    def path_for_round(self, round_id: str) -> Path:
        return self.repo_root / ".worktrees" / f"wt-{round_id}"

    def create_round_worktree(self, round_id: str, current_best_commit: str) -> Path:
        path = self.path_for_round(round_id)
        path.mkdir(parents=True, exist_ok=True)
        self.created.append((round_id, current_best_commit))
        return path

    def remove_round_worktree(self, round_id: str) -> Path:
        path = self.path_for_round(round_id)
        self.removed.append(round_id)
        if path.exists():
            shutil.rmtree(path)
        return path


class PartialCreateWorktreeManager(FakeWorktreeManager):
    def create_round_worktree(self, round_id: str, current_best_commit: str) -> Path:
        path = self.path_for_round(round_id)
        path.mkdir(parents=True, exist_ok=True)
        self.created.append((round_id, current_best_commit))
        raise RuntimeError("worktree add interrupted")


class FixedReviewer:
    def __init__(self, outcome: ReviewOutcome):
        self.outcome = outcome

    def review(self, round_state):
        return ReviewResult(
            round_id=round_state.round_id,
            review_outcome=self.outcome,
            allows_execution=self.outcome == ReviewOutcome.APPROVED,
            requires_human=False,
            scope_check="bounded",
            verification_check="complete",
            repeat_check="novel",
            reset_check="present",
            priority_check="candidate_valid",
            review_notes=[f"forced {self.outcome.value}"],
        )


def make_runtime_state(control_worktree: Path) -> RuntimeState:
    return RuntimeState(
        loop_status=LoopStatus.PLANNING,
        current_best_commit="abc123",
        current_best_round_id="none",
        current_best_candidate_id="none",
        control_branch="quivr-auto-harness",
        control_worktree=control_worktree,
        active_round_id=None,
        active_execution_worktree=None,
        human_wait_reason="none",
        last_updated="2026-04-11T12:00:00Z",
    )


def write_registry(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def read_registry_statuses(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return {row["candidate_id"]: row["status"] for row in reader}


def bootstrap_rows() -> list[dict[str, str]]:
    return [
        {
            "candidate_id": "perf-history-001",
            "candidate_family": "rag",
            "direction": "history-trim",
            "candidate_class": "performance",
            "source": "review-findings",
            "target_path": "core/quivr_core/rag/quivr_rag.py",
            "evidence": "history hotspot",
            "verification": "run tests and benchmark",
            "status": "ready",
            "last_result": "none",
            "do_not_repeat": "none",
            "notes": "",
        },
        {
            "candidate_id": "perf-langgraph-001",
            "candidate_family": "rag",
            "direction": "langgraph-route",
            "candidate_class": "performance",
            "source": "review-findings",
            "target_path": "core/quivr_core/rag/quivr_rag_langgraph.py",
            "evidence": "langgraph hotspot",
            "verification": "run tests and benchmark",
            "status": "ready",
            "last_result": "none",
            "do_not_repeat": "none",
            "notes": "",
        },
    ]


def make_controller(
    tmp_path: Path,
    *,
    reviewer=None,
    worker_runner=None,
    verifier_runner=None,
    vsg_runner=None,
    keep_integrator=None,
):
    docs_root = tmp_path / "docs" / "auto-harness"
    state_store = StateStore(docs_root)
    state_store.write_runtime_state(make_runtime_state(tmp_path))
    write_registry(docs_root / "candidate-registry.tsv", bootstrap_rows())
    (docs_root / "reflection-log.md").write_text("# Reflection Log\n\nNo live rounds have started yet.\n", encoding="utf-8")
    (docs_root / "experiment-ledger.tsv").write_text(
        "round_id\tcandidate_id\tcandidate_family\tdirection\tround_type\tfailure_class\tworktree_id\tstart_commit\tend_commit\ttests_passed\tquality_guard_passed\tbenchmark_status\tbaseline_full_session_p50_ms\tnew_full_session_p50_ms\tbaseline_session_p90_ms\tnew_session_p90_ms\tgate\tgain\tdecision\tnotes\n",
        encoding="utf-8",
    )
    worktree_manager = FakeWorktreeManager(tmp_path)
    controller = AutoHarnessController(
        repo_root=tmp_path,
        docs_root=docs_root,
        reviewer=reviewer,
        worktree_manager=worktree_manager,
        worker_runner=worker_runner,
        verifier_runner=verifier_runner,
        vsg_runner=vsg_runner,
        keep_integrator=keep_integrator,
    )
    return controller, docs_root, state_store, worktree_manager


def successful_worker(round_state, launch_result, runtime_state):
    return {
        "change_note": {
            "round_id": round_state.round_id,
            "agent_id": launch_result.manifest.agent_id,
            "changed_files": round_state.allowed_files,
            "summary": "trimmed repeated history packing",
        },
        "tool_handoff": {
            "event_id": f"tool-{round_state.round_id}-worker",
            "round_id": round_state.round_id,
            "agent_id": launch_result.manifest.agent_id,
            "origin_role": "Worker",
            "tools": ["worker_runner"],
            "recorded_at": "2026-04-11T12:05:00Z",
        },
        "end_commit": f"{runtime_state.current_best_commit}-{round_state.round_id}",
    }


def successful_verifier(round_state, launch_result):
    return {
        "verify": {
            "round_id": round_state.round_id,
            "tests_passed": True,
            "quality_passed": True,
            "benchmark_status": "valid",
            "shadow_status": "needs_execution",
            "api_event_id": None,
        },
        "benchmark_summary": {
            "full_session_p50_ms": 90.0,
            "session_p90_ms": 100.0,
        },
        "tool_handoff": {
            "event_id": f"tool-{round_state.round_id}-verifier",
            "round_id": round_state.round_id,
            "agent_id": launch_result.manifest.agent_id,
            "origin_role": "Verifier",
            "tools": ["verify_round"],
            "recorded_at": "2026-04-11T12:06:00Z",
        },
        "api_handoff": None,
    }


def real_keep_integrator(round_state, start_commit: str, proposed_end_commit: str):
    return {
        "end_commit": f"{start_commit}-real-{round_state.round_id}",
        "integrated": True,
        "summary": "real keep integration completed",
    }


def test_controller_generates_unique_round_ids_across_consecutive_runs(tmp_path):
    controller, docs_root, _, _ = make_controller(
        tmp_path,
        worker_runner=successful_worker,
        verifier_runner=successful_verifier,
        vsg_runner=lambda verify_payload: {
            "gate": 1,
            "gain": 0.1,
            "decision": "keep",
            "compatibility_confirmed": False,
        },
        keep_integrator=real_keep_integrator,
    )

    first = controller.run_once()
    second = controller.run_once()

    assert first["round_id"] != second["round_id"]
    assert (docs_root / "state" / "rounds" / first["round_id"] / "round.json").exists()
    assert (docs_root / "state" / "rounds" / second["round_id"] / "round.json").exists()


def test_candidate_pool_empty_moves_runtime_to_candidate_pool_empty(tmp_path):
    controller, docs_root, state_store, _ = make_controller(tmp_path)
    write_registry(docs_root / "candidate-registry.tsv", [])

    result = controller.run_once()
    runtime_state = state_store.load_runtime_state()

    assert result["status"] == "candidate_pool_empty"
    assert runtime_state.loop_status == LoopStatus.CANDIDATE_POOL_EMPTY


def test_review_revise_returns_to_planning_without_execution(tmp_path):
    controller, docs_root, state_store, worktree_manager = make_controller(
        tmp_path,
        reviewer=FixedReviewer(ReviewOutcome.REVISE),
    )

    result = controller.run_once()
    runtime_state = state_store.load_runtime_state()
    statuses = read_registry_statuses(docs_root / "candidate-registry.tsv")

    assert result["status"] == "review_revise"
    assert runtime_state.loop_status == LoopStatus.PLANNING
    assert worktree_manager.created == []
    assert statuses["perf-history-001"] == "ready"


def test_partial_worktree_creation_is_cleaned_up(tmp_path):
    docs_root = tmp_path / "docs" / "auto-harness"
    state_store = StateStore(docs_root)
    state_store.write_runtime_state(make_runtime_state(tmp_path))
    write_registry(docs_root / "candidate-registry.tsv", bootstrap_rows())
    (docs_root / "reflection-log.md").write_text("# Reflection Log\n\nNo live rounds have started yet.\n", encoding="utf-8")
    (docs_root / "experiment-ledger.tsv").write_text(
        "round_id\tcandidate_id\tcandidate_family\tdirection\tround_type\tfailure_class\tworktree_id\tstart_commit\tend_commit\ttests_passed\tquality_guard_passed\tbenchmark_status\tbaseline_full_session_p50_ms\tnew_full_session_p50_ms\tbaseline_session_p90_ms\tnew_session_p90_ms\tgate\tgain\tdecision\tnotes\n",
        encoding="utf-8",
    )
    worktree_manager = PartialCreateWorktreeManager(tmp_path)
    controller = AutoHarnessController(
        repo_root=tmp_path,
        docs_root=docs_root,
        worktree_manager=worktree_manager,
    )

    with pytest.raises(RuntimeError):
        controller.run_once()

    assert len(worktree_manager.removed) == 1
    removed_round_id = worktree_manager.removed[0]
    assert removed_round_id.startswith("r-")
    assert not worktree_manager.path_for_round(removed_round_id).exists()


def test_worker_crash_records_failure_and_cleans_worktree(tmp_path):
    def crashing_worker(round_state, launch_result, runtime_state):
        raise RuntimeError("worker crashed")

    controller, docs_root, _, worktree_manager = make_controller(
        tmp_path,
        worker_runner=crashing_worker,
        verifier_runner=successful_verifier,
    )

    result = controller.run_once()
    statuses = read_registry_statuses(docs_root / "candidate-registry.tsv")

    assert result["status"] == "reset"
    assert worktree_manager.removed == [result["round_id"]]
    assert statuses["perf-history-001"] == "reset"
    assert json.loads((docs_root / "state" / "rounds" / result["round_id"] / "decision.json").read_text(encoding="utf-8"))["decision"] == "reset"


def test_verifier_failure_records_partial_state_and_cleans_worktree(tmp_path):
    def partial_verifier(round_state, launch_result):
        raise PartialVerifierFailure(
            "benchmark runner interrupted",
            verify_payload={
                "round_id": round_state.round_id,
                "tests_passed": True,
                "quality_passed": True,
                "benchmark_status": "interrupted",
                "shadow_status": "needs_execution",
                "api_event_id": None,
                "benchmark_summary": {
                    "full_session_p50_ms": 100.0,
                    "session_p90_ms": 100.0,
                },
            },
        )

    controller, docs_root, _, worktree_manager = make_controller(
        tmp_path,
        worker_runner=successful_worker,
        verifier_runner=partial_verifier,
    )

    result = controller.run_once()
    verify_payload = json.loads((docs_root / "state" / "rounds" / result["round_id"] / "verify.json").read_text(encoding="utf-8"))

    assert result["status"] == "reset"
    assert worktree_manager.removed == [result["round_id"]]
    assert verify_payload["benchmark_status"] == "interrupted"


@pytest.mark.parametrize(
    ("decision", "expected_candidate_status", "keep_integrator"),
    [
        ("keep", "kept", real_keep_integrator),
        ("reset", "reset", None),
    ],
)
def test_keep_and_reset_write_back_runtime_and_candidate_lifecycle(
    tmp_path,
    decision,
    expected_candidate_status,
    keep_integrator,
):
    controller, docs_root, state_store, _ = make_controller(
        tmp_path,
        worker_runner=successful_worker,
        verifier_runner=successful_verifier,
        vsg_runner=lambda verify_payload: {
            "gate": 1,
            "gain": 0.1,
            "decision": decision,
            "compatibility_confirmed": False,
        },
        keep_integrator=keep_integrator,
    )

    result = controller.run_once()
    runtime_state = state_store.load_runtime_state()
    statuses = read_registry_statuses(docs_root / "candidate-registry.tsv")

    if decision == "keep":
        assert runtime_state.current_best_commit != "abc123"
        assert runtime_state.current_best_candidate_id == "perf-history-001"
    else:
        assert runtime_state.current_best_commit == "abc123"
        assert runtime_state.current_best_candidate_id == "none"
    assert result["status"] == decision
    assert statuses["perf-history-001"] == expected_candidate_status


def test_default_keep_policy_is_dry_run_safe_and_preserves_baseline(tmp_path):
    controller, docs_root, state_store, _ = make_controller(
        tmp_path,
        worker_runner=successful_worker,
        verifier_runner=successful_verifier,
        vsg_runner=lambda verify_payload: {
            "gate": 1,
            "gain": 0.1,
            "decision": "keep",
            "compatibility_confirmed": False,
        },
    )

    result = controller.run_once()
    runtime_state = state_store.load_runtime_state()
    decision_payload = json.loads(
        (docs_root / "state" / "rounds" / result["round_id"] / "decision.json").read_text(encoding="utf-8")
    )

    assert result["status"] == "keep"
    assert runtime_state.current_best_commit == "abc123"
    assert "dry-run-safe" in decision_payload["summary"]


def test_needs_review_moves_runtime_to_await_human(tmp_path):
    controller, docs_root, state_store, _ = make_controller(
        tmp_path,
        worker_runner=successful_worker,
        verifier_runner=successful_verifier,
        vsg_runner=lambda verify_payload: {
            "gate": 1,
            "gain": 0.1,
            "decision": "needs_review",
            "compatibility_confirmed": False,
        },
    )

    result = controller.run_once()
    runtime_state = state_store.load_runtime_state()

    assert result["status"] == "await_human"
    assert runtime_state.loop_status == LoopStatus.AWAIT_HUMAN
    assert "needs_review" in runtime_state.human_wait_reason
    assert "recommendation" in (docs_root / "observer-summary.md").read_text(encoding="utf-8")
