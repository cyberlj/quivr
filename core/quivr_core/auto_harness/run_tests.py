from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_related_tests(command: str, worktree: str | Path) -> dict:
    effective_command = command
    if command.startswith("python "):
        effective_command = f"{sys.executable} {command[len('python '):]}"

    completed = subprocess.run(
        effective_command,
        cwd=Path(worktree),
        shell=True,
        text=True,
        capture_output=True,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "tests_passed": completed.returncode == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--worktree", required=True, type=Path)
    args = parser.parse_args()
    result = run_related_tests(args.command, args.worktree)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["tests_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
