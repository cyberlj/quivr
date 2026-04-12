from __future__ import annotations

import csv
from pathlib import Path

from quivr_core.auto_harness.candidate_service import CandidateService
from quivr_core.auto_harness.contracts import ReviewOutcome, ReviewResult, RoundState


class Reviewer:
    def __init__(
        self,
        candidate_registry_path: str | Path,
        experiment_ledger_path: str | Path,
        reflection_log_path: str | Path,
    ):
        self.candidate_service = CandidateService(candidate_registry_path)
        self.experiment_ledger_path = Path(experiment_ledger_path)
        self.reflection_log_path = Path(reflection_log_path)

    def review(self, round_state: RoundState) -> ReviewResult:
        candidate = self._candidate_by_id(round_state.candidate_id)
        if candidate is None:
            return self._reject(
                round_state.round_id,
                priority_check="candidate_not_selectable",
                review_notes=["candidate missing from registry"],
            )

        if not self._candidate_is_selectable(candidate):
            return self._reject(
                round_state.round_id,
                priority_check="candidate_not_selectable",
                review_notes=["candidate lifecycle does not permit selection"],
            )

        if self._has_missing_commands(round_state):
            return self._reject(
                round_state.round_id,
                verification_check="missing_commands",
                review_notes=["verification commands must all be present"],
            )

        if not round_state.reset_rule.strip():
            return self._reject(
                round_state.round_id,
                reset_check="missing_reset_rule",
                review_notes=["reset rule must be explicit"],
            )

        if not self._scope_is_bounded(round_state, candidate.target_path):
            return self._revise(
                round_state.round_id,
                scope_check="scope_not_bounded",
                review_notes=["allowed_files must stay within the candidate target path"],
            )

        if " and " in round_state.hypothesis.lower():
            return self._revise(
                round_state.round_id,
                scope_check="split_hypothesis",
                review_notes=["round hypothesis must stay single and testable"],
            )

        if self._direction_repeated(round_state.direction):
            return self._reject(
                round_state.round_id,
                repeat_check="repeated_direction",
                review_notes=["direction already appears in ledger or reflection history"],
            )

        return ReviewResult(
            round_id=round_state.round_id,
            review_outcome=ReviewOutcome.APPROVED,
            allows_execution=True,
            requires_human=False,
            scope_check="bounded",
            verification_check="complete",
            repeat_check="novel",
            reset_check="present",
            priority_check="candidate_valid",
            review_notes=["plan is approved for execution"],
        )

    def _candidate_by_id(self, candidate_id: str):
        for candidate in self.candidate_service.load_candidates():
            if candidate.candidate_id == candidate_id:
                return candidate
        return None

    def _candidate_is_selectable(self, candidate) -> bool:
        return candidate.status in {"new", "ready", "reset", "active"} and candidate.do_not_repeat == "none"

    def _has_missing_commands(self, round_state: RoundState) -> bool:
        command_fields = (
            round_state.tests_command,
            round_state.quality_guard_command,
            round_state.benchmark_command,
            round_state.shadow_command,
            round_state.vsg_command,
        )
        return any(not command.strip() for command in command_fields)

    def _scope_is_bounded(self, round_state: RoundState, target_path: str) -> bool:
        return round_state.allowed_files == [target_path]

    def _direction_repeated(self, direction: str) -> bool:
        if self.experiment_ledger_path.exists():
            with self.experiment_ledger_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                if any(row.get("direction") == direction for row in reader):
                    return True

        if self.reflection_log_path.exists():
            if direction in self.reflection_log_path.read_text(encoding="utf-8"):
                return True

        return False

    def _reject(
        self,
        round_id: str,
        scope_check: str = "bounded",
        verification_check: str = "complete",
        repeat_check: str = "novel",
        reset_check: str = "present",
        priority_check: str = "candidate_valid",
        review_notes: list[str] | None = None,
    ) -> ReviewResult:
        return ReviewResult(
            round_id=round_id,
            review_outcome=ReviewOutcome.REJECT,
            allows_execution=False,
            requires_human=False,
            scope_check=scope_check,
            verification_check=verification_check,
            repeat_check=repeat_check,
            reset_check=reset_check,
            priority_check=priority_check,
            review_notes=review_notes or ["review rejected"],
        )

    def _revise(
        self,
        round_id: str,
        scope_check: str = "bounded",
        verification_check: str = "complete",
        repeat_check: str = "novel",
        reset_check: str = "present",
        priority_check: str = "candidate_valid",
        review_notes: list[str] | None = None,
    ) -> ReviewResult:
        return ReviewResult(
            round_id=round_id,
            review_outcome=ReviewOutcome.REVISE,
            allows_execution=False,
            requires_human=False,
            scope_check=scope_check,
            verification_check=verification_check,
            repeat_check=repeat_check,
            reset_check=reset_check,
            priority_check=priority_check,
            review_notes=review_notes or ["review requires revision"],
        )
