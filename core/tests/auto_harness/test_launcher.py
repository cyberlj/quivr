from pathlib import Path

import pytest

from quivr_core.auto_harness.contracts import LoopStatus, RoundState, RuntimeState
from quivr_core.auto_harness.launcher import ExecutionLauncher
from quivr_core.auto_harness.state_store import StateStore


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


def make_round_state() -> RoundState:
    return RoundState(
        round_id="r-20260411-001",
        candidate_id="perf-history-001",
        candidate_family="rag",
        direction="history-trim",
        candidate_class="performance",
        round_type="performance",
        hypothesis="Optimize history-trim in quivr_rag.py.",
        why_now="history-trim is a hotspot",
        allowed_files=["core/quivr_core/rag/quivr_rag.py"],
        forbidden_files=["docs/auto-harness/runtime-state.md"],
        tests_command="uv run pytest tests/test_quivr_rag.py tests/test_chat_history.py -v",
        quality_guard_command="uv run python -m quivr_core.auto_harness.run_quality_guard",
        benchmark_command="uv run python -m quivr_core.auto_harness.run_benchmark",
        shadow_command="uv run python -m quivr_core.auto_harness.run_shadow_e2e",
        vsg_command="uv run python -m quivr_core.auto_harness.vsg",
        success_rule="Keep only if deterministic gates stay green and p50 improves.",
        reset_rule="Reset immediately on failed tests, failed quality guard, or invalid benchmark.",
        novelty_check="Direction must be novel.",
        expected_risk="medium",
        execution_worktree=Path("/tmp/wt-r-20260411-001"),
    )


def test_manifest_paths_differ_by_agent_id(tmp_path):
    store = StateStore(tmp_path / "docs" / "auto-harness")
    launcher = ExecutionLauncher(repo_root=tmp_path, state_store=store)
    round_state = make_round_state()

    worker = launcher.launch_worker(round_state)
    verifier = launcher.launch_verifier(round_state)

    assert worker.manifest_path != verifier.manifest_path
    assert worker.manifest_path.name == "worker-1.json"
    assert verifier.manifest_path.name == "verifier-1.json"


def test_worker_and_verifier_get_different_permissions(tmp_path):
    store = StateStore(tmp_path / "docs" / "auto-harness")
    launcher = ExecutionLauncher(repo_root=tmp_path, state_store=store)
    round_state = make_round_state()

    worker = launcher.launch_worker(round_state)
    verifier = launcher.launch_verifier(round_state)

    assert "edit_code" not in worker.manifest.forbidden_actions
    assert "edit_code" in verifier.manifest.forbidden_actions
    assert worker.environment["AGENT_ROLE"] == "Worker"
    assert verifier.environment["AGENT_ROLE"] == "Verifier"


def test_worker_allowed_commands_resolve_only_to_wrapper_entrypoints(tmp_path):
    store = StateStore(tmp_path / "docs" / "auto-harness")
    launcher = ExecutionLauncher(repo_root=tmp_path, state_store=store)
    round_state = make_round_state()

    worker = launcher.launch_worker(round_state)

    assert worker.manifest.allowed_commands == [
        "core/scripts/auto_harness/execute_guard.sh worker --round-id r-20260411-001 --agent-id worker-1"
    ]


def test_launcher_rejects_direct_unrestricted_module_execution(tmp_path):
    store = StateStore(tmp_path / "docs" / "auto-harness")
    launcher = ExecutionLauncher(repo_root=tmp_path, state_store=store)
    round_state = make_round_state()

    with pytest.raises(ValueError):
        launcher.launch_worker(
            round_state,
            allowed_commands_override=[
                "uv run python -m quivr_core.auto_harness.worker_runner"
            ],
        )


def test_only_one_worker_manifest_per_round(tmp_path):
    store = StateStore(tmp_path / "docs" / "auto-harness")
    launcher = ExecutionLauncher(repo_root=tmp_path, state_store=store)
    round_state = make_round_state()

    launcher.launch_worker(round_state)

    with pytest.raises(ValueError):
        launcher.launch_worker(round_state)


def test_launcher_injects_round_agent_and_worktree_context(tmp_path):
    store = StateStore(tmp_path / "docs" / "auto-harness")
    launcher = ExecutionLauncher(repo_root=tmp_path, state_store=store)
    round_state = make_round_state()

    worker = launcher.launch_worker(round_state)

    assert worker.environment["ROUND_ID"] == "r-20260411-001"
    assert worker.environment["AGENT_ID"] == "worker-1"
    assert worker.environment["WORKTREE_PATH"] == "/tmp/wt-r-20260411-001"
    assert worker.environment["AGENT_MANIFEST_PATH"].endswith("worker-1.json")
