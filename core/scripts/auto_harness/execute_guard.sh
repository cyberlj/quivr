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

manifest_file = Path(manifest_path)
manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
round_root = manifest_file.parent.parent
review_path = round_root / "review.json"

if not review_path.exists():
    print("review.json missing", file=sys.stderr)
    raise SystemExit(1)

review = json.loads(review_path.read_text(encoding="utf-8"))
if review.get("review_outcome") != "approved":
    print("review_outcome must be approved", file=sys.stderr)
    raise SystemExit(1)

invoked = "core/scripts/auto_harness/execute_guard.sh"
if len(sys.argv) > 1:
    invoked = f"{invoked} {' '.join(sys.argv[1:])}"

if invoked not in manifest.get("allowed_commands", []):
    print("command is not allowed by manifest", file=sys.stderr)
    raise SystemExit(1)

print("execution allowed")
PY
