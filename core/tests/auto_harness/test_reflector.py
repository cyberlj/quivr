import json

import pytest

from quivr_core.auto_harness.reflector import reflect_round


def make_verify_payload() -> dict:
    return {
        "round_id": "r-20260411-001",
        "tests_passed": True,
        "quality_passed": True,
        "benchmark_status": "valid",
        "shadow_status": "needs_execution",
        "benchmark_summary": {
            "full_session_p50_ms": 90.0,
            "session_p90_ms": 100.0,
        },
    }


def test_missing_verifier_result_blocks_reflection(tmp_path):
    docs_root = tmp_path / "docs" / "auto-harness"

    with pytest.raises(ValueError):
        reflect_round(
            docs_root=docs_root,
            round_id="r-20260411-001",
            decision="reset",
            worker_change_note="narrowed retrieval scope",
            verify_payload=None,
            recent_ledger_entries=[],
            candidate_lifecycle={"candidate_id": "perf-history-001", "status": "active"},
        )


@pytest.mark.parametrize("decision", ["keep", "reset"])
def test_reflection_is_written_after_keep_and_reset(tmp_path, decision):
    docs_root = tmp_path / "docs" / "auto-harness"

    result = reflect_round(
        docs_root=docs_root,
        round_id="r-20260411-001",
        decision=decision,
        worker_change_note="trimmed repeated history packing",
        verify_payload=make_verify_payload(),
        recent_ledger_entries=[
            {
                "round_id": "r-20260410-003",
                "decision": "reset",
                "failure_class": "benchmark_invalid",
            }
        ],
        candidate_lifecycle={"candidate_id": "perf-history-001", "status": "active"},
    )

    reflection_path = docs_root / "state" / "rounds" / "r-20260411-001" / "reflection.json"
    log_path = docs_root / "reflection-log.md"
    archive_path = docs_root / "rounds" / "r-20260411-001" / "reflection.md"

    payload = json.loads(reflection_path.read_text(encoding="utf-8"))
    assert payload["round_id"] == "r-20260411-001"
    assert payload["summary"].startswith(decision)
    assert result["reflection"]["replan_recommendation"]
    assert "r-20260411-001" in log_path.read_text(encoding="utf-8")
    assert "trimmed repeated history packing" in archive_path.read_text(encoding="utf-8")
