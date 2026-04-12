from pathlib import Path

from quivr_core.auto_harness.contracts import LoopStatus, RuntimeState
from quivr_core.auto_harness.observer import refresh_observer_summary
from quivr_core.auto_harness.state_store import StateStore


def make_runtime_state() -> RuntimeState:
    return RuntimeState(
        loop_status=LoopStatus.AWAIT_HUMAN,
        current_best_commit="abc123",
        current_best_round_id="r-20260410-003",
        current_best_candidate_id="perf-history-001",
        control_branch="quivr-auto-harness",
        control_worktree=Path("/tmp/control"),
        active_round_id="r-20260411-001",
        active_execution_worktree=Path("/tmp/wt-r-20260411-001"),
        human_wait_reason="repeated benchmark invalid resets",
        last_updated="2026-04-11T12:30:00Z",
    )


def test_observer_refreshes_summary_after_repeated_resets(tmp_path):
    docs_root = tmp_path / "docs" / "auto-harness"
    store = StateStore(docs_root)
    store.write_runtime_state(make_runtime_state())

    (docs_root / "experiment-ledger.tsv").parent.mkdir(parents=True, exist_ok=True)
    (docs_root / "experiment-ledger.tsv").write_text(
        "\n".join(
            [
                "round_id\tcandidate_id\tcandidate_family\tdirection\tround_type\tfailure_class\tworktree_id\tstart_commit\tend_commit\ttests_passed\tquality_guard_passed\tbenchmark_status\tbaseline_full_session_p50_ms\tnew_full_session_p50_ms\tbaseline_session_p90_ms\tnew_session_p90_ms\tgate\tgain\tdecision\tnotes",
                "r-20260410-001\tperf-history-001\trag\thistory-trim\tperformance\tbenchmark_invalid\twt-1\tabc\tabc\ttrue\ttrue\tinvalid\t100\t105\t120\t130\t0\t-0.05\treset\tfirst miss",
                "r-20260410-002\tperf-history-001\trag\thistory-trim\tperformance\tbenchmark_invalid\twt-2\tabc\tabc\ttrue\ttrue\tinvalid\t100\t106\t120\t132\t0\t-0.06\treset\tsecond miss",
                "r-20260410-003\tperf-history-001\trag\thistory-trim\tperformance\tbenchmark_invalid\twt-3\tabc\tabc\ttrue\ttrue\tinvalid\t100\t104\t120\t131\t0\t-0.04\treset\tthird miss",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    round_root = docs_root / "state" / "rounds" / "r-20260410-003"
    round_root.mkdir(parents=True, exist_ok=True)
    (round_root / "verify.json").write_text(
        '{\n  "round_id": "r-20260410-003",\n  "tests_passed": true,\n  "quality_passed": true,\n  "benchmark_status": "invalid",\n  "shadow_status": "failure",\n  "benchmark_gain_pct": -0.04,\n  "api_event_id": "api-1"\n}\n',
        encoding="utf-8",
    )

    summary = refresh_observer_summary(docs_root)
    summary_text = (docs_root / "observer-summary.md").read_text(encoding="utf-8")

    assert summary["repeated_failure_class"] == "benchmark_invalid"
    assert summary["recommendation"] == "intervene"
    assert "`await_human`" in summary_text
    assert "`0 keep / 3 reset`" in summary_text
    assert "`benchmark_invalid`" in summary_text
    assert "`degraded (latest=failure)`" in summary_text
