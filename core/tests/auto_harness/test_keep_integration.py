import subprocess
from pathlib import Path

from quivr_core.auto_harness.contracts import RoundState
from quivr_core.auto_harness.keep_integration import integrate_keep_from_worktree


def git(cmd: list[str], cwd: Path) -> str:
    return subprocess.check_output(cmd, cwd=cwd, text=True).strip()


def make_round_state(round_id: str, worktree: Path) -> RoundState:
    return RoundState(
        round_id=round_id,
        candidate_id="perf-history-001",
        candidate_family="rag",
        direction="history-trim",
        candidate_class="performance",
        round_type="performance",
        hypothesis="Optimize history trim.",
        why_now="Bootstrap candidate.",
        allowed_files=["core/quivr_core/rag/quivr_rag.py"],
        forbidden_files=[],
        tests_command="python -m pytest tests/test_quivr_rag.py -v",
        quality_guard_command="python -m quivr_core.auto_harness.run_quality_guard",
        benchmark_command="python -m quivr_core.auto_harness.run_benchmark",
        shadow_command="python -m quivr_core.auto_harness.run_shadow_e2e",
        vsg_command="python -m quivr_core.auto_harness.vsg",
        success_rule="keep on gain",
        reset_rule="reset on gate failure",
        novelty_check="novel",
        expected_risk="medium",
        execution_worktree=worktree,
    )


def setup_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True, text=True)
    source_file = repo / "core" / "quivr_core" / "rag" / "quivr_rag.py"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True, text=True)
    base_commit = git(["git", "rev-parse", "--short", "HEAD"], repo)

    worktree = tmp_path / "wt-round"
    subprocess.run(
        ["git", "worktree", "add", str(worktree), base_commit],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return repo, worktree, base_commit


def test_keep_integration_creates_real_commit_and_pins_keep_ref(tmp_path):
    repo, worktree, base_commit = setup_repo(tmp_path)
    round_state = make_round_state("r-20260412-001", worktree)

    target_file = worktree / "core" / "quivr_core" / "rag" / "quivr_rag.py"
    target_file.write_text("value = 2\n", encoding="utf-8")

    result = integrate_keep_from_worktree(
        round_state=round_state,
        start_commit=base_commit,
        proposed_end_commit="simulated-end-commit",
    )

    ref_commit = git(["git", "rev-parse", result["keep_ref"]], repo)

    assert result["integrated"] is True
    assert result["end_commit"] != base_commit
    assert ref_commit == result["end_commit_full"]


def test_keep_integration_falls_back_to_dry_run_safe_when_allowed_files_do_not_change(tmp_path):
    _, worktree, base_commit = setup_repo(tmp_path)
    round_state = make_round_state("r-20260412-002", worktree)

    result = integrate_keep_from_worktree(
        round_state=round_state,
        start_commit=base_commit,
        proposed_end_commit="simulated-end-commit",
    )

    assert result["integrated"] is False
    assert result["end_commit"] == base_commit
    assert result["keep_ref"] is None
