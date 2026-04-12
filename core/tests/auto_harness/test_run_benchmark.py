from quivr_core.auto_harness.run_benchmark import run_primary_benchmark


def test_warmup_is_excluded(tmp_path):
    result = run_primary_benchmark(
        worktree=tmp_path,
        warmup_session={"full_session_ms": 999.0, "turns_ms": [999.0, 999.0, 999.0]},
        measured_sessions=[
            {"full_session_ms": 100.0, "turns_ms": [30.0, 30.0, 40.0]},
            {"full_session_ms": 110.0, "turns_ms": [35.0, 35.0, 40.0]},
            {"full_session_ms": 120.0, "turns_ms": [40.0, 40.0, 40.0]},
            {"full_session_ms": 130.0, "turns_ms": [45.0, 40.0, 45.0]},
            {"full_session_ms": 140.0, "turns_ms": [50.0, 45.0, 45.0]},
        ],
    )

    assert result["status"] == "valid"
    assert result["full_session_p50_ms"] == 120.0


def test_five_measured_runs_are_aggregated(tmp_path):
    result = run_primary_benchmark(
        worktree=tmp_path,
        measured_sessions=[
            {"full_session_ms": 100.0, "turns_ms": [30.0, 30.0, 40.0]},
            {"full_session_ms": 110.0, "turns_ms": [35.0, 35.0, 40.0]},
            {"full_session_ms": 120.0, "turns_ms": [40.0, 40.0, 40.0]},
            {"full_session_ms": 130.0, "turns_ms": [45.0, 40.0, 45.0]},
            {"full_session_ms": 140.0, "turns_ms": [50.0, 45.0, 45.0]},
        ],
    )

    assert result["status"] == "valid"
    assert result["full_session_p50_ms"] == 120.0
    assert result["session_p90_ms"] == 140.0
    assert result["first_turn_p50_ms"] == 40.0
    assert result["avg_turn_p50_ms"] == 40.0


def test_invalid_runs_return_status_not_valid(tmp_path):
    result = run_primary_benchmark(
        worktree=tmp_path,
        measured_sessions=[
            {"full_session_ms": 100.0, "turns_ms": [30.0, 30.0, 40.0]},
            {"full_session_ms": 110.0, "turns_ms": [35.0, 35.0, 40.0]},
        ],
    )

    assert result["status"] != "valid"
