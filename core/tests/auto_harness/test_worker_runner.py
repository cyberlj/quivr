import json
import os
import subprocess
from pathlib import Path

from quivr_core.auto_harness.contracts import AgentManifest
from quivr_core.auto_harness.state_store import StateStore


def run_worker_runner(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    merged_env = dict(os.environ)
    merged_env.update(env)
    return subprocess.run(
        [
            str(Path(__file__).resolve().parents[2] / ".venv" / "bin" / "python"),
            "-m",
            "quivr_core.auto_harness.worker_runner",
            *args,
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=merged_env,
        text=True,
        capture_output=True,
    )


def setup_worker(tmp_path: Path):
    docs_root = tmp_path / "docs" / "auto-harness"
    worktree = tmp_path / "wt-r-20260411-001"
    allowed = worktree / "core" / "quivr_core" / "rag" / "quivr_rag.py"
    allowed.parent.mkdir(parents=True, exist_ok=True)
    allowed.write_text("value = 1\n", encoding="utf-8")
    store = StateStore(docs_root)
    manifest = AgentManifest(
        round_id="r-20260411-001",
        agent_id="worker-1",
        role="Worker",
        worktree=worktree,
        allowed_files=["core/quivr_core/rag/quivr_rag.py"],
        forbidden_actions=["keep", "reset", "edit_runtime_state"],
        allowed_commands=["core/scripts/auto_harness/execute_guard.sh worker --round-id r-20260411-001 --agent-id worker-1"],
    )
    manifest_path = store.write_agent_manifest(manifest)
    env = {
        "ROUND_ID": "r-20260411-001",
        "AGENT_ID": "worker-1",
        "AGENT_MANIFEST_PATH": str(manifest_path),
        "WORKTREE_PATH": str(worktree),
    }
    return store, env, allowed, worktree


def test_missing_manifest_fails_fast(tmp_path):
    _, env, allowed, _ = setup_worker(tmp_path)
    env.pop("AGENT_MANIFEST_PATH")

    result = run_worker_runner(env, "--changed-file", str(allowed))

    assert result.returncode != 0
    assert "AGENT_MANIFEST_PATH is required" in result.stderr


def test_edit_outside_allowed_files_is_rejected(tmp_path):
    _, env, _, worktree = setup_worker(tmp_path)
    outside = worktree / "core" / "quivr_core" / "rag" / "other.py"
    outside.write_text("value = 2\n", encoding="utf-8")

    result = run_worker_runner(env, "--changed-file", str(outside))

    assert result.returncode != 0
    assert "outside allowed_files" in result.stderr


def test_successful_run_writes_change_note_json(tmp_path):
    store, env, allowed, _ = setup_worker(tmp_path)

    result = run_worker_runner(
        env,
        "--changed-file",
        str(allowed),
        "--tool-name",
        "apply_patch",
    )

    assert result.returncode == 0
    change_note_path = store._round_root("r-20260411-001") / "change_note.json"
    assert change_note_path.exists()
    payload = json.loads(change_note_path.read_text(encoding="utf-8"))
    assert payload["round_id"] == "r-20260411-001"
    assert payload["agent_id"] == "worker-1"
    assert payload["changed_files"] == ["core/quivr_core/rag/quivr_rag.py"]


def test_worker_cannot_write_runtime_state_json(tmp_path):
    _, env, _, worktree = setup_worker(tmp_path)
    forbidden = worktree / "docs" / "auto-harness" / "state" / "runtime-state.json"
    forbidden.parent.mkdir(parents=True, exist_ok=True)
    forbidden.write_text("{}\n", encoding="utf-8")

    result = run_worker_runner(env, "--changed-file", str(forbidden))

    assert result.returncode != 0
    assert "worker cannot mutate runtime-state.json" in result.stderr
