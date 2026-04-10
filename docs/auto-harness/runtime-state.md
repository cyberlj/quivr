# Runtime State

This file is the durable runtime state for the auto harness.

## Fields

- `loop_status`: `design_only`
- `current_best_commit`: `b741578d`
- `current_best_round_id`: `none`
- `current_best_candidate_id`: `none`
- `control_branch`: `quivr-auto-harness`
- `control_worktree`: `/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness`
- `active_execution_worktree`: `none`
- `awaiting_human`: `true`
- `last_updated`: `2026-04-10`

## Status values

Allowed `loop_status` values:

- `design_only`
- `planning`
- `plan_review`
- `executing`
- `verifying`
- `resetting`
- `candidate_pool_empty`
- `blocked`
- `await_human`

## Update rule

Whenever the loop changes state, update this file before proceeding to the next major step.
