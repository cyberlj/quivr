from pathlib import Path

from quivr_core.auto_harness.run_tests import run_related_tests


def test_failing_tests_produce_tests_passed_false(tmp_path):
    result = run_related_tests(
        command="python -c \"import sys; print('boom'); sys.exit(1)\"",
        worktree=tmp_path,
    )

    assert result["tests_passed"] is False
    assert result["returncode"] == 1
    assert "boom" in result["stdout"]


def test_passing_tests_produce_structured_fields(tmp_path):
    result = run_related_tests(
        command="python -c \"print('ok')\"",
        worktree=tmp_path,
    )

    assert result["tests_passed"] is True
    assert result["returncode"] == 0
    assert result["command"] == "python -c \"print('ok')\""
    assert "ok" in result["stdout"]
