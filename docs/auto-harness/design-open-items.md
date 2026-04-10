# Auto Harness Design Open Items

This file is the system of record for unresolved design points in the current `quivr-auto-harness` design.

## Status

- `open`: identified, not yet designed
- `in_progress`: currently being designed
- `decided`: design decision made and recorded elsewhere
- `blocked`: cannot be decided yet because a prerequisite is missing

## Update rule

Whenever one item is resolved:

1. update its `status`
2. write the decision summary in `notes`
3. link the source document that now owns the rule
4. update `last_updated`

## Tracker

| id | topic | why it matters | status | next action | notes | last_updated |
| --- | --- | --- | --- | --- | --- | --- |
| D01 | Benchmark reproducibility | No stable benchmark means no trustworthy keep/reset decisions. | decided | Implement the corpus manifest and session script later. | Owned by `benchmark-spec.md`. Fixed corpus, fixed session, warmup, and repeat count are now defined. | 2026-04-10 |
| D02 | Benchmark statistics | Need one stable latency metric and aggregation rule for scoring. | decided | Implement the benchmark runner output contract. | Owned by `benchmark-spec.md`. Primary metric is `full_session_p50_ms` and guard metric is `session_p90_ms`. | 2026-04-10 |
| D03 | Quality guard assertions | Quality-first policy is meaningless without explicit pass/fail assertions. | decided | Implement the fixed session assertions. | Owned by `quality-guard-spec.md`. Deterministic multi-turn assertions define the hard quality gate. | 2026-04-10 |
| D04 | TODO closure standard | TODO work must have a hard completion rule or it will drift into easy keeps. | decided | Add candidate intake and TODO metadata in implementation. | Owned by `OPERATING_MODEL.md`. `P0`, `P1`, and `P2` rules are now defined. | 2026-04-10 |
| D05 | Candidate discovery | The conductor needs a repeatable way to discover performance items and blocking TODOs. | decided | Define the candidate intake file in a later pass. | Owned by `OPERATING_MODEL.md`. Allowed candidate sources and minimum fields are now defined. | 2026-04-10 |
| D06 | Re-plan thresholds | Continuous failed loops must trigger forced re-planning. | decided | Integrate thresholds into the loop state machine. | Owned by `OPERATING_MODEL.md`. Hard thresholds are now defined. | 2026-04-10 |
| D07 | Benchmark noise handling | Noisy runs can create false keep or false reset decisions. | decided | Implement rerun and invalid-result handling in the benchmark runner. | Owned by `OPERATING_MODEL.md` and `benchmark-spec.md`. Improvement under 5 percent is inconclusive, opposite reruns are noisy, p90 guard is enforced. | 2026-04-10 |
| D08 | Reset git semantics | Need a precise rule for what resets and what persists after a failed round. | decided | Document the exact reset command pattern later. | Owned by `OPERATING_MODEL.md`. Code resets, research memory persists. | 2026-04-10 |
| D09 | Multi-agent I/O contract | Agents need structured handoff or the loop will degrade into ambiguous context passing. | decided | Use the contract to guide future implementation. | Owned by `agent-contract.md`. Agent roles, ownership, and structured handoffs are now defined. | 2026-04-10 |
| D10 | Resource budget | Long-running autonomy needs fixed time and compute budgets per round. | decided | Tune budget values after implementation. | Owned by `OPERATING_MODEL.md`. Phase 1 hard budgets are now defined. | 2026-04-10 |
| D11 | Escalation policy | Need explicit rules for when execution must stop and report to the human. | decided | Refine with concrete execution commands later. | Owned by `OPERATING_MODEL.md`. Start gate and escalation cases are now defined. | 2026-04-10 |
| D12 | Phase completion criteria | Need a hard rule for when phase 1 harness is considered operational. | decided | Use these criteria to gate the first execution launch. | Owned by `OPERATING_MODEL.md`. Completion criteria are now defined. | 2026-04-10 |
| D13 | Two-layer planning and plan review | The loop needs a plan per round and an independent plan review step to avoid self-approval and drift. | decided | Use the planning model to guide future implementation. | Owned by `planning-model.md`. Strategic plan, round plan, plan review, and the revised loop are now defined. | 2026-04-10 |
| D14 | Durable current-best state | Keep and reset require a durable state file for `current_best_commit`. | decided | Use the runtime state file during implementation. | Owned by `runtime-state.md`. The baseline anchor is now repository state, not agent memory. | 2026-04-10 |
| D15 | Candidate registry | Candidate discovery and novelty checks require a structured registry. | decided | Use the registry during implementation. | Owned by `candidate-registry.tsv` and `OPERATING_MODEL.md`. Candidate identity and direction are now structured. | 2026-04-10 |
| D16 | Terminal loop states | The loop needs explicit empty, blocked, and human-wait states. | decided | Reflect these states in the runtime controller. | Owned by `runtime-state.md` and `OPERATING_MODEL.md`. Non-progress states are now explicit. | 2026-04-10 |
| D17 | Worktree execution model | Multi-agent execution needs a deterministic isolation model. | decided | Implement the worktree flow with the runtime controller. | Owned by `worktree-strategy.md`. Planning stays in the control worktree, code changes run in per-round worktrees. | 2026-04-10 |
| D18 | Repo-local agent router and role prompts | Agents need local routing, write-back duties, and fixed role prompts. | decided | Use these files as startup context during implementation. | Owned by `AGENTS.md` and `agent-prompts.md`. | 2026-04-10 |

## Notes

- There are no unresolved high-priority design items in the current tracker. New gaps should be added here as soon as they are discovered.
