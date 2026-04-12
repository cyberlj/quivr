from __future__ import annotations

from quivr_core.auto_harness.contracts import ReviewResult, RoundState, RuntimeState


def render_runtime_state_markdown(runtime_state: RuntimeState) -> str:
    return "\n".join(
        [
            "# Runtime State",
            "",
            "Generated from `docs/auto-harness/state/runtime-state.json`.",
            "",
            f"- `loop_status`: `{runtime_state.loop_status.value}`",
            f"- `current_best_commit`: `{runtime_state.current_best_commit}`",
            f"- `current_best_round_id`: `{runtime_state.current_best_round_id}`",
            f"- `current_best_candidate_id`: `{runtime_state.current_best_candidate_id}`",
        ]
    )


def render_round_plan_markdown(round_state: RoundState) -> str:
    return "\n".join(
        [
            "# Round Plan",
            "",
            f"- `round_id`: `{round_state.round_id}`",
            f"- `candidate_id`: `{round_state.candidate_id}`",
            f"- `round_type`: `{round_state.round_type}`",
            f"- `hypothesis`: {round_state.hypothesis}",
            f"- `allowed_files`: `{', '.join(round_state.allowed_files)}`",
            f"- `tests`: `{round_state.tests_command}`",
            f"- `quality_guard`: `{round_state.quality_guard_command}`",
            f"- `benchmark`: `{round_state.benchmark_command}`",
            f"- `shadow`: `{round_state.shadow_command}`",
            f"- `vsg_evaluator`: `{round_state.vsg_command}`",
            f"- `success_rule`: {round_state.success_rule}",
            f"- `reset_rule`: {round_state.reset_rule}",
        ]
    )


def render_plan_review_markdown(review_result: ReviewResult) -> str:
    return "\n".join(
        [
            "# Plan Review",
            "",
            f"- `round_id`: `{review_result.round_id}`",
            f"- `review_outcome`: `{review_result.review_outcome.value}`",
            f"- `allows_execution`: `{str(review_result.allows_execution).lower()}`",
            f"- `requires_human`: `{str(review_result.requires_human).lower()}`",
            f"- `scope_check`: `{review_result.scope_check}`",
            f"- `verification_check`: `{review_result.verification_check}`",
            f"- `repeat_check`: `{review_result.repeat_check}`",
            f"- `reset_check`: `{review_result.reset_check}`",
            f"- `priority_check`: `{review_result.priority_check}`",
        ]
    )


def render_observer_summary_markdown(summary_lines: list[str]) -> str:
    return "\n".join(["# Observer Summary", "", *summary_lines])
