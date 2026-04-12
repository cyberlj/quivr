from pathlib import Path

from quivr_core.auto_harness.run_quality_guard import run_quality_guard


def test_required_facts_and_forbidden_facts_are_enforced(tmp_path):
    result = run_quality_guard(
        worktree=tmp_path,
        scripted_answers=[
            "Project Atlas keeps notes in Paris and tracks release codenames.",
            "The release codename is Orchid and the timeline is Q3 2026.",
            "I forgot the codename and claim it is Violet.",
        ],
    )

    assert result["passed"] is False
    assert result["failed_turns"] == ["turn-3"]
    assert result["forbidden_fact_hits"] == {
        "turn-3": ["Violet"]
    }


def test_context_link_failures_are_reported(tmp_path):
    result = run_quality_guard(
        worktree=tmp_path,
        scripted_answers=[
            "Project Atlas keeps notes in Paris and tracks release codenames.",
            "The release codename is Orchid and the timeline is Q3 2026.",
            "The codename is Orchid but I dropped the location context.",
        ],
    )

    assert result["passed"] is False
    assert result["failed_turns"] == ["turn-3"]
    assert result["context_link_failures"] == {
        "turn-3": ["Paris"]
    }


def test_quality_guard_sets_round_local_storage_env(tmp_path):
    result = run_quality_guard(
        worktree=tmp_path,
        scripted_answers=[
            "Project Atlas keeps notes in Paris and tracks release codenames.",
            "The release codename is Orchid and the timeline is Q3 2026.",
            "Project Atlas still references Paris and confirms Orchid.",
        ],
    )

    assert result["passed"] is True
    assert result["failed_turns"] == []
    assert result["storage_path"] == str(tmp_path / ".runtime" / "storage")
