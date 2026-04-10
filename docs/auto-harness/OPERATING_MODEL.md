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

### Gate

`Gate` is either `0` or `1`.

A round gets `Gate = 1` only if all of the following are true:

- related tests pass
- quality guard passes
- no crash or timeout occurs
- no obvious functional regression appears
- benchmark results are valid enough to compare

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

## Keep and reset rules

- `Gate = 0` -> `reset`
- `Gate = 1` and `Gain <= 0` -> `reset`
- `Gate = 1` and `Gain > 0` -> `keep`
- `Gate = 1`, `Gain > 0`, but `session_p90_ms` regresses beyond the guard threshold -> `needs_review`, not an automatic keep

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
- `type`
- `source`
- `target_path`
- `evidence`
- `verification`

## Round loop

Each round must follow this control loop:

1. select one candidate
2. write the round plan
3. review the round plan
4. snapshot the current best state
5. make the code change
6. verify tests, quality, and benchmark
7. score the round
8. keep or reset
9. write reflection
10. continue or trigger re-plan

One round may pursue one hypothesis only.

No round may enter code change without an approved plan review.

## Current-best state

The system recognizes one code baseline as `current_best_commit`.

Rules:

- each round starts from `current_best_commit`
- failed rounds reset code back to `current_best_commit`
- only successful rounds may advance `current_best_commit`
- research logs are never reset with code

## Re-plan thresholds

The loop must stop and re-plan when any of these thresholds are reached:

- 3 consecutive failures in the same direction
- 5 total failures without a keep
- 2 consecutive inconclusive or noisy benchmark results
- 2 consecutive TODO keeps, after which the next round must return to performance work

## Noise handling

Benchmark policy:

- 1 warmup run
- 5 measured runs
- main comparison metric: `full_session_p50_ms`
- guard metric: `session_p90_ms`

Benchmark result rules:

- absolute improvement below 5 percent -> `inconclusive`
- two reruns with opposite direction -> `noisy`
- p50 improves but p90 regresses by more than 15 percent -> `needs_review`

## Autonomy policy

Before the first live autonomous execution, the system must notify the human.

Once execution is approved, the loop should continue until manually interrupted, except for explicit escalation cases.

## Escalation cases

Execution must stop and report to the human if:

- the first live run is about to start
- 5 rounds fail without a keep
- benchmark validity collapses for 2 rounds in a row
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
