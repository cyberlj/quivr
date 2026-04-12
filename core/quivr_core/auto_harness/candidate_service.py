from __future__ import annotations

import csv
from pathlib import Path

from pydantic import Field

from quivr_core.auto_harness.contracts import AutoHarnessModel

HOTSPOT_TARGET_PATHS = {
    "core/quivr_core/rag/quivr_rag.py",
    "core/quivr_core/rag/quivr_rag_langgraph.py",
}

BOOTSTRAP_CANDIDATE_IDS = {
    "perf-history-001",
    "perf-context-001",
    "perf-langgraph-001",
    "todo-blocker-001",
}

SELECTABLE_STATUSES = {"new", "ready", "reset"}
CLASS_PRIORITY = {
    "performance": 0,
    "todo": 1,
}


class CandidateRecord(AutoHarnessModel):
    candidate_id: str
    candidate_family: str
    direction: str
    candidate_class: str
    source: str
    target_path: str
    evidence: str
    verification: str
    status: str
    last_result: str
    do_not_repeat: str
    notes: str = Field(default="")


class CandidateService:
    def __init__(self, registry_path: str | Path):
        self.registry_path = Path(registry_path)

    def load_candidates(self) -> list[CandidateRecord]:
        if not self.registry_path.exists():
            return []

        with self.registry_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            candidates = [CandidateRecord.model_validate(row) for row in reader]

        for candidate in candidates:
            self._validate_bootstrap_candidate(candidate)

        return candidates

    def select_candidate(self) -> CandidateRecord | None:
        candidates = self.load_candidates()
        selectable = [candidate for candidate in candidates if self._is_selectable(candidate)]
        if not selectable:
            return None

        return sorted(
            selectable,
            key=lambda candidate: (
                CLASS_PRIORITY.get(candidate.candidate_class, 99),
                candidates.index(candidate),
            ),
        )[0]

    def ensure_allowed_files_within_target_path(
        self, candidate: CandidateRecord, allowed_files: list[str]
    ) -> None:
        for allowed_file in allowed_files:
            if allowed_file != candidate.target_path:
                raise ValueError(
                    f"allowed file {allowed_file!r} must stay within candidate target {candidate.target_path!r}"
                )

    def _is_selectable(self, candidate: CandidateRecord) -> bool:
        return (
            candidate.status in SELECTABLE_STATUSES
            and candidate.do_not_repeat == "none"
        )

    def _validate_bootstrap_candidate(self, candidate: CandidateRecord) -> None:
        if (
            candidate.candidate_id in BOOTSTRAP_CANDIDATE_IDS
            and candidate.target_path not in HOTSPOT_TARGET_PATHS
        ):
            raise ValueError(
                f"bootstrap candidate {candidate.candidate_id!r} must target one of {sorted(HOTSPOT_TARGET_PATHS)}"
            )
