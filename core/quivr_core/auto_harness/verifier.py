from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


Runner = Callable[[], dict]


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_round(
    round_id: str,
    round_root: str | Path,
    tests_runner: Runner,
    quality_runner: Runner,
    benchmark_runner: Runner,
    shadow_runner: Runner,
) -> dict:
    round_root = Path(round_root)
    round_root.mkdir(parents=True, exist_ok=True)

    tests_result = tests_runner()
    quality_result = quality_runner()
    benchmark_result = benchmark_runner()
    shadow_result = shadow_runner()

    verify_payload = {
        "round_id": round_id,
        "tests_passed": tests_result["tests_passed"],
        "quality_passed": quality_result["passed"],
        "benchmark_status": benchmark_result["status"],
        "benchmark_summary": benchmark_result,
        "shadow_status": shadow_result["shadow_status"],
        "api_event_id": shadow_result.get("api_event_id"),
    }
    benchmark_summary_payload = benchmark_result
    tool_usage_summary_payload = {
        "round_id": round_id,
        "tools": ["run_tests", "run_quality_guard", "run_benchmark", "run_shadow_e2e"],
    }
    api_summary_payload = shadow_result.get("api_summary_payload")

    _write_json(round_root / "verify.json", verify_payload)
    _write_json(round_root / "benchmark_summary.json", benchmark_summary_payload)
    _write_json(round_root / "tool_usage_summary.json", tool_usage_summary_payload)
    _write_json(round_root / "api_summary.json", api_summary_payload or {})

    return {
        "verify": verify_payload,
        "benchmark_summary": benchmark_summary_payload,
        "tool_usage_summary": tool_usage_summary_payload,
        "api_summary": api_summary_payload,
    }
