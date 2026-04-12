from __future__ import annotations


def evaluate_vsg(
    baseline_full_session_p50_ms: float,
    verify_payload: dict,
    baseline_session_p90_ms: float | None = None,
) -> dict:
    tests_passed = verify_payload["tests_passed"]
    quality_passed = verify_payload["quality_passed"]
    benchmark_status = verify_payload["benchmark_status"]
    benchmark_summary = verify_payload["benchmark_summary"]
    shadow_status = verify_payload["shadow_status"]

    if not tests_passed or not quality_passed or benchmark_status != "valid":
        return {
            "gate": 0,
            "gain": 0.0,
            "decision": "reset",
            "compatibility_confirmed": shadow_status == "success",
        }

    new_p50 = benchmark_summary["full_session_p50_ms"]
    gain = (baseline_full_session_p50_ms - new_p50) / baseline_full_session_p50_ms
    p90 = benchmark_summary["session_p90_ms"]

    if gain <= 0:
        return {
            "gate": 1,
            "gain": gain,
            "decision": "reset",
            "compatibility_confirmed": shadow_status == "success",
        }

    if (
        baseline_session_p90_ms is not None
        and p90 > baseline_session_p90_ms * 1.15
    ):
        return {
            "gate": 1,
            "gain": gain,
            "decision": "needs_review",
            "compatibility_confirmed": shadow_status == "success",
        }

    if shadow_status == "failure":
        return {
            "gate": 1,
            "gain": gain,
            "decision": "needs_review",
            "compatibility_confirmed": False,
        }

    return {
        "gate": 1,
        "gain": gain,
        "decision": "keep",
        "compatibility_confirmed": shadow_status == "success",
    }
