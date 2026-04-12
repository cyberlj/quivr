import pytest

from quivr_core.auto_harness.run_shadow_e2e import run_shadow_e2e


def test_missing_env_returns_skipped_env_missing(tmp_path):
    result = run_shadow_e2e(
        worktree=tmp_path,
        env={},
    )

    assert result["shadow_status"] == "skipped_env_missing"


def test_fake_success_without_api_event_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        run_shadow_e2e(
            worktree=tmp_path,
            env={
                "OPENAI_API_KEY": "test-key",
                "OPENAI_BASE_URL": "https://kimi.example/v1",
                "OPENAI_MODEL": "kimi-k2",
            },
            fake_result={
                "shadow_status": "success",
                "shadow_full_session_ms": 1200.0,
                "api_event_id": None,
            },
        )


def test_result_contains_model_name_and_endpoint_label(tmp_path):
    result = run_shadow_e2e(
        worktree=tmp_path,
        env={
            "OPENAI_API_KEY": "test-key",
            "OPENAI_BASE_URL": "https://kimi.example/v1",
            "OPENAI_MODEL": "kimi-k2",
        },
        fake_result={
            "shadow_status": "needs_execution",
            "shadow_full_session_ms": None,
            "api_event_id": None,
        },
    )

    assert result["model_name"] == "kimi-k2"
    assert result["base_url_label"] == "kimi.example"
