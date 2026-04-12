import json
from pathlib import Path

from quivr_core.auto_harness.verifier import verify_round
from quivr_core.auto_harness.vsg import evaluate_vsg


def test_verifier_emits_structured_handoffs_only(tmp_path):
    round_root = tmp_path / "rounds" / "r-20260411-001"
    round_root.mkdir(parents=True)

    result = verify_round(
        round_id="r-20260411-001",
        round_root=round_root,
        tests_runner=lambda: {
            "tests_passed": True,
            "returncode": 0,
            "stdout": "ok",
            "stderr": "",
        },
        quality_runner=lambda: {
            "passed": True,
            "failed_turns": [],
            "missing_required_facts": {},
            "forbidden_fact_hits": {},
            "context_link_failures": {},
        },
        benchmark_runner=lambda: {
            "status": "valid",
            "full_session_p50_ms": 90.0,
            "session_p90_ms": 110.0,
            "first_turn_p50_ms": 30.0,
            "avg_turn_p50_ms": 30.0,
        },
        shadow_runner=lambda: {
            "shadow_status": "needs_execution",
            "shadow_full_session_ms": None,
            "api_event_id": None,
            "api_summary_payload": None,
            "model_name": "kimi-k2",
            "base_url_label": "kimi.example",
        },
    )

    assert (round_root / "verify.json").exists()
    assert (round_root / "benchmark_summary.json").exists()
    assert (round_root / "tool_usage_summary.json").exists()
    assert (round_root / "api_summary.json").exists()
    assert "experiment-ledger.tsv" not in "".join(p.name for p in round_root.iterdir())
    assert result["verify"]["tests_passed"] is True


def test_gate_zero_on_failed_tests():
    decision = evaluate_vsg(
        baseline_full_session_p50_ms=100.0,
        verify_payload={
            "tests_passed": False,
            "quality_passed": True,
            "benchmark_status": "valid",
            "benchmark_summary": {
                "full_session_p50_ms": 90.0,
                "session_p90_ms": 100.0,
            },
            "shadow_status": "needs_execution",
        },
    )

    assert decision["gate"] == 0
    assert decision["decision"] == "reset"


def test_gate_zero_on_failed_quality():
    decision = evaluate_vsg(
        baseline_full_session_p50_ms=100.0,
        verify_payload={
            "tests_passed": True,
            "quality_passed": False,
            "benchmark_status": "valid",
            "benchmark_summary": {
                "full_session_p50_ms": 90.0,
                "session_p90_ms": 100.0,
            },
            "shadow_status": "needs_execution",
        },
    )

    assert decision["gate"] == 0
    assert decision["decision"] == "reset"


def test_gain_computed_from_baseline_and_new_p50_only():
    decision = evaluate_vsg(
        baseline_full_session_p50_ms=100.0,
        verify_payload={
            "tests_passed": True,
            "quality_passed": True,
            "benchmark_status": "valid",
            "benchmark_summary": {
                "full_session_p50_ms": 80.0,
                "session_p90_ms": 140.0,
            },
            "shadow_status": "needs_execution",
        },
    )

    assert decision["gain"] == 0.2


def test_shadow_failure_does_not_rewrite_primary_gain_but_blocks_compatibility_claim():
    decision = evaluate_vsg(
        baseline_full_session_p50_ms=100.0,
        verify_payload={
            "tests_passed": True,
            "quality_passed": True,
            "benchmark_status": "valid",
            "benchmark_summary": {
                "full_session_p50_ms": 80.0,
                "session_p90_ms": 90.0,
            },
            "shadow_status": "failure",
        },
    )

    assert decision["gain"] == 0.2
    assert decision["decision"] == "needs_review"
    assert decision["compatibility_confirmed"] is False


def test_p90_guard_breach_requires_review():
    decision = evaluate_vsg(
        baseline_full_session_p50_ms=100.0,
        verify_payload={
            "tests_passed": True,
            "quality_passed": True,
            "benchmark_status": "valid",
            "benchmark_summary": {
                "full_session_p50_ms": 80.0,
                "session_p90_ms": 130.0,
            },
            "shadow_status": "needs_execution",
        },
        baseline_session_p90_ms=100.0,
    )

    assert decision["decision"] == "needs_review"
