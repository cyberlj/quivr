# Worktree Strategy

This document defines how multi-agent execution uses git worktrees.

## Goals

- isolate code changes per round
- avoid shared dirty state between execution agents
- keep planning and ledger files in one control worktree
- make reset cheap and deterministic

## Roles and worktrees

### Control worktree

The control worktree is the long-lived planning surface.

It owns:

- `active-plan.md`
- `round-plan.md`
- `plan-review.md`
- `runtime-state.md`
- `candidate-registry.tsv`
- `experiment-ledger.tsv`
- `reflection-log.md`

Default control worktree:

- `/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness`

### Execution worktree

Each round gets one dedicated execution worktree created from `current_best_commit`.

It owns:

- the code change for that round
- local test output
- local benchmark output

It must not become the long-term source of planning truth.

## Round flow

1. Conductor reads `current_best_commit` from `runtime-state.md`
2. Conductor creates an execution worktree from that commit
3. Worker makes code changes only in that execution worktree
4. Verifier runs tests and benchmark there
5. If the round resets:
   - discard the execution worktree
   - keep the control docs
6. If the round keeps:
   - integrate the kept commit back to the control branch
   - update `runtime-state.md`
   - discard the execution worktree

## Rule

Multiple agents must not edit the same execution worktree at the same time.

One round maps to one execution worktree.
