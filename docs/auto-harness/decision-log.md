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

- Decision: The application-level benchmark uses the real configured Kimi path for `Gain`, while quality gating remains deterministic.
- Why: Performance should reflect the real user path, but the hard quality gate must stay reproducible.
- Alternatives rejected: purely local benchmark as the primary signal, or LLM judge as the Phase 1 hard gate.

## D-009

- Decision: Code resets revert to `current_best_commit`, but research logs and design documents persist.
- Why: Failed rounds must not pollute the code baseline, but the system must keep its memory.
- Alternatives rejected: resetting documentation together with code.

## D-010

- Decision: Candidate pool uses layered priority with performance first and `P0`/`P1` TODOs second.
- Why: This protects the loop from drifting toward easy but low-value keeps.
- Alternatives rejected: one mixed pool for all work items.
