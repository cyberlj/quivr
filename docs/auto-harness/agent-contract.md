# Agent Contract

This document defines the Phase 1 agent roles, responsibilities, and handoff rules.

## Design goal

No single agent should carry the whole loop in working memory.

The system uses narrow roles with repository-mediated handoffs.

## Roles

### Conductor

Responsibilities:

- choose the next candidate
- maintain strategic direction
- decide keep, reset, or re-plan
- maintain `current_best_commit`
- coordinate all other agents

Inputs:

- `active-plan.md`
- `round-plan.md`
- `plan-review.md`
- `experiment-ledger.tsv`
- `reflection-log.md`
- benchmark and test outputs

Outputs:

- next state transition
- updates to decision and execution records

### Planner

Responsibilities:

- draft the current round plan
- keep the round hypothesis narrow
- define exact verification commands

Inputs:

- strategic plan
- candidate record
- recent reflections

Outputs:

- `round-plan.md`

Planner does not approve its own plan.

### Plan Reviewer

Responsibilities:

- challenge the round plan before execution
- reject unclear, oversized, repeated, or unverifiable plans

Inputs:

- `round-plan.md`
- recent experiment and reflection history

Outputs:

- `plan-review.md`

Plan Reviewer does not edit code.

### Worker

Responsibilities:

- make the code changes allowed by the approved round plan

Inputs:

- approved `round-plan.md`
- allowed file list
- target code context

Outputs:

- code changes
- short change note

Worker does not decide keep, reset, or re-plan.

### Verifier

Responsibilities:

- run tests
- run the quality guard
- run the benchmark
- report structured results

Inputs:

- approved round plan
- current code state

Outputs:

- validation result with these fields:
  - `tests_passed`
  - `quality_guard_passed`
  - `benchmark_status`
  - `baseline_full_session_p50_ms`
  - `new_full_session_p50_ms`
  - `baseline_session_p90_ms`
  - `new_session_p90_ms`
  - `notes`

Verifier does not decide whether the result is strategically worth keeping.

### Reflector

Responsibilities:

- record why the round succeeded or failed
- write the `do_not_repeat` guidance
- identify whether re-plan is needed

Inputs:

- worker change note
- verifier result
- recent ledger entries

Outputs:

- reflection entry
- re-plan recommendation

## File ownership

Primary ownership by role:

- `active-plan.md` -> Conductor
- `round-plan.md` -> Planner
- `plan-review.md` -> Plan Reviewer
- code under `core/` -> Worker
- benchmark and validation output -> Verifier
- reflection log -> Reflector

Conductor integrates the final decision into the shared ledger.

## Handoff rule

Agents do not hand off by chat summary alone.

Required handoff surfaces are repository files and structured command output.

If a handoff is not written down, the next role should treat it as unreliable.

## Minimum runtime topology

Phase 1 minimum topology:

- 1 Conductor
- 1 Planner
- 1 Plan Reviewer
- 1 Worker
- 1 Verifier
- 1 Reflector

Some roles may run sequentially in the same session at first, but their responsibilities remain distinct.

## Separation rules

- Planner cannot approve its own plan
- Worker cannot self-certify a keep
- Verifier cannot overrule the quality gate
- Conductor cannot skip plan review
- Reflector cannot erase failed-round history
