from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AutoHarnessModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoopStatus(str, Enum):
    DESIGN_ONLY = "design_only"
    PLANNING = "planning"
    PLAN_REVIEW = "plan_review"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RESETTING = "resetting"
    CANDIDATE_POOL_EMPTY = "candidate_pool_empty"
    BLOCKED = "blocked"
    AWAIT_HUMAN = "await_human"


class ReviewOutcome(str, Enum):
    APPROVED = "approved"
    REVISE = "revise"
    REJECT = "reject"


class ShadowStatus(str, Enum):
    SUCCESS = "success"
    SKIPPED_ENV_MISSING = "skipped_env_missing"
    FAILURE = "failure"
    NEEDS_EXECUTION = "needs_execution"


class Decision(str, Enum):
    KEEP = "keep"
    RESET = "reset"
    NEEDS_REVIEW = "needs_review"
    AWAIT_HUMAN = "await_human"


class RuntimeState(AutoHarnessModel):
    loop_status: LoopStatus
    current_best_commit: str
    current_best_round_id: str
    current_best_candidate_id: str
    control_branch: str
    control_worktree: Path
    active_round_id: str | None
    active_execution_worktree: Path | None
    human_wait_reason: str
    last_updated: str


class RoundState(AutoHarnessModel):
    round_id: str
    candidate_id: str
    candidate_family: str
    direction: str
    candidate_class: str
    round_type: str
    hypothesis: str
    why_now: str
    allowed_files: list[str] = Field(min_length=1)
    forbidden_files: list[str]
    tests_command: str
    quality_guard_command: str
    benchmark_command: str
    shadow_command: str
    vsg_command: str
    success_rule: str
    reset_rule: str
    novelty_check: str
    expected_risk: str
    execution_worktree: Path | None = None


class AgentManifest(AutoHarnessModel):
    round_id: str
    agent_id: str
    role: str
    worktree: Path
    allowed_files: list[str] = Field(min_length=1)
    forbidden_actions: list[str]
    allowed_commands: list[str] = Field(min_length=1)


class ReviewResult(AutoHarnessModel):
    round_id: str
    review_outcome: ReviewOutcome
    allows_execution: bool = False
    requires_human: bool = False
    scope_check: str
    verification_check: str
    repeat_check: str
    reset_check: str
    priority_check: str
    review_notes: list[str] = Field(min_length=1)


class VerifyResult(AutoHarnessModel):
    round_id: str
    tests_passed: bool
    quality_passed: bool
    benchmark_status: str
    shadow_status: ShadowStatus
    benchmark_gain_pct: float
    api_event_id: str | None


class DecisionResult(AutoHarnessModel):
    round_id: str
    decision: Decision
    summary: str


class ReflectionResult(AutoHarnessModel):
    round_id: str
    summary: str
    replan_recommendation: str
    lessons: list[str] = Field(min_length=1)


class RecorderEvent(AutoHarnessModel):
    event_id: str
    round_id: str
    kind: str
    payload: dict[str, Any]
    recorded_at: str
