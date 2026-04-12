#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
CORE_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
PYTHON_BIN="$CORE_ROOT/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" - "$@" <<'PY'
import json
import os
import sys
from pathlib import Path

manifest_path = os.environ.get("AGENT_MANIFEST_PATH")
if not manifest_path:
    print("AGENT_MANIFEST_PATH is required", file=sys.stderr)
    raise SystemExit(1)

if len(sys.argv) != 2:
    print("usage: edit_guard.sh <target-file>", file=sys.stderr)
    raise SystemExit(1)

manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
if "edit_code" in manifest.get("forbidden_actions", []):
    print("agent is not allowed to edit code", file=sys.stderr)
    raise SystemExit(1)

target = Path(sys.argv[1]).resolve()
worktree = Path(manifest["worktree"]).resolve()
try:
    relative_path = target.relative_to(worktree).as_posix()
except ValueError:
    print("target file is outside worktree", file=sys.stderr)
    raise SystemExit(1)

if relative_path not in manifest.get("allowed_files", []):
    print(f"target file is outside allowed_files: {relative_path}", file=sys.stderr)
    raise SystemExit(1)

print("edit allowed")
PY
