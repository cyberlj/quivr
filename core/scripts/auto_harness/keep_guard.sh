#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
CORE_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
PYTHON_BIN="$CORE_ROOT/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" - <<'PY'
import json
import os
import sys
from pathlib import Path

manifest_path = os.environ.get("AGENT_MANIFEST_PATH")
if not manifest_path:
    print("AGENT_MANIFEST_PATH is required", file=sys.stderr)
    raise SystemExit(1)

manifest_file = Path(manifest_path)
round_root = manifest_file.parent.parent
docs_root = manifest_file.parents[4]
verify_path = round_root / "verify.json"
decision_path = round_root / "decision.json"

if not verify_path.exists():
    print("verify.json missing", file=sys.stderr)
    raise SystemExit(1)
if not decision_path.exists():
    print("decision.json missing", file=sys.stderr)
    raise SystemExit(1)

verify = json.loads(verify_path.read_text(encoding="utf-8"))
decision = json.loads(decision_path.read_text(encoding="utf-8"))

if decision.get("decision") == "keep" and verify.get("shadow_status") == "success":
    event_id = verify.get("api_event_id")
    api_log_path = docs_root / "api-log.jsonl"
    if not event_id or not api_log_path.exists():
        print("shadow success requires a matching api event", file=sys.stderr)
        raise SystemExit(1)

    found = False
    for line in api_log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("event_id") == event_id:
            found = True
            break
    if not found:
        print("shadow success requires a matching api event", file=sys.stderr)
        raise SystemExit(1)

print("keep allowed")
PY
