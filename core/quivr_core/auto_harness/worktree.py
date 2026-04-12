from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable


Runner = Callable[[list[str], Path], None]


def _default_runner(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


class WorktreeManager:
    def __init__(
        self,
        repo_root: str | Path,
        runner: Runner | None = None,
    ):
        self.repo_root = Path(repo_root)
        self.worktree_root = self.repo_root / ".worktrees"
        self.runner = runner or _default_runner

    def path_for_round(self, round_id: str) -> Path:
        return self.worktree_root / f"wt-{round_id}"

    def create_round_worktree(self, round_id: str, current_best_commit: str) -> Path:
        path = self.path_for_round(round_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.runner(
            ["git", "worktree", "add", str(path), current_best_commit],
            self.repo_root,
        )
        return self.ensure_worktree_exists(path)

    def remove_round_worktree(self, round_id: str) -> Path:
        path = self.path_for_round(round_id)
        if not path.exists():
            return path

        self.runner(
            ["git", "worktree", "remove", str(path), "--force"],
            self.repo_root,
        )
        if path.exists():
            shutil.rmtree(path)
        return path

    def ensure_worktree_exists(self, worktree_path: str | Path) -> Path:
        path = Path(worktree_path)
        if not path.exists():
            raise FileNotFoundError(f"worktree path does not exist: {path}")
        return path
