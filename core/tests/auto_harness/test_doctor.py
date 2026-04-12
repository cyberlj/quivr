import json
import os
import subprocess
from pathlib import Path

from quivr_core.auto_harness.contracts import LoopStatus, RuntimeState
from quivr_core.auto_harness.state_store import StateStore


HEADER = (
    "candidate_id\tcandidate_family\tdirection\tcandidate_class\tsource\t"
    "target_path\tevidence\tverification\tstatus\tlast_result\tdo_not_repeat\tnotes\n"
)


def write_registry(path: Path, rows: list[str]) -> None:
    path.write_text(HEADER + "".join(rows), encoding="utf-8")


def runtime_state() -> RuntimeState:
    return RuntimeState(
        loop_status=LoopStatus.EXECUTING,
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


def run_doctor(docs_root: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    return subprocess.run(
        [
            str(Path(__file__).resolve().parents[2] / ".venv" / "bin" / "python"),
            "-m",
            "quivr_core.auto_harness.doctor",
            "--docs-root",
            str(docs_root),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=merged_env,
        text=True,
        capture_output=True,
    )


def test_missing_provider_env_is_surfaced_as_readiness_issue(tmp_path):
    docs_root = tmp_path / "docs" / "auto-harness"
    store = StateStore(docs_root)
    store.write_runtime_state(runtime_state())
    write_registry(docs_root / "candidate-registry.tsv", [])

    result = run_doctor(docs_root, env={"OPENAI_API_KEY": ""})

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "OPENAI_API_KEY" in payload["readiness_issues"]


def test_active_round_is_reported_from_runtime_state(tmp_path):
    docs_root = tmp_path / "docs" / "auto-harness"
    store = StateStore(docs_root)
    store.write_runtime_state(runtime_state())
    write_registry(
        docs_root / "candidate-registry.tsv",
        [
            "perf-history-001\trag\thistory-trim\tperformance\treview-findings\tcore/quivr_core/rag/quivr_rag.py\tevidence\tverify\tready\tnone\tnone\tnote\n"
        ],
    )

    result = run_doctor(docs_root, env={"OPENAI_API_KEY": "test-key"})

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["loop_status"] == "executing"
    assert payload["active_round"] == "r-20260411-001"
    assert payload["current_best_commit"] == "abc123"
    assert payload["candidate_pool_summary"]["selectable"] == 1


def test_doctor_is_read_only(tmp_path):
    docs_root = tmp_path / "docs" / "auto-harness"
    store = StateStore(docs_root)
    store.write_runtime_state(runtime_state())
    registry_path = docs_root / "candidate-registry.tsv"
    write_registry(registry_path, [])
    before = {
        "runtime": store.runtime_state_path().read_text(encoding="utf-8"),
        "registry": registry_path.read_text(encoding="utf-8"),
    }

    result = run_doctor(docs_root, env={"OPENAI_API_KEY": "test-key"})

    assert result.returncode == 0
    after = {
        "runtime": store.runtime_state_path().read_text(encoding="utf-8"),
        "registry": registry_path.read_text(encoding="utf-8"),
    }
    assert before == after
