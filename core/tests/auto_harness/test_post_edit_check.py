import os
import subprocess
from pathlib import Path

from quivr_core.auto_harness.contracts import AgentManifest
from quivr_core.auto_harness.state_store import StateStore

from tests.auto_harness.test_launcher import make_round_state


def run_post_edit_check(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    return subprocess.run(
        [
            str(Path(__file__).resolve().parents[2] / ".venv" / "bin" / "python"),
            "-m",
            "quivr_core.auto_harness.post_edit_check",
            *args,
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=merged_env,
        text=True,
        capture_output=True,
    )


def setup_post_edit(tmp_path: Path):
    docs_root = tmp_path / "docs" / "auto-harness"
    worktree = tmp_path / "wt-r-20260411-001"
    target = worktree / "sandbox" / "module_ok.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("value = 1\n", encoding="utf-8")
    store = StateStore(docs_root)
    round_state = make_round_state().model_copy(
        update={
            "execution_worktree": worktree,
            "allowed_files": ["sandbox/module_ok.py"],
        }
    )
    store.write_round_state(round_state)
    manifest = AgentManifest(
        round_id=round_state.round_id,
        agent_id="worker-1",
        role="Worker",
        worktree=worktree,
        allowed_files=["sandbox/module_ok.py"],
        forbidden_actions=["keep", "reset", "edit_runtime_state"],
        allowed_commands=["core/scripts/auto_harness/execute_guard.sh worker --round-id r-20260411-001 --agent-id worker-1"],
    )
    manifest_path = store.write_agent_manifest(manifest)
    round_state_path = store.round_state_path(round_state.round_id)
    return manifest_path, round_state_path, target, worktree


def test_post_edit_failure_blocks_verifier_handoff(tmp_path):
    manifest_path, round_state_path, target, _ = setup_post_edit(tmp_path)
    target.write_text("def broken(:\n", encoding="utf-8")

    result = run_post_edit_check(
        "--manifest-path",
        str(manifest_path),
        "--round-state-path",
        str(round_state_path),
        "--changed-file",
        str(target),
    )

    assert result.returncode != 0
    assert "py_compile failed" in result.stderr


def test_post_edit_check_fails_fast_for_changes_outside_allowed_files(tmp_path):
    manifest_path, round_state_path, _, worktree = setup_post_edit(tmp_path)
    outside = worktree / "sandbox" / "module_bad.py"
    outside.write_text("value = 2\n", encoding="utf-8")

    result = run_post_edit_check(
        "--manifest-path",
        str(manifest_path),
        "--round-state-path",
        str(round_state_path),
        "--changed-file",
        str(outside),
    )

    assert result.returncode != 0
    assert "outside allowed_files" in result.stderr


def test_post_edit_check_passes_for_valid_changes(tmp_path):
    manifest_path, round_state_path, target, _ = setup_post_edit(tmp_path)

    result = run_post_edit_check(
        "--manifest-path",
        str(manifest_path),
        "--round-state-path",
        str(round_state_path),
        "--changed-file",
        str(target),
    )

    assert result.returncode == 0
    assert "post-edit checks passed" in result.stdout
