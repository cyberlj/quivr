from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


def integrate_keep_from_worktree(
    round_state,
    start_commit: str,
    proposed_end_commit: str,
) -> dict[str, Any]:
    worktree = Path(round_state.execution_worktree)
    ref_name = f"refs/auto-harness/keeps/{round_state.round_id}"
    allowed_files = list(round_state.allowed_files)

    if not allowed_files:
        return _dry_run_safe_result(start_commit)

    try:
        _git(
            ["git", "add", "--", *allowed_files],
            cwd=worktree,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return _dry_run_safe_result(start_commit)

    cached_diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", *allowed_files],
        cwd=worktree,
        env=_git_env(),
        check=False,
        capture_output=True,
        text=True,
    )
    if cached_diff.returncode == 0:
        return _dry_run_safe_result(start_commit)
    if cached_diff.returncode != 1:
        raise subprocess.CalledProcessError(
            cached_diff.returncode,
            cached_diff.args,
            output=cached_diff.stdout,
            stderr=cached_diff.stderr,
        )

    commit_message = f"auto-harness keep {round_state.round_id}"
    _git(
        ["git", "commit", "-m", commit_message],
        cwd=worktree,
    )
    end_commit_full = _git_output(["git", "rev-parse", "HEAD"], cwd=worktree)
    end_commit_short = _git_output(["git", "rev-parse", "--short", "HEAD"], cwd=worktree)
    _git(
        ["git", "update-ref", ref_name, end_commit_full],
        cwd=worktree,
    )
    return {
        "end_commit": end_commit_short,
        "end_commit_full": end_commit_full,
        "integrated": True,
        "keep_ref": ref_name,
        "summary": (
            f"real keep integration committed allowed_files and pinned {ref_name} to {end_commit_short}; "
            f"proposed_end_commit={proposed_end_commit}"
        ),
    }


def _dry_run_safe_result(start_commit: str) -> dict[str, Any]:
    return {
        "end_commit": start_commit,
        "end_commit_full": start_commit,
        "integrated": False,
        "keep_ref": None,
        "summary": "keep accepted under dry-run-safe policy; real baseline integration is still pending",
    }


def _git(cmd: list[str], cwd: Path) -> None:
    subprocess.run(
        cmd,
        cwd=cwd,
        env=_git_env(),
        check=True,
        text=True,
        capture_output=True,
    )


def _git_output(cmd: list[str], cwd: Path) -> str:
    return subprocess.check_output(cmd, cwd=cwd, env=_git_env(), text=True).strip()


def _git_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("GIT_AUTHOR_NAME", "auto-harness")
    env.setdefault("GIT_AUTHOR_EMAIL", "auto-harness@example.invalid")
    env.setdefault("GIT_COMMITTER_NAME", env["GIT_AUTHOR_NAME"])
    env.setdefault("GIT_COMMITTER_EMAIL", env["GIT_AUTHOR_EMAIL"])
    return env
