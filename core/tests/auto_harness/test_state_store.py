import json
from pathlib import Path

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
from quivr_core.auto_harness.state_store import StateStore


def make_runtime_state() -> RuntimeState:
    return RuntimeState(
        loop_status=LoopStatus.PLANNING,
        current_best_commit="abc123",
        current_best_round_id="r-20260410-001",
        current_best_candidate_id="perf-history-001",
        control_branch="quivr-auto-harness",
        control_worktree=Path("/tmp/control"),
        active_round_id="r-20260411-001",
        active_execution_worktree=Path("/tmp/wt-r-20260411-001"),
        human_wait_reason="none",
        last_updated="2026-04-11T10:00:00Z",
    )


def make_round_state() -> RoundState:
    return RoundState(
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


def make_agent_manifest() -> AgentManifest:
    return AgentManifest(
        round_id="r-20260411-001",
        agent_id="worker-1",
        role="Worker",
        worktree=Path("/tmp/wt-r-20260411-001"),
        allowed_files=["core/quivr_core/rag/quivr_rag.py"],
        forbidden_actions=["keep", "reset", "edit_runtime_state"],
        allowed_commands=["core/scripts/auto_harness/execute_guard.sh worker"],
    )


def make_review() -> ReviewResult:
    return ReviewResult(
        round_id="r-20260411-001",
        review_outcome=ReviewOutcome.APPROVED,
        allows_execution=True,
        scope_check="ok",
        verification_check="ok",
        repeat_check="ok",
        reset_check="ok",
        priority_check="ok",
        review_notes=["bounded scope"],
    )


def make_verify() -> VerifyResult:
    return VerifyResult(
        round_id="r-20260411-001",
        tests_passed=True,
        quality_passed=True,
        benchmark_status="valid",
        shadow_status=ShadowStatus.SKIPPED_ENV_MISSING,
        benchmark_gain_pct=1.25,
        api_event_id=None,
    )


def make_decision() -> DecisionResult:
    return DecisionResult(
        round_id="r-20260411-001",
        decision=Decision.KEEP,
        summary="keep the candidate",
    )


def make_reflection() -> ReflectionResult:
    return ReflectionResult(
        round_id="r-20260411-001",
        summary="history trim improved p50",
        replan_recommendation="try a larger benchmark next",
        lessons=["keep hypothesis narrow"],
    )


def make_event() -> RecorderEvent:
    return RecorderEvent(
        event_id="evt-001",
        round_id="r-20260411-001",
        kind="runtime_transition",
        payload={"from": "planning", "to": "plan_review"},
        recorded_at="2026-04-11T10:00:00Z",
    )


def test_state_store_round_trips_models(tmp_path):
    store = StateStore(tmp_path / "docs" / "auto-harness")

    runtime_state = make_runtime_state()
    round_state = make_round_state()
    manifest = make_agent_manifest()
    review = make_review()
    verify = make_verify()
    decision = make_decision()
    reflection = make_reflection()

    store.write_runtime_state(runtime_state)
    store.write_round_state(round_state)
    store.write_agent_manifest(manifest)
    store.write_review_result(review)
    store.write_verify_result(verify)
    store.write_decision_result(decision)
    store.write_reflection_result(reflection)

    assert store.load_runtime_state() == runtime_state
    assert store.load_round_state(round_state.round_id) == round_state
    assert store.load_agent_manifest(round_state.round_id, manifest.agent_id) == manifest
    assert store.load_review_result(round_state.round_id) == review
    assert store.load_verify_result(round_state.round_id) == verify
    assert store.load_decision_result(round_state.round_id) == decision
    assert store.load_reflection_result(round_state.round_id) == reflection


def test_state_store_preserves_timestamp_and_path_fields(tmp_path):
    store = StateStore(tmp_path / "docs" / "auto-harness")
    runtime_state = make_runtime_state()

    store.write_runtime_state(runtime_state)

    loaded = store.load_runtime_state()
    assert loaded.last_updated == "2026-04-11T10:00:00Z"
    assert loaded.control_worktree == Path("/tmp/control")
    assert loaded.active_execution_worktree == Path("/tmp/wt-r-20260411-001")


def test_state_store_appends_recorder_events_as_jsonl(tmp_path):
    store = StateStore(tmp_path / "docs" / "auto-harness")
    first_event = make_event()
    second_event = first_event.model_copy(update={"event_id": "evt-002"})

    store.append_recorder_event(first_event)
    store.append_recorder_event(second_event)

    log_path = tmp_path / "docs" / "auto-harness" / "state" / "recorder-events.jsonl"
    lines = log_path.read_text().splitlines()

    assert len(lines) == 2
    assert json.loads(lines[0])["event_id"] == "evt-001"
    assert json.loads(lines[1])["event_id"] == "evt-002"


def test_state_store_atomic_write_does_not_leave_temp_files(tmp_path):
    store = StateStore(tmp_path / "docs" / "auto-harness")

    store.write_runtime_state(make_runtime_state())

    temp_files = list((tmp_path / "docs" / "auto-harness" / "state").glob("*.tmp"))
    assert temp_files == []
