from __future__ import annotations

from quivr_core.auto_harness.candidate_service import CandidateRecord
from quivr_core.auto_harness.contracts import RoundState, RuntimeState


class Planner:
    def plan_round(
        self, candidate: CandidateRecord, runtime_state: RuntimeState, round_id: str
    ) -> RoundState:
        tests_command = self._tests_command_for_candidate(candidate)
        target_label = candidate.target_path.rsplit("/", maxsplit=1)[-1]

        return RoundState(
            round_id=round_id,
            candidate_id=candidate.candidate_id,
            candidate_family=candidate.candidate_family,
            direction=candidate.direction,
            candidate_class=candidate.candidate_class,
            round_type=candidate.candidate_class,
            hypothesis=f"Optimize {candidate.direction} in {target_label}.",
            why_now=(
                f"{candidate.evidence}. Current best commit is "
                f"{runtime_state.current_best_commit}."
            ),
            allowed_files=[candidate.target_path],
            forbidden_files=[
                "docs/auto-harness/runtime-state.md",
                "docs/auto-harness/round-plan.md",
                "docs/auto-harness/plan-review.md",
            ],
            tests_command=tests_command,
            quality_guard_command="python -m quivr_core.auto_harness.run_quality_guard",
            benchmark_command="python -m quivr_core.auto_harness.run_benchmark",
            shadow_command="python -m quivr_core.auto_harness.run_shadow_e2e",
            vsg_command="python -m quivr_core.auto_harness.vsg",
            success_rule="Keep only if deterministic gates stay green and p50 improves.",
            reset_rule="Reset immediately on failed tests, failed quality guard, or invalid benchmark.",
            novelty_check=f"Direction {candidate.direction} must be novel against recent ledger and reflection history.",
            expected_risk="medium",
            execution_worktree=None,
        )

    def _tests_command_for_candidate(self, candidate: CandidateRecord) -> str:
        if candidate.target_path.endswith("quivr_rag_langgraph.py"):
            return "python -m pytest tests/test_quivr_rag.py -v"
        return "python -m pytest tests/test_quivr_rag.py tests/test_chat_history.py -v"
