# AGENTS.md

This repository uses `docs/auto-harness/` as the system of record for autonomous work.

## Read order

Every agent working in this repository must read, in order:

1. `docs/auto-harness/OPERATING_MODEL.md`
2. `docs/auto-harness/planning-model.md`
3. `docs/auto-harness/agent-contract.md`
4. `docs/auto-harness/runtime-state.md`
5. `docs/auto-harness/active-plan.md`

Then read only the specific role files and target code needed for the assigned task.

## Hard rules

- Do not fabricate unknown facts.
- Do not keep key state in working memory when it can be written to the repo.
- Do not start code changes without an approved round plan.
- Do not self-approve a keep.
- Do not modify files outside the round plan's allowed scope.
- Do not expand the mutable surface without escalating.
- Do not leave stray temporary files in the repository root.

## Required write-backs

Agents must write back new durable information to the repository when it appears:

- update `runtime-state.md` when loop state changes
- update `candidate-registry.tsv` when candidate status changes
- update `round-plan.md` for each round
- update `plan-review.md` before execution
- update `experiment-ledger.tsv` after verification
- update `reflection-log.md` after keep or reset
- update `decision-log.md` when a stable rule changes
- update `design-open-items.md` when a new design gap is discovered

## Environment facts

When an agent confirms a new environment fact, it must write it down in the repo if future rounds will depend on it.

Examples:

- confirmed model provider and base URL
- benchmark corpus location
- dependency or tool availability
- worktree layout

## Worktree discipline

- Conductor planning files live in the control worktree.
- Execution agents use dedicated per-round worktrees.
- A keep may only be integrated back through the documented worktree flow.

See `docs/auto-harness/worktree-strategy.md` for the execution model.

## Role prompts

Role-specific identity prompts live in:

- `docs/auto-harness/agent-prompts.md`
