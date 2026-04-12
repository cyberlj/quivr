import json
import os
import subprocess
from pathlib import Path

from quivr_core.auto_harness.contracts import Decision, DecisionResult, ReflectionResult, ReviewOutcome, ReviewResult, ShadowStatus, VerifyResult
from quivr_core.auto_harness.launcher import ExecutionLauncher
from quivr_core.auto_harness.state_store import StateStore

from tests.auto_harness.test_launcher import make_round_state


def run_script(script_path: Path, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script_path), *args],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        text=True,
        capture_output=True,
    )


def setup_round(tmp_path: Path):
    docs_root = tmp_path / "docs" / "auto-harness"
    worktree = tmp_path / "wt-r-20260411-001"
    worktree.mkdir(parents=True)
    round_state = make_round_state().model_copy(update={"execution_worktree": worktree})
    store = StateStore(docs_root)
    launcher = ExecutionLauncher(repo_root=tmp_path, state_store=store)
    launch = launcher.launch_worker(round_state)
    env = dict(os.environ)
    env["AGENT_MANIFEST_PATH"] = str(launch.manifest_path)
    return store, round_state, launch, env


def test_edit_guard_blocks_changes_outside_allowed_files(tmp_path):
    _, round_state, launch, env = setup_round(tmp_path)
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "auto_harness" / "edit_guard.sh"
    forbidden = round_state.execution_worktree / "core" / "quivr_core" / "rag" / "other.py"
    forbidden.parent.mkdir(parents=True, exist_ok=True)
    forbidden.write_text("x = 1\n", encoding="utf-8")

    result = run_script(script_path, str(forbidden), env=env)

    assert result.returncode != 0
    assert "outside allowed_files" in result.stderr
    assert launch.manifest_path.exists()


def test_execute_guard_blocks_when_review_missing(tmp_path):
    _, round_state, _, env = setup_round(tmp_path)
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "auto_harness" / "execute_guard.sh"

    result = run_script(
        script_path,
        "worker",
        "--round-id",
        round_state.round_id,
        "--agent-id",
        "worker-1",
        env=env,
    )

    assert result.returncode != 0
    assert "review.json missing" in result.stderr


def test_execute_guard_blocks_when_review_not_approved(tmp_path):
    store, round_state, _, env = setup_round(tmp_path)
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "auto_harness" / "execute_guard.sh"
    store.write_review_result(
        ReviewResult(
            round_id=round_state.round_id,
            review_outcome=ReviewOutcome.REVISE,
            allows_execution=False,
            requires_human=False,
            scope_check="split_hypothesis",
            verification_check="complete",
            repeat_check="novel",
            reset_check="present",
            priority_check="candidate_valid",
            review_notes=["split it"],
        )
    )

    result = run_script(
        script_path,
        "worker",
        "--round-id",
        round_state.round_id,
        "--agent-id",
        "worker-1",
        env=env,
    )

    assert result.returncode != 0
    assert "review_outcome must be approved" in result.stderr


def test_execute_guard_blocks_when_command_not_in_manifest(tmp_path):
    store, round_state, _, env = setup_round(tmp_path)
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "auto_harness" / "execute_guard.sh"
    store.write_review_result(
        ReviewResult(
            round_id=round_state.round_id,
            review_outcome=ReviewOutcome.APPROVED,
            allows_execution=True,
            requires_human=False,
            scope_check="bounded",
            verification_check="complete",
            repeat_check="novel",
            reset_check="present",
            priority_check="candidate_valid",
            review_notes=["approved"],
        )
    )

    result = run_script(
        script_path,
        "verifier",
        "--round-id",
        round_state.round_id,
        "--agent-id",
        "verifier-1",
        env=env,
    )

    assert result.returncode != 0
    assert "command is not allowed" in result.stderr


def test_keep_guard_blocks_when_verify_or_decision_missing(tmp_path):
    _, _, _, env = setup_round(tmp_path)
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "auto_harness" / "keep_guard.sh"

    result = run_script(script_path, env=env)

    assert result.returncode != 0
    assert "verify.json missing" in result.stderr


def test_keep_guard_blocks_shadow_success_without_matching_api_event(tmp_path):
    store, round_state, _, env = setup_round(tmp_path)
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "auto_harness" / "keep_guard.sh"
    store.write_verify_result(
        VerifyResult(
            round_id=round_state.round_id,
            tests_passed=True,
            quality_passed=True,
            benchmark_status="valid",
            shadow_status=ShadowStatus.SUCCESS,
            benchmark_gain_pct=0.2,
            api_event_id=None,
        )
    )
    store.write_decision_result(
        DecisionResult(
            round_id=round_state.round_id,
            decision=Decision.KEEP,
            summary="keep",
        )
    )

    result = run_script(script_path, env=env)

    assert result.returncode != 0
    assert "shadow success requires a matching api event" in result.stderr


def test_finalize_guard_blocks_when_reflection_missing(tmp_path):
    _, _, _, env = setup_round(tmp_path)
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "auto_harness" / "finalize_guard.sh"

    result = run_script(script_path, env=env)

    assert result.returncode != 0
    assert "reflection.json missing" in result.stderr


def test_finalize_guard_blocks_when_archive_incomplete(tmp_path):
    store, round_state, _, env = setup_round(tmp_path)
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "auto_harness" / "finalize_guard.sh"
    store.write_reflection_result(
        ReflectionResult(
            round_id=round_state.round_id,
            summary="summary",
            replan_recommendation="next",
            lessons=["lesson"],
        )
    )
    archive_root = tmp_path / "docs" / "auto-harness" / "rounds" / round_state.round_id
    archive_root.mkdir(parents=True, exist_ok=True)
    (archive_root / "plan.md").write_text("# Plan\n", encoding="utf-8")

    result = run_script(script_path, env=env)

    assert result.returncode != 0
    assert "round archive incomplete" in result.stderr
