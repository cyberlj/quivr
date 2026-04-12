# AGENTS.md

This repository uses `docs/auto-harness/` as the system of record for autonomous work.

## Read order

Every agent working in this repository must read, in order:

1. `docs/auto-harness/review-findings.md`
2. `docs/auto-harness/phase1-mvp-design.md`
3. `docs/auto-harness/phase1-mvp-implementation-plan.md`
4. `docs/auto-harness/state/execution-status.json` when present

Then read only the specific supporting docs and target code needed for the assigned task.

## Document tiers

Use `docs/auto-harness/` in these tiers:

### 1. Current mainline

These files define the current Phase 1 direction and execution order:

- `docs/auto-harness/review-findings.md`
- `docs/auto-harness/phase1-mvp-design.md`
- `docs/auto-harness/phase1-mvp-implementation-plan.md`

### 2. Constraint references

Read these when the task touches their domain:

- `docs/auto-harness/agent-contract.md`
- `docs/auto-harness/planning-model.md`
- `docs/auto-harness/observation-model.md`
- `docs/auto-harness/event-schema.md`
- `docs/auto-harness/worktree-strategy.md`
- `docs/auto-harness/benchmark-spec.md`
- `docs/auto-harness/quality-guard-spec.md`
- `docs/auto-harness/OPERATING_MODEL.md`

### 3. Runtime state

These files describe current loop state and recent history. Read them as live state, not as design baseline:

- `docs/auto-harness/state/execution-status.json`
- `docs/auto-harness/runtime-state.md`
- `docs/auto-harness/round-plan.md`
- `docs/auto-harness/plan-review.md`
- `docs/auto-harness/observer-summary.md`
- `docs/auto-harness/candidate-registry.tsv`
- `docs/auto-harness/experiment-ledger.tsv`
- `docs/auto-harness/reflection-log.md`
- `docs/auto-harness/decision-log.md`
- `docs/auto-harness/event-log.jsonl`
- `docs/auto-harness/tool-log.jsonl`
- `docs/auto-harness/api-log.jsonl`

### 4. Historical docs

These files are background only. They must not override the current mainline:

- `docs/auto-harness/implementation-plan.md`
- `docs/auto-harness/active-plan.md`

## Source of truth

- Current design baseline: `docs/auto-harness/phase1-mvp-design.md`
- Current execution order: `docs/auto-harness/phase1-mvp-implementation-plan.md`
- Current implementation progress and continuation point: `docs/auto-harness/state/execution-status.json`
- Runtime truth: `docs/auto-harness/state/*.json` when present
- Markdown views are human-readable outputs, not machine source of truth

## Hard rules

- Do not fabricate unknown facts.
- Do not keep key state in working memory when it can be written to the repo.
- Do not resume implementation work without reading `docs/auto-harness/state/execution-status.json` when it exists.
- Do not redo tasks already marked complete in `docs/auto-harness/state/execution-status.json` unless the file also records a reason to reopen them.
- Do not use `state/execution-status.json` as the shared runtime state for multi-agent round execution.
- Do not let multiple loop roles co-own `state/execution-status.json`; follow role ownership for `state/*.json`, ledgers, and logs.
- Do not start code changes without an approved round plan.
- Do not self-approve a keep.
- Do not modify files outside the round plan's allowed scope.
- Do not expand the mutable surface without escalating.
- Do not leave stray temporary files in the repository root.
- Do not treat `runtime-state.md`, `round-plan.md`, or other runtime files as the design baseline.
- Do not treat `docs/auto-harness/implementation-plan.md` as the active implementation plan.

## Required write-backs

Agents must write back new durable information to the repository when it appears:

- update `state/execution-status.json` when active implementation-plan progress, verified commands, blockers, or continuation point changes
- update `runtime-state.md` when loop state changes
- update `candidate-registry.tsv` when candidate status changes
- update `round-plan.md` for each round
- update `plan-review.md` before execution
- update `experiment-ledger.tsv` after verification
- update `reflection-log.md` after keep or reset
- update `decision-log.md` when a stable rule changes
- update `design-open-items.md` when a new design gap is discovered
- append `event-log.jsonl` for major loop events
- append `tool-log.jsonl` for structured tool usage summaries
- append `api-log.jsonl` for external API interaction summaries
- update `observer-summary.md` when the observer runs

`runtime-state.md` is owned by the Conductor only.

`state/execution-status.json` is the canonical continuation record for agents executing the active implementation plan. It is not the shared state surface for multi-agent round runtime.

Observation-maintenance writes must not recursively log themselves.

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
- Observation files are written in the control worktree only.

See `docs/auto-harness/worktree-strategy.md` for the execution model.

## Role prompts

Role-specific identity prompts live in:

- `docs/auto-harness/agent-prompts.md`

## Observation layer

Observation roles do not control strategy.

- `Recorder` normalizes facts handed off by primary loop roles
- `Observer` summarizes and alerts
- `Dashboard` stays read-only

No observation role may edit business code or decide keep or reset.
