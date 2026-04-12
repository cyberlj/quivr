from pathlib import Path

import pytest
from pydantic import ValidationError

from quivr_core.auto_harness.contracts import (
    AgentManifest,
    Decision,
    DecisionResult,
    LoopStatus,
    RecorderEvent,
    ReflectionResult,
    ReviewOutcome,
    ReviewResult,
    RoundState,
    RuntimeState,
    ShadowStatus,
    VerifyResult,
)


def test_runtime_state_rejects_invalid_loop_status():
    with pytest.raises(ValidationError):
        RuntimeState(
            loop_status="invalid",
            current_best_commit="abc123",
            current_best_round_id="none",
            current_best_candidate_id="none",
            control_branch="quivr-auto-harness",
            control_worktree=Path("/tmp/control"),
            active_round_id=None,
            active_execution_worktree=None,
            human_wait_reason="none",
            last_updated="2026-04-11T10:00:00Z",
        )


def test_review_result_rejects_invalid_review_outcome():
    with pytest.raises(ValidationError):
        ReviewResult(
            round_id="r-20260411-001",
            review_outcome="ship-it",
            scope_check="ok",
            verification_check="ok",
            repeat_check="ok",
            reset_check="ok",
            priority_check="ok",
            review_notes=["looks fine"],
        )


def test_verify_result_rejects_invalid_shadow_status():
    with pytest.raises(ValidationError):
        VerifyResult(
            round_id="r-20260411-001",
            tests_passed=True,
            quality_passed=True,
            benchmark_status="valid",
            shadow_status="green",
            benchmark_gain_pct=1.25,
            api_event_id=None,
        )


def test_decision_result_rejects_invalid_decision():
    with pytest.raises(ValidationError):
        DecisionResult(
            round_id="r-20260411-001",
            decision="ship",
            summary="summary",
        )


def test_round_state_requires_required_fields():
    with pytest.raises(ValidationError):
        RoundState(round_id="r-20260411-001")


def test_agent_manifest_requires_allowed_commands():
    with pytest.raises(ValidationError):
        AgentManifest(
            round_id="r-20260411-001",
            agent_id="worker-1",
            role="Worker",
            worktree=Path("/tmp/wt-r-20260411-001"),
            allowed_files=["core/quivr_core/rag/quivr_rag.py"],
            forbidden_actions=["keep"],
        )


def test_contract_models_preserve_path_and_id_fields():
    round_state = RoundState(
        round_id="r-20260411-001",
        candidate_id="perf-history-001",
        candidate_family="rag",
        direction="history-trim",
        candidate_class="performance",
        round_type="performance",
        hypothesis="Trim chat history to reduce repeated work.",
        why_now="Bootstrap performance candidate.",
        allowed_files=["core/quivr_core/rag/quivr_rag.py"],
        forbidden_files=["docs/auto-harness/runtime-state.md"],
        tests_command="uv run pytest tests/test_quivr_rag.py -v",
        quality_guard_command="uv run python -m quivr_core.auto_harness.run_quality_guard",
        benchmark_command="uv run python -m quivr_core.auto_harness.run_benchmark",
        shadow_command="uv run python -m quivr_core.auto_harness.run_shadow_e2e",
        vsg_command="uv run python -m quivr_core.auto_harness.vsg",
        success_rule="p50 improves and tests stay green",
        reset_rule="reset if any deterministic gate fails",
        novelty_check="direction not repeated in last 5 rounds",
        expected_risk="medium",
        execution_worktree=Path("/tmp/wt-r-20260411-001"),
    )
    manifest = AgentManifest(
        round_id="r-20260411-001",
        agent_id="worker-1",
        role="Worker",
        worktree=Path("/tmp/wt-r-20260411-001"),
        allowed_files=["core/quivr_core/rag/quivr_rag.py"],
        forbidden_actions=["keep", "reset"],
        allowed_commands=["core/scripts/auto_harness/execute_guard.sh worker"],
    )

    assert round_state.round_id == "r-20260411-001"
    assert round_state.execution_worktree == Path("/tmp/wt-r-20260411-001")
    assert manifest.agent_id == "worker-1"
    assert manifest.worktree == Path("/tmp/wt-r-20260411-001")


def test_all_enum_values_are_available():
    assert LoopStatus.DESIGN_ONLY.value == "design_only"
    assert ReviewOutcome.APPROVED.value == "approved"
    assert ShadowStatus.SKIPPED_ENV_MISSING.value == "skipped_env_missing"
    assert Decision.KEEP.value == "keep"


def test_review_result_defaults_to_no_execution_unlock():
    review = ReviewResult(
        round_id="r-20260411-001",
        review_outcome=ReviewOutcome.REVISE,
        scope_check="narrow it",
        verification_check="ok",
        repeat_check="ok",
        reset_check="ok",
        priority_check="ok",
        review_notes=["split hypothesis"],
    )

    assert review.allows_execution is False
    assert review.requires_human is False


def test_recorder_event_requires_payload():
    with pytest.raises(ValidationError):
        RecorderEvent(
            event_id="evt-1",
            round_id="r-20260411-001",
            kind="runtime_transition",
            recorded_at="2026-04-11T10:00:00Z",
        )


def test_reflection_result_requires_lessons():
    with pytest.raises(ValidationError):
        ReflectionResult(
            round_id="r-20260411-001",
            summary="summary",
            replan_recommendation="retry",
        )
