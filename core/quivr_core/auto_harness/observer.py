from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from quivr_core.auto_harness.contracts import LoopStatus
from quivr_core.auto_harness.render_views import render_observer_summary_markdown
from quivr_core.auto_harness.state_store import StateStore


def refresh_observer_summary(
    docs_root: str | Path,
    recent_window: int = 5,
) -> dict[str, Any]:
    docs_root = Path(docs_root)
    runtime_state = _load_runtime_state(docs_root)
    ledger_rows = _load_ledger_rows(docs_root)
    recent_rows = ledger_rows[-recent_window:]
    keep_count = sum(1 for row in recent_rows if row.get("decision") == "keep")
    reset_count = sum(1 for row in recent_rows if row.get("decision") == "reset")
    keep_reset_ratio = f"{keep_count} keep / {reset_count} reset"
    repeated_failure_class = _repeated_failure_class(recent_rows)
    shadow_health = _shadow_health(docs_root)
    alert_state = _alert_state(runtime_state)
    recommendation = _recommendation(
        repeated_failure_class=repeated_failure_class,
        alert_state=alert_state,
        shadow_health=shadow_health,
    )

    summary = {
        "loop_status": runtime_state.loop_status.value if runtime_state else "unknown",
        "round_id": runtime_state.active_round_id if runtime_state else "none",
        "current_best_commit": runtime_state.current_best_commit if runtime_state else "unknown",
        "keep_reset_ratio": keep_reset_ratio,
        "repeated_failure_class": repeated_failure_class,
        "alert_state": alert_state,
        "shadow_health": shadow_health,
        "recommendation": recommendation,
    }
    lines = [
        f"- `loop_status`: `{summary['loop_status']}`",
        f"- `round_id`: `{summary['round_id']}`",
        f"- `current_best_commit`: `{summary['current_best_commit']}`",
        f"- `keep_reset_ratio`: `{summary['keep_reset_ratio']}`",
        f"- `repeated_failure_class`: `{summary['repeated_failure_class']}`",
        f"- `alert_state`: `{summary['alert_state']}`",
        f"- `shadow_health`: `{summary['shadow_health']}`",
        f"- `recommendation`: `{summary['recommendation']}`",
    ]
    (docs_root / "observer-summary.md").write_text(
        render_observer_summary_markdown(lines) + "\n",
        encoding="utf-8",
    )
    return summary


def _load_runtime_state(docs_root: Path):
    path = docs_root / "state" / "runtime-state.json"
    if not path.exists():
        return None
    return StateStore(docs_root).load_runtime_state()


def _load_ledger_rows(docs_root: Path) -> list[dict[str, str]]:
    path = docs_root / "experiment-ledger.tsv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [row for row in reader if any((value or "").strip() for value in row.values())]


def _repeated_failure_class(rows: list[dict[str, str]]) -> str:
    reset_rows = [row for row in rows if row.get("decision") == "reset"]
    if len(reset_rows) < 2:
        return "none"
    latest_class = reset_rows[-1].get("failure_class", "").strip()
    if not latest_class:
        return "none"
    trailing_same = 0
    for row in reversed(reset_rows):
        if row.get("failure_class", "").strip() == latest_class:
            trailing_same += 1
            continue
        break
    return latest_class if trailing_same >= 2 else "none"


def _shadow_health(docs_root: Path) -> str:
    verify_paths = sorted((docs_root / "state" / "rounds").glob("*/verify.json"))
    if not verify_paths:
        return "unknown"
    payload = json.loads(verify_paths[-1].read_text(encoding="utf-8"))
    shadow_status = payload.get("shadow_status", "unknown")
    if shadow_status == "success":
        return "healthy"
    if shadow_status == "failure":
        return "degraded (latest=failure)"
    return str(shadow_status)


def _alert_state(runtime_state) -> str:
    if runtime_state is None:
        return "none"
    if runtime_state.loop_status == LoopStatus.CANDIDATE_POOL_EMPTY:
        return LoopStatus.CANDIDATE_POOL_EMPTY.value
    if runtime_state.loop_status == LoopStatus.AWAIT_HUMAN:
        return LoopStatus.AWAIT_HUMAN.value
    return "none"


def _recommendation(
    repeated_failure_class: str,
    alert_state: str,
    shadow_health: str,
) -> str:
    if alert_state in {LoopStatus.CANDIDATE_POOL_EMPTY.value, LoopStatus.AWAIT_HUMAN.value}:
        return "intervene"
    if repeated_failure_class != "none":
        return "intervene"
    if shadow_health.startswith("degraded"):
        return "watch"
    return "continue"
