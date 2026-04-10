# Quality Guard Spec

This document defines the quality gate for Phase 1.

## Purpose

Phase 1 is quality-first. A speed improvement is invalid if answer quality or multi-turn continuity regresses.

The quality guard is part of `Gate`, not part of `Gain`.

## Phase 1 strategy

Phase 1 uses deterministic assertions instead of LLM judge scoring.

Quality guard inputs are fixed and versioned:

- one fixed corpus definition
- one fixed multi-turn session script
- one fixed assertion set

## Assertion model

Each turn in the fixed session must define:

- `turn_id`
- `question`
- `required_facts`
- `forbidden_facts`
- `required_context_links`

### Required facts

Facts that must appear in the answer for the turn to pass.

### Forbidden facts

Facts or claims that must not appear.

### Required context links

Cross-turn references that prove the system preserved context correctly.

## Pass criteria

The quality guard passes only if all of the following are true:

- all required facts are present
- no forbidden fact appears
- required context links hold across turns
- answer structure remains parseable for the test harness

Phase 1 does not accept partial quality passes.

## Failure handling

If any turn fails its assertions:

- `quality_guard_passed = false`
- `Gate = 0`
- the round must reset

## Relationship to unit tests

Unit and integration tests verify code behavior.

The quality guard verifies that the fixed application-level session still behaves acceptably.

Both are required for `Gate = 1`.

## Phase 1 output contract

The quality guard runner must output at least:

- `session_id`
- `passed`
- `failed_turns`
- `missing_required_facts`
- `forbidden_fact_hits`
- `context_link_failures`

## Future extension

Phase 2 may add LLM judge scoring as a secondary signal, but Phase 1 uses deterministic assertions only.
