# Phase 1 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable Phase 1 auto harness for Quivr that executes one real round through machine state, per-agent manifests, execution worktree, deterministic verification, shadow E2E, and mechanical keep/reset.

**Architecture:** The implementation keeps `docs/auto-harness/` as the control plane, but moves machine truth into `docs/auto-harness/state/`. One controller owns the loop. One round gets one execution worktree and one writing worker. Verification is split into deterministic local gates and a real-provider shadow path. Policy is enforced through repo-local wrappers that read per-agent manifests.

**Tech Stack:** Python 3.11, `pydantic`, `pathlib`, `json`, `subprocess`, `tempfile`, `pytest`, existing Quivr test fixtures (`FakeListChatModel`, `DeterministicFakeEmbedding`, `InMemoryVectorStore`)

## Execution Status

Canonical progress, verified commands, blockers, and continuation point live in:

- `docs/auto-harness/state/execution-status.json`

---

## File Structure

### Create

- `core/quivr_core/auto_harness/__init__.py`
- `core/quivr_core/auto_harness/contracts.py`
- `core/quivr_core/auto_harness/state_store.py`
- `core/quivr_core/auto_harness/candidate_service.py`
- `core/quivr_core/auto_harness/planner.py`
- `core/quivr_core/auto_harness/reviewer.py`
- `core/quivr_core/auto_harness/worktree.py`
- `core/quivr_core/auto_harness/launcher.py`
- `core/quivr_core/auto_harness/doctor.py`
- `core/quivr_core/auto_harness/harness_docs_lint.py`
- `core/quivr_core/auto_harness/post_edit_check.py`
- `core/quivr_core/auto_harness/worker_runner.py`
- `core/quivr_core/auto_harness/verifier.py`
- `core/quivr_core/auto_harness/reflector.py`
- `core/quivr_core/auto_harness/recorder.py`
- `core/quivr_core/auto_harness/observer.py`
- `core/quivr_core/auto_harness/run_tests.py`
- `core/quivr_core/auto_harness/run_quality_guard.py`
- `core/quivr_core/auto_harness/run_benchmark.py`
- `core/quivr_core/auto_harness/run_shadow_e2e.py`
- `core/quivr_core/auto_harness/vsg.py`
- `core/quivr_core/auto_harness/render_views.py`
- `core/quivr_core/auto_harness/controller.py`
- `core/tests/auto_harness/__init__.py`
- `core/tests/auto_harness/test_contracts.py`
- `core/tests/auto_harness/test_state_store.py`
- `core/tests/auto_harness/test_candidate_service.py`
- `core/tests/auto_harness/test_planner.py`
- `core/tests/auto_harness/test_reviewer.py`
- `core/tests/auto_harness/test_worktree.py`
- `core/tests/auto_harness/test_launcher.py`
- `core/tests/auto_harness/test_doctor.py`
- `core/tests/auto_harness/test_harness_docs_lint.py`
- `core/tests/auto_harness/test_wrappers.py`
- `core/tests/auto_harness/test_post_edit_check.py`
- `core/tests/auto_harness/test_run_tests.py`
- `core/tests/auto_harness/test_run_quality_guard.py`
- `core/tests/auto_harness/test_run_benchmark.py`
- `core/tests/auto_harness/test_run_shadow_e2e.py`
- `core/tests/auto_harness/test_vsg.py`
- `core/tests/auto_harness/test_reflector.py`
- `core/tests/auto_harness/test_recorder.py`
- `core/tests/auto_harness/test_observer.py`
- `core/tests/auto_harness/test_controller.py`
- `core/scripts/auto_harness/edit_guard.sh`
- `core/scripts/auto_harness/execute_guard.sh`
- `core/scripts/auto_harness/keep_guard.sh`
- `core/scripts/auto_harness/finalize_guard.sh`
- `docs/auto-harness/state/.gitkeep`
- `docs/auto-harness/state/rounds/.gitkeep`
- `docs/auto-harness/rounds/.gitkeep`

### Modify

- `docs/auto-harness/candidate-registry.tsv`
- `docs/auto-harness/runtime-state.md`
- `docs/auto-harness/round-plan.md`
- `docs/auto-harness/plan-review.md`
- `docs/auto-harness/observer-summary.md`

## Task 1: Contracts And Machine State

**Files:**
- Create: `core/quivr_core/auto_harness/contracts.py`
- Create: `core/quivr_core/auto_harness/state_store.py`
- Create: `core/tests/auto_harness/test_contracts.py`
- Create: `core/tests/auto_harness/test_state_store.py`
- Create: `docs/auto-harness/state/.gitkeep`
- Create: `docs/auto-harness/state/rounds/.gitkeep`

- [ ] Define `RuntimeState`, `RoundState`, `AgentManifest`, `ReviewResult`, `VerifyResult`, `DecisionResult`, `ReflectionResult` in `contracts.py`.
- [ ] Use strict enums for:
  - `loop_status`
  - `review_outcome`
  - `decision`
  - `shadow_status`
- [ ] Implement JSON read/write helpers in `state_store.py` for:
  - runtime state
  - round state
  - agent manifest
  - review
  - verify
  - decision
  - reflection
  - recorder event
- [ ] Implement atomic write behavior: write temp file then replace.
- [ ] Add tests for:
  - invalid enum values fail validation
  - round and agent ids round-trip
  - timestamp and path fields preserve exactly
  - missing required fields fail
- [ ] Run:

```bash
cd core
uv run pytest tests/auto_harness/test_contracts.py tests/auto_harness/test_state_store.py -v
```

- [ ] Commit:

```bash
git add core/quivr_core/auto_harness/contracts.py core/quivr_core/auto_harness/state_store.py core/tests/auto_harness/test_contracts.py core/tests/auto_harness/test_state_store.py docs/auto-harness/state/.gitkeep docs/auto-harness/state/rounds/.gitkeep
git commit -m "feat(auto-harness): add contracts and state store"
```

## Task 2: Candidate Service And Bootstrap Registry

**Files:**
- Create: `core/quivr_core/auto_harness/candidate_service.py`
- Create: `core/tests/auto_harness/test_candidate_service.py`
- Modify: `docs/auto-harness/candidate-registry.tsv`

- [ ] Normalize candidate schema to:

```text
candidate_id	candidate_family	direction	candidate_class	source	target_path	evidence	verification	status	last_result	do_not_repeat	notes
```

- [ ] Seed bootstrap candidates:
  - `perf-history-001`
  - `perf-context-001`
  - `perf-langgraph-001`
  - `todo-blocker-001`
- [ ] Narrow bootstrap mutable surface at seed time:
  - `target_path` must be one of:
    - `core/quivr_core/rag/quivr_rag.py`
    - `core/quivr_core/rag/quivr_rag_langgraph.py`
  - planner-derived `allowed_files` must stay within the selected candidate `target_path`
- [ ] Implement candidate loading, filtering, and selection rules in `candidate_service.py`.
- [ ] Enforce:
  - only `new`, `ready`, `reset` are selectable
  - `do_not_repeat == none`
  - performance candidates win over TODO candidates
- [ ] Add tests for:
  - empty registry returns `None`
  - performance beats `P1`
  - blocked or exhausted candidates are skipped
  - repeated direction with `do_not_repeat=direction` is rejected
  - bootstrap candidates outside RAG hotspot files are rejected
- [ ] Run:

```bash
cd core
uv run pytest tests/auto_harness/test_candidate_service.py -v
```

- [ ] Commit:

```bash
git add core/quivr_core/auto_harness/candidate_service.py core/tests/auto_harness/test_candidate_service.py docs/auto-harness/candidate-registry.tsv
git commit -m "feat(auto-harness): add candidate service and bootstrap registry"
```

## Task 3: Planner, Reviewer, And Human View Rendering

**Files:**
- Create: `core/quivr_core/auto_harness/planner.py`
- Create: `core/quivr_core/auto_harness/reviewer.py`
- Create: `core/quivr_core/auto_harness/render_views.py`
- Create: `core/tests/auto_harness/test_planner.py`
- Create: `core/tests/auto_harness/test_reviewer.py`
- Modify: `docs/auto-harness/runtime-state.md`
- Modify: `docs/auto-harness/round-plan.md`
- Modify: `docs/auto-harness/plan-review.md`
- Modify: `docs/auto-harness/observer-summary.md`

- [ ] Split planning ownership cleanly:
  - Controller generates `round_id` and a minimal round seed only
  - Planner is the only writer of full `RoundState`
  - Reviewer never mutates `RoundState`
- [ ] Planner renders full `RoundState` from:
  - one selected candidate
  - current runtime state
  - controller-provided `round_id`
- [ ] Reviewer consumes:
  - `RoundState`
  - `candidate-registry.tsv`
  - `experiment-ledger.tsv`
  - `reflection-log.md`
  and emits `ReviewResult`.
- [ ] `render_views.py` renders Markdown from JSON state. Do not make Markdown authoritative.
- [ ] Enforce reviewer checks:
  - single hypothesis
  - bounded scope
  - commands present
  - novelty valid
  - no missing reset rule
  - candidate still valid under lifecycle rules
  - `revise` does not unlock execution
- [ ] Add tests for:
  - Planner is the only component that materializes full `RoundState`
  - round plans always include allowed files and command fields
  - reviewer rejects repeated direction
  - reviewer rejects empty verification commands
  - reviewer rejects a candidate blocked by registry lifecycle
  - reviewer can emit `revise` without forcing `await_human`
  - reviewer consumes ledger and reflection history, not only candidate metadata
  - render output contains round id and candidate id
- [ ] Run:

```bash
cd core
uv run pytest tests/auto_harness/test_planner.py tests/auto_harness/test_reviewer.py -v
```

- [ ] Commit:

```bash
git add core/quivr_core/auto_harness/planner.py core/quivr_core/auto_harness/reviewer.py core/quivr_core/auto_harness/render_views.py core/tests/auto_harness/test_planner.py core/tests/auto_harness/test_reviewer.py docs/auto-harness/runtime-state.md docs/auto-harness/round-plan.md docs/auto-harness/plan-review.md docs/auto-harness/observer-summary.md
git commit -m "feat(auto-harness): add planner reviewer and rendered views"
```

## Task 4: Worktree And Agent Launcher

**Files:**
- Create: `core/quivr_core/auto_harness/worktree.py`
- Create: `core/quivr_core/auto_harness/launcher.py`
- Create: `core/tests/auto_harness/test_worktree.py`
- Create: `core/tests/auto_harness/test_launcher.py`

- [ ] Implement worktree helpers:
  - create round worktree from `current_best_commit`
  - remove round worktree
  - verify worktree path exists
- [ ] Implement agent launcher that creates one manifest per agent and injects:
  - `ROUND_ID`
  - `AGENT_ID`
  - `AGENT_ROLE`
  - `AGENT_MANIFEST_PATH`
  - `WORKTREE_PATH`
- [ ] Make launcher the only allowed spawn path for execution agents.
- [ ] Encode wrapper-only execution:
  - Worker `allowed_commands` must point to repo-local wrapper entrypoints
  - Verifier `allowed_commands` must point to repo-local wrapper entrypoints
  - direct invocation of worker or verifier modules is not allowed from controller
- [ ] Enforce single writer for Phase 1:
  - only one Worker manifest per round
  - Verifier is read-only
- [ ] Add tests for:
  - unique `round_id` maps to unique worktree path
  - manifest paths differ by agent id
  - Worker and Verifier get different permissions
  - Worker `allowed_commands` resolve only to wrapper entrypoints
  - launcher rejects manifests that expose direct unrestricted module execution
  - worktree cleanup removes only round worktree
- [ ] Run:

```bash
cd core
uv run pytest tests/auto_harness/test_worktree.py tests/auto_harness/test_launcher.py -v
```

- [ ] Commit:

```bash
git add core/quivr_core/auto_harness/worktree.py core/quivr_core/auto_harness/launcher.py core/tests/auto_harness/test_worktree.py core/tests/auto_harness/test_launcher.py
git commit -m "feat(auto-harness): add worktree and agent launcher"
```

## Task 5: Wrapper Guards

**Files:**
- Create: `core/scripts/auto_harness/edit_guard.sh`
- Create: `core/scripts/auto_harness/execute_guard.sh`
- Create: `core/scripts/auto_harness/keep_guard.sh`
- Create: `core/scripts/auto_harness/finalize_guard.sh`
- Create: `core/quivr_core/auto_harness/post_edit_check.py`
- Create: `core/tests/auto_harness/test_wrappers.py`
- Create: `core/tests/auto_harness/test_post_edit_check.py`

- [ ] `edit_guard.sh` reads `AGENT_MANIFEST_PATH` and blocks writes outside `allowed_files`.
- [ ] `execute_guard.sh` blocks execution when:
  - `review.json` missing
  - `review_outcome != approved`
  - manifest does not allow the command
- [ ] `keep_guard.sh` blocks keep when:
  - `verify.json` missing
  - `decision.json` missing
  - shadow success has no matching API event id
- [ ] `finalize_guard.sh` blocks round completion when:
  - `reflection.json` missing
  - round archive is incomplete
- [ ] `post_edit_check.py` runs immediately after worker execution and before verifier.
- [ ] `post_edit_check.py` checks:
  - `py_compile`
  - target module import smoke
  - no edits outside `allowed_files`
  - round state schema still validates
- [ ] Treat wrappers as mandatory execution surfaces, not optional utilities.
- [ ] Expose one wrapper entry per execution role:
  - worker wrapper
  - verifier wrapper
  - keep wrapper
  - finalize wrapper
- [ ] Add tests using subprocess calls that assert non-zero exit for invalid states.
- [ ] Add tests for:
  - post-edit failure blocks verifier handoff
  - changed file outside manifest scope fails fast
- [ ] Run:

```bash
cd core
uv run pytest tests/auto_harness/test_wrappers.py tests/auto_harness/test_post_edit_check.py -v
```

- [ ] Commit:

```bash
git add core/scripts/auto_harness/edit_guard.sh core/scripts/auto_harness/execute_guard.sh core/scripts/auto_harness/keep_guard.sh core/scripts/auto_harness/finalize_guard.sh core/quivr_core/auto_harness/post_edit_check.py core/tests/auto_harness/test_wrappers.py core/tests/auto_harness/test_post_edit_check.py
git commit -m "feat(auto-harness): add wrapper guards"
```

## Task 5A: Doctor And Resume Surface

**Files:**
- Create: `core/quivr_core/auto_harness/doctor.py`
- Create: `core/tests/auto_harness/test_doctor.py`

- [ ] Implement `doctor.py` as a read-only startup and recovery entrypoint.
- [ ] `doctor.py` reports:
  - `loop_status`
  - `active_round`
  - `current_best_commit`
  - candidate pool summary
  - missing environment requirements
  - recommended next command
- [ ] `doctor.py` must not mutate runtime state or round state.
- [ ] Add tests for:
  - missing provider env is surfaced as readiness issue
  - active round is reported from runtime state
  - no-write mode is enforced
- [ ] Run:

```bash
cd core
uv run pytest tests/auto_harness/test_doctor.py -v
```

- [ ] Commit:

```bash
git add core/quivr_core/auto_harness/doctor.py core/tests/auto_harness/test_doctor.py
git commit -m "feat(auto-harness): add doctor and resume surface"
```

## Task 5B: Docs Lint

**Files:**
- Create: `core/quivr_core/auto_harness/harness_docs_lint.py`
- Create: `core/tests/auto_harness/test_harness_docs_lint.py`

- [ ] Implement a minimal `docs_lint` for `docs/auto-harness/`.
- [ ] Enforce only these checks in Phase 1:
  - ownership consistency across design and contract docs
  - review outcome semantics are consistent
  - round archive layout is consistent
  - recorder / verifier / controller write boundaries are consistent
- [ ] Keep `docs_lint` narrow. Do not turn it into a general doc style checker.
- [ ] Add tests for:
  - mismatched ownership fails
  - mismatched archive layout fails
  - mismatched review state semantics fail
- [ ] Run:

```bash
cd core
uv run pytest tests/auto_harness/test_harness_docs_lint.py -v
```

- [ ] Commit:

```bash
git add core/quivr_core/auto_harness/harness_docs_lint.py core/tests/auto_harness/test_harness_docs_lint.py
git commit -m "feat(auto-harness): add docs lint"
```

## Task 6: Worker Runner Contract

**Files:**
- Create: `core/quivr_core/auto_harness/worker_runner.py`
- Create: `core/tests/auto_harness/test_worker_runner.py`

- [ ] Define `worker_runner.py` as the only code-writing execution module.
- [ ] Inputs:
  - `ROUND_ID`
  - `AGENT_ID`
  - `AGENT_MANIFEST_PATH`
  - `WORKTREE_PATH`
- [ ] Outputs:
  - `change_note.json`
  - structured tool usage handoff for `tool-log.jsonl`
- [ ] Enforce:
  - writes only inside execution worktree
  - edits only allowed files
  - no direct keep/reset/state mutation
- [ ] Add tests for:
  - missing manifest fails fast
  - edit outside `allowed_files` is rejected
  - successful run writes `change_note.json`
  - worker cannot write `runtime-state.json`
- [ ] Run:

```bash
cd core
uv run pytest tests/auto_harness/test_worker_runner.py -v
```

- [ ] Commit:

```bash
git add core/quivr_core/auto_harness/worker_runner.py core/tests/auto_harness/test_worker_runner.py
git commit -m "feat(auto-harness): add worker runner contract"
```

## Task 7: Deterministic Test Runner And Quality Guard

**Files:**
- Create: `core/quivr_core/auto_harness/run_tests.py`
- Create: `core/quivr_core/auto_harness/run_quality_guard.py`
- Create: `core/tests/auto_harness/test_run_tests.py`
- Create: `core/tests/auto_harness/test_run_quality_guard.py`

- [ ] `run_tests.py` executes the round's fixed related test command and emits structured JSON fields.
- [ ] `run_quality_guard.py` uses:
  - `DeterministicFakeEmbedding`
  - `FakeListChatModel`
  - `InMemoryVectorStore`
  - fixed small corpus
  - fixed multi-turn session
  - fixed assertions
- [ ] Do not depend on remote providers in this layer.
- [ ] Explicitly set round-local storage env vars before quality execution:
  - `QUIVR_LOCAL_STORAGE=<worktree>/.runtime/storage`
- [ ] Add tests for:
  - failing tests produce `tests_passed=false`
  - required facts and forbidden facts are enforced
  - context link failures are reported
- [ ] Run:

```bash
cd core
uv run pytest tests/auto_harness/test_run_tests.py tests/auto_harness/test_run_quality_guard.py -v
```

- [ ] Commit:

```bash
git add core/quivr_core/auto_harness/run_tests.py core/quivr_core/auto_harness/run_quality_guard.py core/tests/auto_harness/test_run_tests.py core/tests/auto_harness/test_run_quality_guard.py
git commit -m "feat(auto-harness): add deterministic test and quality runners"
```

## Task 8: Deterministic Primary Benchmark

**Files:**
- Create: `core/quivr_core/auto_harness/run_benchmark.py`
- Create: `core/tests/auto_harness/test_run_benchmark.py`

- [ ] Build the primary benchmark on deterministic local paths only.
- [ ] Measure:
  - `full_session_p50_ms`
  - `session_p90_ms`
  - `first_turn_p50_ms`
  - `avg_turn_p50_ms`
- [ ] Use fixed corpus and fake LLM path. Do not include real provider latency.
- [ ] Set round-local storage and temp dirs before benchmark execution.
- [ ] Add tests for:
  - warmup is excluded
  - five measured runs are aggregated
  - invalid runs return `status != valid`
- [ ] Run:

```bash
cd core
uv run pytest tests/auto_harness/test_run_benchmark.py -v
```

- [ ] Commit:

```bash
git add core/quivr_core/auto_harness/run_benchmark.py core/tests/auto_harness/test_run_benchmark.py
git commit -m "feat(auto-harness): add deterministic primary benchmark"
```

## Task 9: Real Shadow E2E

**Files:**
- Create: `core/quivr_core/auto_harness/run_shadow_e2e.py`
- Create: `core/tests/auto_harness/test_run_shadow_e2e.py`

- [ ] Resolve provider config from environment.
- [ ] On missing provider config, emit `shadow_status=skipped_env_missing`.
- [ ] On real execution, emit one normalized API summary payload for the recorder.
- [ ] `shadow_status=success` is only valid when an API event id is present in the result payload.
- [ ] Add tests for:
  - missing env returns `skipped_env_missing`
  - fake success without API event is rejected
  - result contains model name and endpoint label
- [ ] Run:

```bash
cd core
uv run pytest tests/auto_harness/test_run_shadow_e2e.py -v
```

- [ ] Commit:

```bash
git add core/quivr_core/auto_harness/run_shadow_e2e.py core/tests/auto_harness/test_run_shadow_e2e.py
git commit -m "feat(auto-harness): add shadow e2e runner"
```

## Task 10: Verifier And VSG

**Files:**
- Create: `core/quivr_core/auto_harness/verifier.py`
- Create: `core/quivr_core/auto_harness/vsg.py`
- Create: `core/tests/auto_harness/test_vsg.py`

- [ ] `verifier.py` orchestrates:
  - `run_tests.py`
  - `run_quality_guard.py`
  - `run_benchmark.py`
  - `run_shadow_e2e.py`
- [ ] `verifier.py` emits structured handoff only:
  - `verify.json`
  - benchmark summary payload
  - tool usage summary payload
  - API summary payload
- [ ] Keep durable write ownership out of verifier:
  - do not append `experiment-ledger.tsv`
  - do not append `tool-log.jsonl`
  - do not append `api-log.jsonl`
- [ ] `vsg.py` consumes only structured verifier output.
- [ ] Enforce:
  - no ad hoc recompute from raw logs
  - `needs_review` on p90 guard breach
  - `needs_review` or `await_human` on shadow incompatibility
- [ ] Add tests for:
  - gate zero on failed tests
  - gate zero on failed quality
  - gain computed from baseline and new p50 only
  - shadow failure does not rewrite primary gain but does block compatibility claim
- [ ] Run:

```bash
cd core
uv run pytest tests/auto_harness/test_vsg.py -v
```

- [ ] Commit:

```bash
git add core/quivr_core/auto_harness/verifier.py core/quivr_core/auto_harness/vsg.py core/tests/auto_harness/test_vsg.py
git commit -m "feat(auto-harness): add verifier and vsg evaluator"
```

## Task 11: Reflector, Recorder, And Observer

**Files:**
- Create: `core/quivr_core/auto_harness/reflector.py`
- Create: `core/quivr_core/auto_harness/recorder.py`
- Create: `core/quivr_core/auto_harness/observer.py`
- Create: `core/tests/auto_harness/test_reflector.py`
- Create: `core/tests/auto_harness/test_recorder.py`
- Create: `core/tests/auto_harness/test_observer.py`

- [ ] Implement `reflector.py` as a first-class post-decision step.
- [ ] Inputs:
  - worker change note
  - verifier result
  - recent ledger entries
  - current candidate lifecycle state
- [ ] Outputs:
  - `reflection.json`
  - `reflection-log.md` entry
  - re-plan recommendation
- [ ] Implement `recorder.py` as the only writer for:
  - `event-log.jsonl`
  - `tool-log.jsonl`
  - `api-log.jsonl`
- [ ] Implement `observer.py` as a minimal post-round health summarizer.
- [ ] `observer.py` refreshes `observer-summary.md` from durable repo facts only.
- [ ] Phase 1 observer only reports:
  - recent keep/reset ratio
  - repeated failure class
  - `candidate_pool_empty` / `await_human`
  - shadow health
- [ ] Recorder consumes structured handoffs only:
  - controller runtime transition payloads
  - worker tool usage payloads
  - verifier API summary payloads
- [ ] Add tests for:
  - missing verifier result blocks reflection
  - reflection is required after both keep and reset
  - recorder appends one normalized event per handoff
  - recorder does not double-write on repeated controller invocation
  - observer refreshes summary after repeated resets
- [ ] Run:

```bash
cd core
uv run pytest tests/auto_harness/test_reflector.py tests/auto_harness/test_recorder.py tests/auto_harness/test_observer.py -v
```

- [ ] Commit:

```bash
git add core/quivr_core/auto_harness/reflector.py core/quivr_core/auto_harness/recorder.py core/quivr_core/auto_harness/observer.py core/tests/auto_harness/test_reflector.py core/tests/auto_harness/test_recorder.py core/tests/auto_harness/test_observer.py
git commit -m "feat(auto-harness): add reflector recorder and observer"
```

## Task 12: Controller, Failure Paths, And Durable Write-Backs

**Files:**
- Create: `core/quivr_core/auto_harness/controller.py`
- Create: `core/tests/auto_harness/test_controller.py`
- Create: `docs/auto-harness/rounds/.gitkeep`

- [ ] Implement the only allowed `--once` flow:
  1. load runtime state
  2. select candidate
  3. generate unique round id
  4. persist round seed only
  5. launch planner
  6. persist planner-produced full round state
  7. launch reviewer
  8. if approved, create execution worktree
  9. launch worker through wrapper-only path
  10. launch verifier through wrapper-only path
  11. run VSG
  12. keep/reset
  13. launch reflector
  14. update candidate lifecycle
  15. append ledger and recorder surfaces through owned roles
  16. launch observer
  17. archive round
  18. render human views
  19. cleanup worktree
- [ ] Do not allow:
  - fixed `r-0001`
  - `tests_passed=True` placeholders
  - `current_best_commit` staying unchanged on keep
- [ ] Controller owns shared control-plane write-backs for:
  - `runtime-state.md`
  - `candidate-registry.tsv`
  - `experiment-ledger.tsv`
- [ ] Controller does not directly append:
  - `reflection-log.md`
  - `event-log.jsonl`
  - `tool-log.jsonl`
  - `api-log.jsonl`
- [ ] Candidate lifecycle write-back must be mechanical:
  - selected candidate `ready -> active`
  - keep outcome `active -> kept`
  - reset outcome `active -> reset`
  - blocked prerequisite `active -> blocked`
  - exhausted direction `active -> exhausted`
- [ ] `review_outcome=revise` must return to planning without execution and without defaulting to `await_human`.
- [ ] `review_outcome=reject` triggers re-plan unless candidate pool is exhausted or a hard stop condition is present.
- [ ] Add explicit failure-path handling for:
  - review rejected
  - review revise
  - worker crash
  - wrapper rejection
  - verifier partial failure
  - interrupted round after worktree creation
- [ ] Enforce cleanup on every exit path:
  - failed review before worktree means no worktree created
  - failed worker/verifier after worktree creation means worktree removed
  - durable logs remain
- [ ] Add tests for:
  - unique round ids across consecutive runs
  - candidate pool empty moves to `candidate_pool_empty`
  - review `revise` returns to planning without execution
  - rejected review returns to re-plan path without execution
  - worker crash records failure and cleans worktree
  - wrapper rejection records failure and cleans worktree
  - verifier failure records partial state and cleans worktree
  - keep advances `current_best_commit`
  - reset preserves previous baseline
  - `needs_review` moves to `await_human`
  - candidate lifecycle is written back after keep and reset
  - observer summary refreshes after round completion
  - required write-backs are updated after round completion
- [ ] Run:

```bash
cd core
uv run pytest tests/auto_harness/test_controller.py -v
```

- [ ] Commit:

```bash
git add core/quivr_core/auto_harness/controller.py core/tests/auto_harness/test_controller.py docs/auto-harness/rounds/.gitkeep
git commit -m "feat(auto-harness): add phase1 mvp controller"
```

## Task 13: Dry Run Acceptance

**Files:**
- Modify: `docs/auto-harness/runtime-state.md`
- Modify: `docs/auto-harness/round-plan.md`
- Modify: `docs/auto-harness/plan-review.md`
- Modify: `docs/auto-harness/observer-summary.md`

- [ ] Run the read-only startup checks:

```bash
cd core
uv run python -m quivr_core.auto_harness.doctor
uv run python -m quivr_core.auto_harness.harness_docs_lint
```

- [ ] Run one full dry-run:

```bash
cd core
uv run python -m quivr_core.auto_harness.controller --once
```

- [ ] Until real keep integration exists, dry-run acceptance must use a dry-run-safe keep policy that does not write a synthetic commit into `current_best_commit`.
- [ ] Real keep integration remains required after Task 13 so a future keep writes an actual integrated commit hash back to runtime state.

- [ ] Verify all of these exist:
  - `docs/auto-harness/state/runtime-state.json`
  - `docs/auto-harness/state/rounds/<round_id>/round.json`
  - `docs/auto-harness/state/rounds/<round_id>/agents/worker-1.json`
  - `docs/auto-harness/state/rounds/<round_id>/review.json`
  - `docs/auto-harness/state/rounds/<round_id>/verify.json`
  - `docs/auto-harness/state/rounds/<round_id>/decision.json`
  - `docs/auto-harness/state/rounds/<round_id>/reflection.json`
  - `docs/auto-harness/rounds/<round_id>/plan.md`
  - `docs/auto-harness/rounds/<round_id>/plan-review.md`
  - `docs/auto-harness/rounds/<round_id>/verify.md`
  - `docs/auto-harness/rounds/<round_id>/decision.md`
  - `docs/auto-harness/rounds/<round_id>/reflection.md`
  - `docs/auto-harness/rounds/<round_id>/artifacts.json`
  - `docs/auto-harness/rounds/<round_id>/summary.md`
- [ ] Verify the worktree was created and removed.
- [ ] Verify markdown views were rendered from JSON state.
- [ ] Verify durable write-backs happened:
  - `docs/auto-harness/experiment-ledger.tsv`
  - `docs/auto-harness/reflection-log.md`
  - `docs/auto-harness/event-log.jsonl`
  - `docs/auto-harness/tool-log.jsonl`
  - `docs/auto-harness/api-log.jsonl`
  - `docs/auto-harness/candidate-registry.tsv`
  - `docs/auto-harness/observer-summary.md`
- [ ] Commit:

```bash
git add docs/auto-harness/runtime-state.md docs/auto-harness/round-plan.md docs/auto-harness/plan-review.md docs/auto-harness/observer-summary.md
git commit -m "test(auto-harness): validate phase1 mvp dry run"
```

## Final Acceptance Criteria

- [ ] One real round can run end-to-end from controller entry
- [ ] Runtime state is JSON-first
- [ ] `doctor` can restore operator context without mutating state
- [ ] `docs_lint` keeps design and plan semantics aligned
- [ ] Planner, Reviewer, Worker, Verifier are launched through manifests
- [ ] Reflector and Recorder have first-class execution and ownership boundaries
- [ ] Observer remains minimal and read-only
- [ ] Single writer per round is enforced
- [ ] Worker cannot edit outside `allowed_files`
- [ ] Worker changes are screened by L0 post-edit checks before verifier
- [ ] No approved review means no execution
- [ ] Planner is the only writer of full round state
- [ ] Controller and launcher can only reach execution roles through wrapper entrypoints
- [ ] No `verify.json` or `decision.json` means no keep
- [ ] No `reflection.json` means no finalize
- [ ] Shadow success requires a real API event
- [ ] Review rejection, worker crash, wrapper rejection, and verifier failure all clean up correctly
- [ ] `candidate-registry.tsv`, `experiment-ledger.tsv`, `reflection-log.md`, `event-log.jsonl`, `tool-log.jsonl`, and `api-log.jsonl` are updated through their owning roles on every completed round
- [ ] Round archive contains `plan.md`, `plan-review.md`, `verify.md`, `decision.md`, `reflection.md`, and `artifacts.json`
- [ ] Review outcome `revise` returns to planning without unnecessary human escalation
- [ ] Keep advances `current_best_commit`
- [ ] Reset leaves baseline unchanged and preserves round history
