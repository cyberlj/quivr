from pathlib import Path

from quivr_core.auto_harness.candidate_service import CandidateRecord
from quivr_core.auto_harness.contracts import LoopStatus, RuntimeState
from quivr_core.auto_harness.planner import Planner
from quivr_core.auto_harness.render_views import render_round_plan_markdown


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


def make_candidate() -> CandidateRecord:
    return CandidateRecord(
        candidate_id="perf-history-001",
        candidate_family="rag",
        direction="history-trim",
        candidate_class="performance",
        source="review-findings",
        target_path="core/quivr_core/rag/quivr_rag.py",
        evidence="chat history work is on the critical path",
        verification="focused rag tests",
        status="ready",
        last_result="none",
        do_not_repeat="none",
        notes="bootstrap candidate",
    )


def test_planner_materializes_full_round_state():
    planner = Planner()

    round_state = planner.plan_round(
        candidate=make_candidate(),
        runtime_state=make_runtime_state(),
        round_id="r-20260411-001",
    )

    assert round_state.round_id == "r-20260411-001"
    assert round_state.candidate_id == "perf-history-001"
    assert round_state.round_type == "performance"
    assert round_state.execution_worktree is None


def test_round_plan_includes_allowed_files_and_command_fields():
    planner = Planner()

    round_state = planner.plan_round(
        candidate=make_candidate(),
        runtime_state=make_runtime_state(),
        round_id="r-20260411-001",
    )

    assert round_state.allowed_files == ["core/quivr_core/rag/quivr_rag.py"]
    assert round_state.tests_command
    assert round_state.quality_guard_command
    assert round_state.benchmark_command
    assert round_state.shadow_command
    assert round_state.vsg_command


def test_render_output_contains_round_id_and_candidate_id():
    planner = Planner()
    round_state = planner.plan_round(
        candidate=make_candidate(),
        runtime_state=make_runtime_state(),
        round_id="r-20260411-001",
    )

    rendered = render_round_plan_markdown(round_state)

    assert "r-20260411-001" in rendered
    assert "perf-history-001" in rendered
