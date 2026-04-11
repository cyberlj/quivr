# Auto Harness Operating Model

This document defines the control model for autonomous optimization in the current `quivr-auto-harness` repository.

## Scope

Phase 1 applies to:

- `core/quivr_core`
- `core/tests`
- `docs/auto-harness`

Default read-only areas:

- `docs/docs`
- `examples`
- dependency manifests
- public-facing root documentation

## Goal

Build a trustworthy autonomous research loop that can:

- improve performance for the target user scenario
- close only high-value TODO work
- keep or reset changes based on evidence
- preserve decision history, plans, and reflections in-repo

## Target scenario

Phase 1 optimizes for this application-level scenario:

- small teams
- local or lightweight vector storage
- knowledge base around 1 GB
- continuous multi-turn question answering
- answer quality is more important than raw speed

## North-star score

Each round is evaluated by:

`VSG = Gate x Gain`

The keep or reset decision must be produced by a fixed evaluator script.

The conductor must not compute `Gate` or `Gain` from scattered logs by ad hoc reasoning once the evaluator exists. It must read the evaluator's structured output.

### Gate

`Gate` is either `0` or `1`.

A round gets `Gate = 1` only if all of the following are true:

- related tests pass
- quality guard passes
- no crash or timeout occurs
- no obvious functional regression appears
- primary gain benchmark results are valid enough to compare
- shadow E2E smoke does not report a hard compatibility failure

Otherwise:

- `Gate = 0`
- the round must reset

### Gain

`Gain` depends on round type.

For TODO rounds:

- `Gain = 1` if the targeted `P0` or `P1` TODO is verifiably closed
- `Gain = 0` otherwise

For performance rounds:

`Gain = (baseline_full_session_p50_ms - new_full_session_p50_ms) / baseline_full_session_p50_ms`

For performance rounds, `Gain` is computed from the primary gain benchmark only.

Shadow E2E results are secondary signals. They may:

- confirm that the real user path still works
- raise warnings
- trigger review when they diverge sharply from the primary gain trend

They do not redefine the Phase 1 baseline by themselves.

## Keep and reset rules

- `Gate = 0` -> `reset`
- `Gate = 1` and `Gain <= 0` -> `reset`
- `Gate = 1` and `Gain > 0` -> `keep`
- `Gate = 1`, `Gain > 0`, but `session_p90_ms` regresses beyond the guard threshold -> `needs_review`, not an automatic keep
- `Gate = 1`, `Gain > 0`, but shadow E2E reports degraded compatibility or suspicious divergence -> `needs_review`, not an automatic keep

The evaluator script must return a structured decision with at least:

- `gate`
- `gain`
- `decision`
- `reason`
- `needs_review`

Decision values:

- `keep`
- `reset`
- `needs_review`

## Candidate classes

Phase 1 uses three TODO classes:

- `P0`: functional integrity TODO
- `P1`: research-blocking TODO
- `P2`: ordinary TODO

Only `P0` and `P1` may enter the active candidate pool.

Candidate pool layers:

- `Layer A`: performance candidates
- `Layer B`: `P0` and `P1` TODO candidates

Default priority goes to `Layer A`.

## Candidate sources

Performance candidates may come from:

- benchmark evidence
- trace or profile evidence
- prior reflections
- code hotspots in the active path

TODO candidates may come from:

- `TODO`, `FIXME`, or `HACK` comments in `core/`
- failing or skipped tests
- missing benchmark, quality, or observability pieces that block the loop

Every candidate must be recorded with:

- `candidate_id`
- `candidate_family`
- `direction`
- `type`
- `source`
- `target_path`
- `evidence`
- `verification`

These records live in:

- `docs/auto-harness/candidate-registry.tsv`

Candidate registry fields require controlled value sets.

- `status` allowed values:
  - `new`
  - `ready`
  - `active`
  - `kept`
  - `reset`
  - `blocked`
  - `exhausted`
  - `closed`
- `last_result` allowed values:
  - `none`
  - `keep`
  - `reset`
  - `inconclusive`
  - `noisy`
  - `blocked`
- `do_not_repeat` allowed values:
  - `none`
  - `round_only`
  - `direction`
  - `candidate`

A candidate is valid for selection only when:

- `status` is `new`, `ready`, or `reset`
- `do_not_repeat` is `none`
- it is not blocked by missing assets

If no valid candidates remain, the loop must enter `candidate_pool_empty` or `await_human`.

## Round loop

Each round must follow this control loop:

1. select one candidate
2. write the round plan
3. review the round plan
4. snapshot the current best state
5. make the code change
6. verify tests, quality, and benchmark
7. run the VSG evaluator
8. keep or reset
9. write reflection
10. continue or trigger re-plan

One round may pursue one hypothesis only.

No round may enter code change without an approved plan review.

No round may be kept or reset without an evaluator result.

## Current-best state

The system recognizes one code baseline as `current_best_commit`.

Rules:

- `current_best_commit` must be written to `runtime-state.md`
- each round starts from `current_best_commit`
- failed rounds reset code back to `current_best_commit`
- only successful rounds may advance `current_best_commit`
- research logs are never reset with code

`current_best_commit` is repository state, not conductor memory.

## Re-plan thresholds

The loop must stop and re-plan when any of these thresholds are reached:

- 3 consecutive failures in the same direction
- 5 total failures without a keep
- 2 consecutive inconclusive or noisy benchmark results
- 2 consecutive TODO keeps, after which the next round must return to performance work

These thresholds must be computed from structured ledger fields, not free-text notes.

## Noise handling

Benchmark policy:

- 1 warmup run
- 5 measured runs
- main comparison metric: `full_session_p50_ms`
- guard metric: `session_p90_ms`
- shadow E2E runs as a secondary observation layer

Benchmark result rules:

- absolute improvement below 5 percent -> `inconclusive`
- two reruns with opposite direction -> `noisy`
- p50 improves but p90 regresses by more than 15 percent -> `needs_review`
- shadow E2E instability alone does not rewrite the primary gain baseline

## Autonomy policy

Before the first live autonomous execution, the system must notify the human.

Once execution is approved, the loop should continue until manually interrupted, except for explicit escalation cases.

The loop also has terminal or waiting states:

- `candidate_pool_empty`
- `blocked`
- `await_human`

If there is no valid candidate to execute, the loop must enter one of these states instead of re-planning forever.

## Escalation cases

Execution must stop and report to the human if:

- the first live run is about to start
- 5 rounds fail without a keep
- benchmark validity collapses for 2 rounds in a row
- shadow E2E repeatedly fails in a way that suggests the real Kimi path is no longer trustworthy
- the candidate pool is empty
- the loop is blocked on missing information or missing assets
- the mutable surface must expand
- new dependencies are required
- public API or root documentation must change
- reset can no longer return to a safe code state

## Resource budget

Phase 1 hard budgets:

- max 30 minutes per round
- max 10 minutes for benchmark
- max 10 minutes for tests
- default concurrency: 2 agents

## Phase 1 completion

Phase 1 is operational only when all of the following are true:

- benchmark spec exists and is accepted
- quality guard spec exists and is accepted
- this operating model exists and is accepted
- at least 1 `P0` or `P1` TODO round has been kept
- at least 1 performance round has been kept
- at least 3 full rounds have been recorded
- at least 1 real reset has occurred successfully
- at least 1 re-plan has occurred successfully
