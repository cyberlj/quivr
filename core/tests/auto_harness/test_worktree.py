from pathlib import Path

import pytest

from quivr_core.auto_harness.worktree import WorktreeManager


def test_unique_round_id_maps_to_unique_worktree_path(tmp_path):
    manager = WorktreeManager(repo_root=tmp_path)

    first = manager.path_for_round("r-20260411-001")
    second = manager.path_for_round("r-20260411-002")

    assert first == tmp_path / ".worktrees" / "wt-r-20260411-001"
    assert second == tmp_path / ".worktrees" / "wt-r-20260411-002"
    assert first != second


def test_create_round_worktree_from_current_best_commit(tmp_path):
    calls: list[list[str]] = []

    def fake_runner(cmd: list[str], cwd: Path) -> None:
        calls.append(cmd)
        (tmp_path / ".worktrees" / "wt-r-20260411-001").mkdir(parents=True, exist_ok=True)

    manager = WorktreeManager(repo_root=tmp_path, runner=fake_runner)

    created = manager.create_round_worktree("r-20260411-001", "abc123")

    assert created.exists()
    assert calls == [
        [
            "git",
            "worktree",
            "add",
            str(tmp_path / ".worktrees" / "wt-r-20260411-001"),
            "abc123",
        ]
    ]


def test_worktree_cleanup_removes_only_round_worktree(tmp_path):
    removed: list[list[str]] = []

    def fake_runner(cmd: list[str], cwd: Path) -> None:
        removed.append(cmd)

    manager = WorktreeManager(repo_root=tmp_path, runner=fake_runner)
    target = tmp_path / ".worktrees" / "wt-r-20260411-001"
    other = tmp_path / ".worktrees" / "wt-r-20260411-002"
    target.mkdir(parents=True)
    other.mkdir(parents=True)

    manager.remove_round_worktree("r-20260411-001")

    assert not target.exists()
    assert other.exists()
    assert removed == [
        ["git", "worktree", "remove", str(target), "--force"]
    ]


def test_verify_worktree_path_exists(tmp_path):
    manager = WorktreeManager(repo_root=tmp_path)
    path = tmp_path / ".worktrees" / "wt-r-20260411-001"
    path.mkdir(parents=True)

    assert manager.ensure_worktree_exists(path) == path

    with pytest.raises(FileNotFoundError):
        manager.ensure_worktree_exists(tmp_path / ".worktrees" / "wt-r-20260411-404")
