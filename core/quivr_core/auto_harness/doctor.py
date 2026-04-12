from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from quivr_core.auto_harness.candidate_service import CandidateService
from quivr_core.auto_harness.state_store import StateStore


def inspect_runtime(docs_root: Path) -> dict:
    store = StateStore(docs_root)
    runtime_state = store.load_runtime_state()
    candidate_service = CandidateService(docs_root / "candidate-registry.tsv")
    candidates = candidate_service.load_candidates()
    selectable = [
        candidate
        for candidate in candidates
        if candidate.status in {"new", "ready", "reset"} and candidate.do_not_repeat == "none"
    ]
    readiness_issues: list[str] = []
    if not os.environ.get("OPENAI_API_KEY"):
        readiness_issues.append("OPENAI_API_KEY")

    recommended_next_command = (
        "uv run python -m quivr_core.auto_harness.controller --once"
        if not readiness_issues
        else "set required provider environment variables before controller --once"
    )

    return {
        "loop_status": runtime_state.loop_status.value,
        "active_round": runtime_state.active_round_id,
        "current_best_commit": runtime_state.current_best_commit,
        "candidate_pool_summary": {
            "total": len(candidates),
            "selectable": len(selectable),
        },
        "readiness_issues": readiness_issues,
        "recommended_next_command": recommended_next_command,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "docs" / "auto-harness",
    )
    args = parser.parse_args()

    print(json.dumps(inspect_runtime(args.docs_root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
