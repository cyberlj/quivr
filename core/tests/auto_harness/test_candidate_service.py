from pathlib import Path

import pytest

from quivr_core.auto_harness.candidate_service import (
    BOOTSTRAP_CANDIDATE_IDS,
    HOTSPOT_TARGET_PATHS,
    CandidateRecord,
    CandidateService,
)


HEADER = (
    "candidate_id\tcandidate_family\tdirection\tcandidate_class\tsource\t"
    "target_path\tevidence\tverification\tstatus\tlast_result\tdo_not_repeat\tnotes\n"
)


def write_registry(path: Path, rows: list[str]) -> None:
    path.write_text(HEADER + "".join(rows), encoding="utf-8")


def make_row(
    candidate_id: str,
    candidate_class: str = "performance",
    status: str = "ready",
    do_not_repeat: str = "none",
    target_path: str = "core/quivr_core/rag/quivr_rag.py",
    direction: str = "history-trim",
) -> str:
    return (
        f"{candidate_id}\trag\t{direction}\t{candidate_class}\treview-findings\t"
        f"{target_path}\tfound hotspot\tpytest target\t{status}\tnone\t{do_not_repeat}\tnote\n"
    )


def test_empty_registry_returns_none(tmp_path):
    registry_path = tmp_path / "candidate-registry.tsv"
    write_registry(registry_path, [])

    service = CandidateService(registry_path)

    assert service.select_candidate() is None


def test_performance_candidate_beats_todo_candidate(tmp_path):
    registry_path = tmp_path / "candidate-registry.tsv"
    write_registry(
        registry_path,
        [
            make_row("todo-blocker-001", candidate_class="todo"),
            make_row("perf-history-001", candidate_class="performance", direction="context-trim"),
        ],
    )

    service = CandidateService(registry_path)

    selected = service.select_candidate()
    assert selected is not None
    assert selected.candidate_id == "perf-history-001"


def test_blocked_or_exhausted_candidates_are_skipped(tmp_path):
    registry_path = tmp_path / "candidate-registry.tsv"
    write_registry(
        registry_path,
        [
            make_row("perf-blocked-001", status="blocked"),
            make_row("perf-exhausted-001", status="exhausted", direction="context-trim"),
            make_row("perf-ready-001", status="ready", direction="langgraph-route"),
        ],
    )

    service = CandidateService(registry_path)

    selected = service.select_candidate()
    assert selected is not None
    assert selected.candidate_id == "perf-ready-001"


def test_repeated_direction_is_rejected(tmp_path):
    registry_path = tmp_path / "candidate-registry.tsv"
    write_registry(
        registry_path,
        [
            make_row("perf-repeat-001", do_not_repeat="direction"),
        ],
    )

    service = CandidateService(registry_path)

    assert service.select_candidate() is None


def test_bootstrap_candidates_outside_hotspot_files_are_rejected(tmp_path):
    registry_path = tmp_path / "candidate-registry.tsv"
    write_registry(
        registry_path,
        [
            make_row(
                "perf-history-001",
                target_path="core/quivr_core/brain/brain.py",
            ),
        ],
    )

    service = CandidateService(registry_path)

    with pytest.raises(ValueError):
        service.load_candidates()


def test_allowed_files_must_stay_within_candidate_target_path(tmp_path):
    registry_path = tmp_path / "candidate-registry.tsv"
    write_registry(
        registry_path,
        [
            make_row("perf-history-001"),
        ],
    )
    service = CandidateService(registry_path)
    candidate = service.load_candidates()[0]

    service.ensure_allowed_files_within_target_path(
        candidate, ["core/quivr_core/rag/quivr_rag.py"]
    )

    with pytest.raises(ValueError):
        service.ensure_allowed_files_within_target_path(
            candidate, ["core/quivr_core/rag/quivr_rag_langgraph.py"]
        )


def test_bootstrap_constants_cover_expected_seed_set():
    assert BOOTSTRAP_CANDIDATE_IDS == {
        "perf-history-001",
        "perf-context-001",
        "perf-langgraph-001",
        "todo-blocker-001",
    }
    assert HOTSPOT_TARGET_PATHS == {
        "core/quivr_core/rag/quivr_rag.py",
        "core/quivr_core/rag/quivr_rag_langgraph.py",
    }


def test_candidate_record_keeps_registry_fields():
    record = CandidateRecord(
        candidate_id="perf-history-001",
        candidate_family="rag",
        direction="history-trim",
        candidate_class="performance",
        source="review-findings",
        target_path="core/quivr_core/rag/quivr_rag.py",
        evidence="hotspot evidence",
        verification="pytest target",
        status="ready",
        last_result="none",
        do_not_repeat="none",
        notes="seed candidate",
    )

    assert record.candidate_id == "perf-history-001"
    assert record.target_path in HOTSPOT_TARGET_PATHS
