#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
CORE_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
PYTHON_BIN="$CORE_ROOT/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" - <<'PY'
import os
import sys
from pathlib import Path

manifest_path = os.environ.get("AGENT_MANIFEST_PATH")
if not manifest_path:
    print("AGENT_MANIFEST_PATH is required", file=sys.stderr)
    raise SystemExit(1)

manifest_file = Path(manifest_path)
round_id = manifest_file.stem
round_root = manifest_file.parent.parent
docs_root = manifest_file.parents[4]
reflection_path = round_root / "reflection.json"

if not reflection_path.exists():
    print("reflection.json missing", file=sys.stderr)
    raise SystemExit(1)

archive_root = docs_root / "rounds" / round_root.name
required_files = [
    "plan.md",
    "plan-review.md",
    "verify.md",
    "decision.md",
    "reflection.md",
    "artifacts.json",
    "summary.md",
]
missing = [name for name in required_files if not (archive_root / name).exists()]
if missing:
    print("round archive incomplete", file=sys.stderr)
    raise SystemExit(1)

print("finalize allowed")
PY
