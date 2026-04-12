from __future__ import annotations

from pathlib import Path
from typing import Any

from quivr_core.auto_harness.contracts import ReflectionResult
from quivr_core.auto_harness.state_store import StateStore


def reflect_round(
    docs_root: str | Path,
    round_id: str,
    decision: str,
    worker_change_note: str,
    verify_payload: dict[str, Any] | None,
    recent_ledger_entries: list[dict[str, Any]],
    candidate_lifecycle: dict[str, Any],
) -> dict[str, Any]:
    if not verify_payload:
        raise ValueError("verify_payload is required before reflection")
    if verify_payload.get("round_id") not in {None, round_id}:
        raise ValueError("verify_payload round_id does not match reflection round_id")
    if decision not in {"keep", "reset"}:
        raise ValueError("reflection requires a keep or reset decision")

    docs_root = Path(docs_root)
    root_cause = _infer_root_cause(verify_payload, recent_ledger_entries, decision)
    replan_recommendation = _build_replan_recommendation(
        decision=decision,
        root_cause=root_cause,
        candidate_lifecycle=candidate_lifecycle,
    )
    lessons = [
        f"root_cause={root_cause}",
        f"do_not_repeat={_build_do_not_repeat(root_cause, decision)}",
    ]
    reflection = ReflectionResult(
        round_id=round_id,
        summary=f"{decision}: {worker_change_note}",
        replan_recommendation=replan_recommendation,
        lessons=lessons,
    )

    StateStore(docs_root).write_reflection_result(reflection)
    archive_path = _write_round_reflection_markdown(
        docs_root=docs_root,
        round_id=round_id,
        decision=decision,
        worker_change_note=worker_change_note,
        root_cause=root_cause,
        replan_recommendation=replan_recommendation,
        candidate_lifecycle=candidate_lifecycle,
    )
    log_path = _append_reflection_log(
        docs_root=docs_root,
        round_id=round_id,
        decision=decision,
        worker_change_note=worker_change_note,
        root_cause=root_cause,
        replan_recommendation=replan_recommendation,
    )
    return {
        "reflection": reflection.model_dump(mode="json"),
        "reflection_log_path": str(log_path),
        "archive_markdown_path": str(archive_path),
        "replan_recommendation": replan_recommendation,
    }


def _infer_root_cause(
    verify_payload: dict[str, Any],
    recent_ledger_entries: list[dict[str, Any]],
    decision: str,
) -> str:
    if not verify_payload.get("tests_passed", False):
        return "tests_failed"
    if not verify_payload.get("quality_passed", False):
        return "quality_guard_failed"
    if verify_payload.get("benchmark_status") != "valid":
        return "benchmark_invalid"
    if verify_payload.get("shadow_status") == "failure":
        return "shadow_failure"
    if decision == "keep":
        return "verified_gain"

    for entry in reversed(recent_ledger_entries):
        failure_class = entry.get("failure_class")
        if failure_class:
            return str(failure_class)
    return "insufficient_gain"


def _build_replan_recommendation(
    decision: str,
    root_cause: str,
    candidate_lifecycle: dict[str, Any],
) -> str:
    candidate_status = candidate_lifecycle.get("status", "unknown")
    if decision == "keep":
        return f"promote learning and continue with the next bounded candidate; current candidate status={candidate_status}"
    return f"re-plan before another round; address {root_cause}; current candidate status={candidate_status}"


def _build_do_not_repeat(root_cause: str, decision: str) -> str:
    if decision == "keep":
        return "do not widen the mutable surface while carrying forward the winning change"
    return f"do not rerun the same round without addressing {root_cause}"


def _write_round_reflection_markdown(
    docs_root: Path,
    round_id: str,
    decision: str,
    worker_change_note: str,
    root_cause: str,
    replan_recommendation: str,
    candidate_lifecycle: dict[str, Any],
) -> Path:
    archive_root = docs_root / "rounds" / round_id
    archive_root.mkdir(parents=True, exist_ok=True)
    path = archive_root / "reflection.md"
    lines = [
        "# Reflection",
        "",
        f"- `round_id`: `{round_id}`",
        f"- `decision`: `{decision}`",
        f"- `worker_change_note`: {worker_change_note}",
        f"- `root_cause`: `{root_cause}`",
        f"- `candidate_status`: `{candidate_lifecycle.get('status', 'unknown')}`",
        f"- `replan_recommendation`: {replan_recommendation}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _append_reflection_log(
    docs_root: Path,
    round_id: str,
    decision: str,
    worker_change_note: str,
    root_cause: str,
    replan_recommendation: str,
) -> Path:
    path = docs_root / "reflection-log.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Reflection Log\n"
    if "No live rounds have started yet." in existing:
        existing = existing.replace("\nNo live rounds have started yet.\n", "\n")
        existing = existing.rstrip() + "\n"
    entry = "\n".join(
        [
            "",
            f"## {round_id}",
            "",
            f"- `round_id`: `{round_id}`",
            f"- `decision`: `{decision}`",
            f"- `root_cause`: `{root_cause}`",
            f"- `evidence`: {worker_change_note}",
            f"- `next_move`: {replan_recommendation}",
        ]
    )
    path.write_text(existing.rstrip() + entry + "\n", encoding="utf-8")
    return path
