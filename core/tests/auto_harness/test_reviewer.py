from pathlib import Path

from quivr_core.auto_harness.candidate_service import CandidateRecord
from quivr_core.auto_harness.contracts import LoopStatus, ReviewOutcome, RuntimeState
from quivr_core.auto_harness.planner import Planner
from quivr_core.auto_harness.reviewer import Reviewer


HEADER = (
    "candidate_id\tcandidate_family\tdirection\tcandidate_class\tsource\t"
    "target_path\tevidence\tverification\tstatus\tlast_result\tdo_not_repeat\tnotes\n"
)

LEDGER_HEADER = (
    "round_id\tcandidate_id\tcandidate_family\tdirection\tround_type\tfailure_class\tworktree_id\t"
    "start_commit\tend_commit\ttests_passed\tquality_guard_passed\tbenchmark_status\t"
    "baseline_full_session_p50_ms\tnew_full_session_p50_ms\tbaseline_session_p90_ms\t"
    "new_session_p90_ms\tgate\tgain\tdecision\tnotes\n"
)


def write_candidate_registry(path: Path, rows: list[str]) -> None:
    path.write_text(HEADER + "".join(rows), encoding="utf-8")


def write_ledger(path: Path, rows: list[str]) -> None:
    path.write_text(LEDGER_HEADER + "".join(rows), encoding="utf-8")


def make_runtime_state() -> RuntimeState:
    return RuntimeState(
        loop_status=LoopStatus.PLANNING,
        current_best_commit="abc123",
        current_best_round_id="r-20260410-001",
        current_best_candidate_id="perf-history-001",
        control_branch="quivr-auto-harness",
        control_worktree=Path("/tmp/control"),
        active_round_id=None,
        active_execution_worktree=None,
        human_wait_reason="none",
        last_updated="2026-04-11T10:00:00Z",
    )


def make_candidate(status: str = "ready") -> CandidateRecord:
    return CandidateRecord(
        candidate_id="perf-history-001",
        candidate_family="rag",
        direction="history-trim",
        candidate_class="performance",
        source="review-findings",
        target_path="core/quivr_core/rag/quivr_rag.py",
        evidence="chat history work is on the critical path",
        verification="focused rag tests",
        status=status,
        last_result="none",
        do_not_repeat="none",
        notes="bootstrap candidate",
    )


def candidate_row(status: str = "ready", direction: str = "history-trim") -> str:
    return (
        f"perf-history-001\trag\t{direction}\tperformance\treview-findings\t"
        "core/quivr_core/rag/quivr_rag.py\tchat history work is on the critical path\t"
        f"focused rag tests\t{status}\tnone\tnone\tbootstrap candidate\n"
    )


def planner_round():
    return Planner().plan_round(
        candidate=make_candidate(),
        runtime_state=make_runtime_state(),
        round_id="r-20260411-001",
    )


def test_reviewer_rejects_repeated_direction(tmp_path):
    registry_path = tmp_path / "candidate-registry.tsv"
    ledger_path = tmp_path / "experiment-ledger.tsv"
    reflection_path = tmp_path / "reflection-log.md"
    write_candidate_registry(registry_path, [candidate_row()])
    write_ledger(
        ledger_path,
        [
            "r-20260410-001\tperf-old-001\trag\thistory-trim\tperformance\tnone\twt-1\t"
            "abc\tdef\ttrue\ttrue\tvalid\t10\t9\t20\t18\t1\t0.1\treset\trepeated direction\n"
        ],
    )
    reflection_path.write_text("# Reflection Log\nhistory-trim failed recently\n", encoding="utf-8")

    review = Reviewer(registry_path, ledger_path, reflection_path).review(planner_round())

    assert review.review_outcome == ReviewOutcome.REJECT
    assert review.allows_execution is False


def test_reviewer_rejects_empty_verification_commands(tmp_path):
    registry_path = tmp_path / "candidate-registry.tsv"
    ledger_path = tmp_path / "experiment-ledger.tsv"
    reflection_path = tmp_path / "reflection-log.md"
    write_candidate_registry(registry_path, [candidate_row()])
    write_ledger(ledger_path, [])
    reflection_path.write_text("# Reflection Log\n", encoding="utf-8")

    round_state = planner_round().model_copy(update={"benchmark_command": ""})
    review = Reviewer(registry_path, ledger_path, reflection_path).review(round_state)

    assert review.review_outcome == ReviewOutcome.REJECT
    assert review.verification_check == "missing_commands"


def test_reviewer_rejects_candidate_blocked_by_lifecycle(tmp_path):
    registry_path = tmp_path / "candidate-registry.tsv"
    ledger_path = tmp_path / "experiment-ledger.tsv"
    reflection_path = tmp_path / "reflection-log.md"
    write_candidate_registry(registry_path, [candidate_row(status="blocked")])
    write_ledger(ledger_path, [])
    reflection_path.write_text("# Reflection Log\n", encoding="utf-8")

    review = Reviewer(registry_path, ledger_path, reflection_path).review(planner_round())

    assert review.review_outcome == ReviewOutcome.REJECT
    assert review.priority_check == "candidate_not_selectable"


def test_reviewer_can_emit_revise_without_human_escalation(tmp_path):
    registry_path = tmp_path / "candidate-registry.tsv"
    ledger_path = tmp_path / "experiment-ledger.tsv"
    reflection_path = tmp_path / "reflection-log.md"
    write_candidate_registry(registry_path, [candidate_row()])
    write_ledger(ledger_path, [])
    reflection_path.write_text("# Reflection Log\n", encoding="utf-8")

    round_state = planner_round().model_copy(
        update={"hypothesis": "Trim history and rewrite context assembly in one round"}
    )
    review = Reviewer(registry_path, ledger_path, reflection_path).review(round_state)

    assert review.review_outcome == ReviewOutcome.REVISE
    assert review.requires_human is False
    assert review.allows_execution is False


def test_reviewer_consumes_ledger_and_reflection_history(tmp_path):
    registry_path = tmp_path / "candidate-registry.tsv"
    ledger_path = tmp_path / "experiment-ledger.tsv"
    reflection_path = tmp_path / "reflection-log.md"
    write_candidate_registry(registry_path, [candidate_row(direction="fresh-direction")])
    write_ledger(
        ledger_path,
        [
            "r-20260410-001\tperf-old-001\trag\tfresh-direction\tperformance\tnoisy\twt-1\t"
            "abc\tdef\ttrue\ttrue\tvalid\t10\t9\t20\t18\t1\t0.1\treset\tfresh-direction repeated\n"
        ],
    )
    reflection_path.write_text("# Reflection Log\nfresh-direction should pause\n", encoding="utf-8")

    candidate = make_candidate()
    candidate = candidate.model_copy(update={"direction": "fresh-direction"})
    round_state = Planner().plan_round(candidate, make_runtime_state(), "r-20260411-001")
    review = Reviewer(registry_path, ledger_path, reflection_path).review(round_state)

    assert review.repeat_check == "repeated_direction"
    assert review.review_outcome == ReviewOutcome.REJECT
