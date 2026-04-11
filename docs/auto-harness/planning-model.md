# Planning Model

This document defines the planning layer for the Phase 1 auto harness.

## Why planning is a hard gate

The loop must not rely on the conductor remembering what to do next.

Each round needs:

- a fresh round plan
- a separate plan review
- explicit permission to enter code change

Without this layer, the loop will drift toward self-approval, repeated failed ideas, and shallow reflections.

## Two-layer planning

Phase 1 uses two planning layers.

### Strategic plan

The strategic plan defines the current research direction.

It answers:

- what Phase 1 is trying to achieve
- what the current top priorities are
- what the active constraints are
- what the next unresolved design or execution risks are

Repository file:

- `docs/auto-harness/active-plan.md`

This file changes slowly. It should not be rewritten every round.

### Round plan

The round plan defines one experimental cycle.

It answers:

- which single hypothesis is being tested
- which files may change
- which tests and benchmark commands must run
- what success means
- what reset means
- what evidence would invalidate the idea
- which evaluator command will decide keep or reset

Repository file:

- `docs/auto-harness/round-plan.md`

This file must be rewritten or explicitly refreshed every round.

## Round plan required fields

Every round plan must include:

- `round_id`
- `candidate_id`
- `round_type`
- `hypothesis`
- `why_now`
- `allowed_files`
- `forbidden_files`
- `tests`
- `quality_guard`
- `benchmark`
- `vsg_evaluator`
- `success_rule`
- `reset_rule`
- `novelty_check`
- `candidate_family`
- `direction`
- `expected_risk`

If any field is missing, the round may not enter execution.

## Plan review

Every round plan must be reviewed by a separate agent before any code change begins.

Repository file:

- `docs/auto-harness/plan-review.md`

The review must answer:

- is the hypothesis single and testable
- is the change scope bounded
- is verification complete
- is keep or reset decidable from the planned evidence
- does this repeat a recently failed idea
- is this candidate worth doing now

The review must compare the round plan against:

- `candidate-registry.tsv`
- `experiment-ledger.tsv`
- `reflection-log.md`

The review must also confirm that the candidate is still valid for selection under the candidate lifecycle rules.

Allowed review outcomes:

- `approved`
- `revise`
- `reject`

Only `approved` may unlock execution.

## State transition rule

The loop state machine becomes:

1. select candidate
2. refresh strategic context if needed
3. write round plan
4. review round plan
5. snapshot current best state
6. execute change
7. verify
8. judge
9. keep or reset
10. reflect
11. continue or re-plan

No round may skip steps 3 or 4.

## Re-plan triggers

The system must return to planning if:

- the round plan is rejected
- the same direction failed 3 times
- benchmark validity becomes noisy twice in a row
- the active strategic plan no longer matches the best available evidence

If there are no valid candidates left, the system must not loop on re-plan. It must enter `candidate_pool_empty` or `await_human`.

## Candidate lifecycle

Candidates move through this lifecycle:

1. `new`
2. `ready`
3. `active`
4. one of:
   - `kept`
   - `reset`
   - `blocked`
   - `exhausted`
   - `closed`

Lifecycle rules:

- `new` -> `ready` after evidence and verification fields are complete
- `ready` -> `active` when selected for a round
- `active` -> `kept` when the round keeps
- `active` -> `reset` when the round resets but the direction is still retryable
- `reset` -> `ready` after reflection confirms the candidate remains retryable and the next round plan changes the approach enough to satisfy the novelty check
- `active` -> `blocked` when a prerequisite is missing
- `active` -> `exhausted` when repeated evidence says this direction should stop
- `kept` or `closed` candidates are not selectable again
- `exhausted` candidates are not selectable again unless a later decision log explicitly reopens them

## Memory rule

Strategic plan, round plan, and plan review are all repository memory.

They are not optional notes. They are control surfaces for the harness.
