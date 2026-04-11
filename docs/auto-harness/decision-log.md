# Decision Log

This file records stable design decisions for the Phase 1 auto harness.

## D-001

- Decision: The auto harness targets the current `quivr-auto-harness` repository only.
- Why: The earlier `quivr-auto-dev` wording was a naming mistake. Design must match the actual repository boundary.
- Alternatives rejected: designing for a future separate execution repository before the current harness exists.

## D-002

- Decision: Phase 1 prioritizes performance optimization. TODO work is allowed only when it is `P0` functional integrity or `P1` research-blocking.
- Why: Ordinary TODO work is easier to keep and would distort the loop away from the main objective.
- Alternatives rejected: equal priority between TODO closure and performance work.

## D-003

- Decision: The Phase 1 target scenario is small teams, local or lightweight vector storage, around 1 GB of knowledge, and continuous multi-turn question answering.
- Why: Application-level benchmark decisions must match the actual intended usage pattern.
- Alternatives rejected: optimizing for large enterprise or million-scale deployments first.

## D-004

- Decision: Answer quality has priority over raw speed.
- Why: Faster but worse answers are not valid progress for the target scenario.
- Alternatives rejected: speed-first optimization with tolerated answer drift.

## D-005

- Decision: The north-star score is `VSG = Gate x Gain`.
- Why: The loop needs one explicit keep or reset rule.
- Alternatives rejected: informal judgment or multi-objective scoring without a hard gate.

## D-006

- Decision: `Gate` requires related tests, quality guard, and valid benchmark behavior to pass.
- Why: Unverified or noisy rounds must not advance the code baseline.
- Alternatives rejected: keeping rounds on apparent speed gain alone.

## D-007

- Decision: Performance `Gain` uses `full_session_p50_ms` as the primary metric and `session_p90_ms` as a guard metric.
- Why: `p50` is more stable for autonomous loop control in a noisy external-model setup, while `p90` protects against tail regressions.
- Alternatives rejected: using `p90` as the primary keep metric in Phase 1.

## D-008

- Decision: Phase 1 uses a fixed application-owned primary gain benchmark for `Gain`, while the real configured Kimi path runs as a shadow E2E benchmark.
- Why: The keep or reset loop needs a stable baseline that does not drift with upstream provider upgrades, rate limits, or scheduling noise. The real Kimi path is still important, but as a compatibility and observation layer, not as the sole score anchor.
- Alternatives rejected: using the active Kimi path as the only primary gain signal, or dropping the real Kimi path entirely.

## D-009

- Decision: Code resets revert to `current_best_commit`, but research logs and design documents persist.
- Why: Failed rounds must not pollute the code baseline, but the system must keep its memory.
- Alternatives rejected: resetting documentation together with code.

## D-010

- Decision: Candidate pool uses layered priority with performance first and `P0`/`P1` TODOs second.
- Why: This protects the loop from drifting toward easy but low-value keeps.
- Alternatives rejected: one mixed pool for all work items.

## D-011

- Decision: `current_best_commit` must live in a repository state file, not only in conductor memory.
- Why: Keep and reset depend on a durable anchor that survives restarts and handoffs.
- Alternatives rejected: implicit state held by the active conductor.

## D-012

- Decision: Candidate tracking requires a dedicated registry with `candidate_family` and `direction`.
- Why: Novelty checks and repeated-failure detection need structured history.
- Alternatives rejected: deriving candidate identity from free-text notes alone.

## D-013

- Decision: The loop must support terminal and waiting states such as `candidate_pool_empty`, `blocked`, and `await_human`.
- Why: A harness should stop consciously when there is no valid work instead of re-planning forever.
- Alternatives rejected: endless planner-review-replan churn.

## D-014

- Decision: Multi-agent code execution uses one dedicated execution worktree per round, while planning and ledger state stay in the control worktree.
- Why: This isolates code changes, keeps reset cheap, and protects shared planning state.
- Alternatives rejected: making all agents share one dirty worktree.

## D-015

- Decision: The repository needs a local `AGENTS.md` and fixed role prompts.
- Why: Agents need an in-repo router, write-back rules, and stable role identity.
- Alternatives rejected: relying only on external conversation context or host-level instructions.

## D-016

- Decision: Shadow E2E benchmark instability does not automatically zero out performance `Gain`.
- Why: External provider drift should not masquerade as a code regression in the core keep or reset loop.
- Alternatives rejected: binding the Phase 1 reset decision directly to every shadow E2E fluctuation.

## D-017

- Decision: `runtime-state.md` uses `loop_status` as the single waiting-state source of truth, with `human_wait_reason` only as an explanatory field.
- Why: Parallel waiting flags create contradictory controller and observer reads.
- Alternatives rejected: keeping both `await_human` and `awaiting_human` as independent state signals.

## D-018

- Decision: Recorder does not own loop state and must not recursively log its own observation-maintenance actions.
- Why: Observation should describe the harness, not create a self-expanding meta-log.
- Alternatives rejected: letting Recorder co-own `runtime-state.md` or logging every logging write.

## D-019

- Decision: Candidate selection requires an explicit lifecycle with constrained status values.
- Why: `candidate_pool_empty`, novelty checks, and repeated-failure controls need mechanical candidate validity rules.
- Alternatives rejected: leaving candidate validity implicit in free-text notes.

## D-020

- Decision: Keep or reset must be decided by a fixed VSG evaluator script with structured output.
- Why: The conductor should consume one mechanical decision surface, not recompute `Gate` and `Gain` from scattered logs in working memory.
- Alternatives rejected: manual keep or reset judgment from raw verification artifacts.

## D-021

- Decision: When multiple implementations satisfy the Phase 1 control requirements, prefer the simplest one. Small incremental gains do not justify added operational or structural complexity.
- Why: Phase 1 needs a trustworthy runnable loop more than architectural completeness. Extra modules, states, and workflows increase failure surface and slow execution unless they deliver clear near-term value.
- Alternatives rejected: adding abstractions, roles, or infrastructure early to make the system look more complete without immediate loop value.
