from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from quivr_core.auto_harness.contracts import AgentManifest


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _relative_to_worktree(worktree: Path, changed_file: Path) -> str:
    try:
        return changed_file.relative_to(worktree).as_posix()
    except ValueError as exc:
        raise ValueError(f"changed file is outside worktree: {changed_file}") from exc


def run_worker_runner(changed_files: list[Path], tool_names: list[str]) -> dict:
    round_id = _required_env("ROUND_ID")
    agent_id = _required_env("AGENT_ID")
    manifest_path = Path(_required_env("AGENT_MANIFEST_PATH"))
    worktree = Path(_required_env("WORKTREE_PATH"))

    manifest = AgentManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    if manifest.worktree != worktree:
        raise ValueError("WORKTREE_PATH does not match manifest worktree")

    changed_relative_paths: list[str] = []
    for changed_file in changed_files:
        relative_path = _relative_to_worktree(worktree, changed_file)
        if relative_path == "docs/auto-harness/state/runtime-state.json":
            raise ValueError("worker cannot mutate runtime-state.json")
        if relative_path not in manifest.allowed_files:
            raise ValueError(f"changed file is outside allowed_files: {relative_path}")
        changed_relative_paths.append(relative_path)

    round_root = manifest_path.parent.parent
    change_note = {
        "round_id": round_id,
        "agent_id": agent_id,
        "changed_files": changed_relative_paths,
    }
    tool_usage = {
        "round_id": round_id,
        "agent_id": agent_id,
        "tools": tool_names,
    }

    (round_root / "change_note.json").write_text(
        json.dumps(change_note, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (round_root / "tool_usage.json").write_text(
        json.dumps(tool_usage, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return change_note


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--changed-file", action="append", default=[], type=Path)
    parser.add_argument("--tool-name", action="append", default=[], type=str)
    args = parser.parse_args()

    try:
        run_worker_runner(args.changed_file, args.tool_name)
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        return 1

    print("worker run recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
