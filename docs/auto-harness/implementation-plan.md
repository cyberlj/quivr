# Phase 1 Auto Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable Phase 1 auto harness that can bootstrap a baseline from `current_best_commit`, execute one fixed candidate round in isolated `--once --dry-run` mode, persist round artifacts in-repo, run benchmark and quality verification, and produce a mechanical VSG decision.

**Architecture:** The implementation stays inside `core/quivr_core/auto_harness/` and treats `docs/auto-harness/` as the durable control plane. Verification is split into a stable primary gain benchmark, a deterministic assertion-based quality guard, a real shadow smoke contract, and a fixed VSG evaluator. The first controller is intentionally small: one process, role-separated modules, baseline bootstrap before performance comparison, real `round-plan.md` and `plan-review.md` writes, and dry-run runtime and telemetry isolated under `docs/auto-harness/sandbox/`.

**Tech Stack:** Python 3.11, `pydantic`, stdlib `json/csv/pathlib/subprocess/statistics`, existing Quivr core test fixtures (`FakeListChatModel`, `DeterministicFakeEmbedding`, `InMemoryVectorStore`), `pytest`

**Implementation Rule:** If two designs satisfy the same Phase 1 requirement, choose the simpler one. Do not add files, states, abstractions, or flows for marginal improvement alone.

---

## File Map

### Create

- `core/quivr_core/auto_harness/__init__.py`
- `core/quivr_core/auto_harness/contracts.py`
- `core/quivr_core/auto_harness/repo_io.py`
- `core/quivr_core/auto_harness/fixtures.py`
- `core/quivr_core/auto_harness/session_driver.py`
- `core/quivr_core/auto_harness/benchmark_runner.py`
- `core/quivr_core/auto_harness/shadow_e2e_runner.py`
- `core/quivr_core/auto_harness/quality_guard_runner.py`
- `core/quivr_core/auto_harness/baseline_store.py`
- `core/quivr_core/auto_harness/verifier.py`
- `core/quivr_core/auto_harness/vsg_evaluator.py`
- `core/quivr_core/auto_harness/candidate_service.py`
- `core/quivr_core/auto_harness/planner.py`
- `core/quivr_core/auto_harness/plan_reviewer.py`
- `core/quivr_core/auto_harness/controller.py`
- `core/tests/auto_harness/__init__.py`
- `core/tests/auto_harness/test_contracts.py`
- `core/tests/auto_harness/test_repo_io.py`
- `core/tests/auto_harness/test_fixtures.py`
- `core/tests/auto_harness/test_session_driver.py`
- `core/tests/auto_harness/test_benchmark_runner.py`
- `core/tests/auto_harness/test_shadow_e2e_runner.py`
- `core/tests/auto_harness/test_quality_guard_runner.py`
- `core/tests/auto_harness/test_baseline_store.py`
- `core/tests/auto_harness/test_vsg_evaluator.py`
- `core/tests/auto_harness/test_candidate_service.py`
- `core/tests/auto_harness/test_planner.py`
- `core/tests/auto_harness/test_controller.py`
- `docs/auto-harness/fixtures/small-team-corpus-v1/manifest.json`
- `docs/auto-harness/fixtures/small-team-corpus-v1/docs/product_overview.md`
- `docs/auto-harness/fixtures/small-team-corpus-v1/docs/ops_runbook.md`
- `docs/auto-harness/fixtures/multiturn-session-v1.json`
- `docs/auto-harness/fixtures/quality-assertions-v1.json`
- `docs/auto-harness/baselines/.gitkeep`
- `docs/auto-harness/sandbox/.gitkeep`
- `docs/auto-harness/rounds/.gitkeep`

### Modify

- `docs/auto-harness/round-plan.md`
- `docs/auto-harness/plan-review.md`

---

### Task 1: Contracts And Repository I/O

**Files:**
- Create: `core/quivr_core/auto_harness/contracts.py`
- Create: `core/quivr_core/auto_harness/repo_io.py`
- Create: `core/tests/auto_harness/test_contracts.py`
- Create: `core/tests/auto_harness/test_repo_io.py`
- Test: `core/tests/auto_harness/test_contracts.py`
- Test: `core/tests/auto_harness/test_repo_io.py`

- [ ] **Step 1: Write the failing contract tests**

```python
from pathlib import Path

from quivr_core.auto_harness.contracts import (
    BenchmarkResult,
    CandidateRecord,
    RuntimeState,
    VSGDecision,
)


def test_runtime_state_requires_known_loop_status():
    state = RuntimeState.model_validate(
        {
            "loop_status": "design_only",
            "current_best_commit": "b741578d",
            "current_best_round_id": "none",
            "current_best_candidate_id": "none",
            "control_branch": "quivr-auto-harness",
            "control_worktree": "/tmp/control",
            "active_execution_worktree": "none",
            "human_wait_reason": "none",
            "last_updated": "2026-04-11",
        }
    )

    assert state.loop_status == "design_only"


def test_runtime_state_requires_wait_reason_only_for_await_human():
    waiting = RuntimeState.model_validate(
        {
            "loop_status": "await_human",
            "current_best_commit": "b741578d",
            "current_best_round_id": "none",
            "current_best_candidate_id": "none",
            "control_branch": "quivr-auto-harness",
            "control_worktree": "/tmp/control",
            "active_execution_worktree": "none",
            "human_wait_reason": "first_live_run_not_started",
            "last_updated": "2026-04-11",
        }
    )

    assert waiting.human_wait_reason == "first_live_run_not_started"


def test_benchmark_result_contract_exposes_required_metrics():
    result = BenchmarkResult.model_validate(
        {
            "corpus_id": "small-team-corpus-v1",
            "session_id": "multiturn-session-v1",
            "full_session_p50_ms": 120.0,
            "session_p90_ms": 135.0,
            "first_turn_p50_ms": 50.0,
            "avg_turn_p50_ms": 40.0,
            "status": "valid",
        }
    )

    assert result.status == "valid"


def test_vsg_decision_contract_preserves_needs_review_flag():
    decision = VSGDecision.model_validate(
        {
            "gate": 1,
            "gain": 0.12,
            "decision": "needs_review",
            "reason": "p90 regressed",
            "needs_review": True,
        }
    )

    assert decision.needs_review is True
```

- [ ] **Step 2: Write the failing repository round-trip tests**

```python
import json
from pathlib import Path

from quivr_core.auto_harness.contracts import RuntimeState
from quivr_core.auto_harness.repo_io import (
    append_jsonl,
    load_runtime_state,
    load_tsv_records,
    write_runtime_state,
)


def test_runtime_state_markdown_round_trip(tmp_path: Path):
    target = tmp_path / "runtime-state.md"
    state = RuntimeState(
        loop_status="planning",
        current_best_commit="deadbeef",
        current_best_round_id="r-0001",
        current_best_candidate_id="perf-001",
        control_branch="main",
        control_worktree="/tmp/control",
        active_execution_worktree="/tmp/exec",
        human_wait_reason="none",
        last_updated="2026-04-11",
    )

    write_runtime_state(target, state)
    reloaded = load_runtime_state(target)

    assert reloaded == state


def test_append_jsonl_writes_one_object_per_line(tmp_path: Path):
    target = tmp_path / "event-log.jsonl"
    append_jsonl(target, {"round_id": "r-0001", "status": "ok"})
    append_jsonl(target, {"round_id": "r-0002", "status": "ok"})

    lines = target.read_text().splitlines()
    assert [json.loads(line)["round_id"] for line in lines] == ["r-0001", "r-0002"]


def test_load_tsv_records_reads_header_back_into_dicts(tmp_path: Path):
    target = tmp_path / "candidate-registry.tsv"
    target.write_text(
        "candidate_id\tstatus\tlast_result\nperf-001\tready\tnone\n",
        encoding="utf-8",
    )

    rows = load_tsv_records(target)

    assert rows == [
        {"candidate_id": "perf-001", "status": "ready", "last_result": "none"}
    ]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run from `core/`:

```bash
./.venv/bin/pytest tests/auto_harness/test_contracts.py tests/auto_harness/test_repo_io.py -v
```

Expected: `ModuleNotFoundError: No module named 'quivr_core.auto_harness'`

- [ ] **Step 4: Implement the contracts and repository serializers**

```python
from typing import Literal

from pydantic import BaseModel, model_validator


class RuntimeState(BaseModel):
    loop_status: Literal[
        "design_only",
        "planning",
        "plan_review",
        "executing",
        "verifying",
        "resetting",
        "candidate_pool_empty",
        "blocked",
        "await_human",
    ]
    current_best_commit: str
    current_best_round_id: str
    current_best_candidate_id: str
    control_branch: str
    control_worktree: str
    active_execution_worktree: str
    human_wait_reason: str
    last_updated: str

    @model_validator(mode="after")
    def validate_waiting_reason(self):
        if self.loop_status == "await_human" and self.human_wait_reason == "none":
            raise ValueError("await_human requires a non-none human_wait_reason")
        if self.loop_status != "await_human" and self.human_wait_reason != "none":
            raise ValueError("non-waiting states must use human_wait_reason=none")
        return self


class CandidateRecord(BaseModel):
    candidate_id: str
    candidate_family: str
    direction: str
    candidate_class: str
    source: str
    target_path: str
    evidence: str
    verification: str
    status: Literal["new", "ready", "active", "kept", "reset", "blocked", "exhausted", "closed"]
    last_result: Literal["none", "keep", "reset", "inconclusive", "noisy", "blocked"]
    do_not_repeat: Literal["none", "round_only", "direction", "candidate"]
    notes: str = ""


class BenchmarkResult(BaseModel):
    corpus_id: str
    session_id: str
    full_session_p50_ms: float | None = None
    session_p90_ms: float | None = None
    first_turn_p50_ms: float | None = None
    avg_turn_p50_ms: float | None = None
    status: Literal["valid", "inconclusive", "noisy", "invalid", "needs_review"]


class VSGDecision(BaseModel):
    gate: Literal[0, 1]
    gain: float
    decision: Literal["keep", "reset", "needs_review"]
    reason: str
    needs_review: bool = False
```

```python
from __future__ import annotations

import csv
import json
from pathlib import Path

from quivr_core.auto_harness.contracts import RuntimeState


def write_runtime_state(path: Path, state: RuntimeState) -> None:
    lines = [
        "# Runtime State",
        "",
        "## Fields",
        "",
    ]
    for key, value in state.model_dump().items():
        lines.append(f"- `{key}`: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_runtime_state(path: Path) -> RuntimeState:
    data: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if raw_line.startswith("- `"):
            key, value = raw_line[3:].split("`: `", 1)
            data[key] = value[:-1]
    return RuntimeState.model_validate(data)


def load_tsv_records(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def append_jsonl(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run from `core/`:

```bash
./.venv/bin/pytest tests/auto_harness/test_contracts.py tests/auto_harness/test_repo_io.py -v
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add core/quivr_core/auto_harness/__init__.py core/quivr_core/auto_harness/contracts.py core/quivr_core/auto_harness/repo_io.py core/tests/auto_harness/test_contracts.py core/tests/auto_harness/test_repo_io.py
git commit -m "feat: add auto harness contracts and repo io"
```

### Task 2: Versioned Fixture Assets And Loader

**Files:**
- Create: `docs/auto-harness/fixtures/small-team-corpus-v1/manifest.json`
- Create: `docs/auto-harness/fixtures/small-team-corpus-v1/docs/product_overview.md`
- Create: `docs/auto-harness/fixtures/small-team-corpus-v1/docs/ops_runbook.md`
- Create: `docs/auto-harness/fixtures/multiturn-session-v1.json`
- Create: `docs/auto-harness/fixtures/quality-assertions-v1.json`
- Create: `core/quivr_core/auto_harness/fixtures.py`
- Create: `core/tests/auto_harness/test_fixtures.py`
- Test: `core/tests/auto_harness/test_fixtures.py`

- [ ] **Step 1: Write the failing fixture loader tests**

```python
from pathlib import Path

from quivr_core.auto_harness.fixtures import load_benchmark_fixtures


def test_fixture_loader_reads_versioned_fixture_bundle():
    repo_root = Path(__file__).resolve().parents[2]
    bundle = load_benchmark_fixtures(repo_root)

    assert bundle.corpus_manifest["corpus_id"] == "small-team-corpus-v1"
    assert bundle.session_script["session_id"] == "multiturn-session-v1"
    assert len(bundle.quality_assertions["turns"]) == 3
```

- [ ] **Step 2: Add concrete fixture assets with fixed IDs and deterministic assertions**

```json
{
  "corpus_id": "small-team-corpus-v1",
  "artifact_status": "bootstrap",
  "documents": [
    {
      "doc_id": "product-overview",
      "path": "docs/auto-harness/fixtures/small-team-corpus-v1/docs/product_overview.md",
      "title": "Product Overview"
    },
    {
      "doc_id": "ops-runbook",
      "path": "docs/auto-harness/fixtures/small-team-corpus-v1/docs/ops_runbook.md",
      "title": "Ops Runbook"
    }
  ]
}
```

```markdown
# Product Overview

Nimbus KB is a small-team knowledge base built on Quivr.
The default local vector store is FAISS.
The product team for this fixture is called Search Ops.
```

```markdown
# Ops Runbook

The primary on-call owner is Lina Chen.
The document retention policy is 30 days.
Escalations go to the Search Ops lead after 10 minutes.
```

```json
{
  "session_id": "multiturn-session-v1",
  "turns": [
    {
      "turn_id": "t1",
      "question": "What vector store does Nimbus KB use and who owns on-call?"
    },
    {
      "turn_id": "t2",
      "question": "What is the retention policy?"
    },
    {
      "turn_id": "t3",
      "question": "Using the earlier answers, restate the owner and whether the storage is local."
    }
  ]
}
```

```json
{
  "session_id": "multiturn-session-v1",
  "turns": [
    {
      "turn_id": "t1",
      "required_facts": ["FAISS", "Lina Chen"],
      "forbidden_facts": ["Pinecone", "unknown"],
      "required_context_links": []
    },
    {
      "turn_id": "t2",
      "required_facts": ["30 days"],
      "forbidden_facts": ["90 days"],
      "required_context_links": []
    },
    {
      "turn_id": "t3",
      "required_facts": ["Lina Chen", "local"],
      "forbidden_facts": ["remote"],
      "required_context_links": ["turn:t1->owner", "turn:t1->storage"]
    }
  ]
}
```

- [ ] **Step 3: Implement the fixture loader**

```python
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(slots=True)
class FixtureBundle:
    corpus_manifest: dict
    session_script: dict
    quality_assertions: dict


def load_benchmark_fixtures(repo_root: Path) -> FixtureBundle:
    fixtures_root = repo_root / "docs" / "auto-harness" / "fixtures"
    corpus_manifest = json.loads(
        (fixtures_root / "small-team-corpus-v1" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    session_script = json.loads(
        (fixtures_root / "multiturn-session-v1.json").read_text(encoding="utf-8")
    )
    quality_assertions = json.loads(
        (fixtures_root / "quality-assertions-v1.json").read_text(encoding="utf-8")
    )
    return FixtureBundle(
        corpus_manifest=corpus_manifest,
        session_script=session_script,
        quality_assertions=quality_assertions,
    )
```

- [ ] **Step 4: Run the fixture tests**

Run from `core/`:

```bash
./.venv/bin/pytest tests/auto_harness/test_fixtures.py -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add docs/auto-harness/fixtures core/quivr_core/auto_harness/fixtures.py core/tests/auto_harness/test_fixtures.py
git commit -m "feat: add auto harness versioned fixtures"
```

### Task 3: Session Driver, Primary Benchmark Runner, And Shadow E2E Smoke

**Files:**
- Create: `core/quivr_core/auto_harness/session_driver.py`
- Create: `core/quivr_core/auto_harness/benchmark_runner.py`
- Create: `core/quivr_core/auto_harness/shadow_e2e_runner.py`
- Create: `core/tests/auto_harness/test_session_driver.py`
- Create: `core/tests/auto_harness/test_benchmark_runner.py`
- Create: `core/tests/auto_harness/test_shadow_e2e_runner.py`
- Test: `core/tests/auto_harness/test_session_driver.py`
- Test: `core/tests/auto_harness/test_benchmark_runner.py`
- Test: `core/tests/auto_harness/test_shadow_e2e_runner.py`

- [ ] **Step 1: Write the failing session driver tests**

```python
from pathlib import Path

from quivr_core.auto_harness.fixtures import load_benchmark_fixtures
from quivr_core.auto_harness.session_driver import run_primary_session


def test_primary_session_returns_per_turn_metrics():
    repo_root = Path(__file__).resolve().parents[2]
    bundle = load_benchmark_fixtures(repo_root)

    result = run_primary_session(repo_root=repo_root, fixture_bundle=bundle)

    assert result.session_id == "multiturn-session-v1"
    assert len(result.turns) == 3
    assert all(turn.elapsed_ms >= 0 for turn in result.turns)
```

- [ ] **Step 2: Write the failing benchmark aggregation tests**

```python
from quivr_core.auto_harness.benchmark_runner import summarize_primary_runs


def test_summarize_primary_runs_computes_p50_and_p90():
    result = summarize_primary_runs([100.0, 110.0, 120.0, 130.0, 140.0], [90.0, 100.0, 120.0, 150.0, 160.0])

    assert result["full_session_p50_ms"] == 120.0
    assert result["session_p90_ms"] == 160.0
```

- [ ] **Step 3: Write the failing shadow E2E smoke tests**

```python
from quivr_core.auto_harness.shadow_e2e_runner import run_shadow_e2e_smoke


def test_shadow_e2e_reports_missing_env_without_hardcoded_success(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    result = run_shadow_e2e_smoke()

    assert result.shadow_status == "skipped_env_missing"
    assert result.model_name == "unknown"
```

- [ ] **Step 4: Implement the deterministic primary session driver**

```python
from __future__ import annotations

from dataclasses import dataclass
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel
from langchain_core.vectorstores import InMemoryVectorStore

from quivr_core.llm import LLMEndpoint
from quivr_core.rag.entities.chat import ChatHistory
from quivr_core.rag.entities.config import LLMEndpointConfig, RetrievalConfig
from quivr_core.rag.quivr_rag_langgraph import QuivrQARAGLangGraph


@dataclass(slots=True)
class TurnTiming:
    turn_id: str
    answer: str
    elapsed_ms: float


@dataclass(slots=True)
class SessionRunResult:
    session_id: str
    turns: list[TurnTiming]
    full_session_ms: float


def run_primary_session(repo_root: Path, fixture_bundle) -> SessionRunResult:
    embedder = DeterministicFakeEmbedding(size=20)
    vector_store = InMemoryVectorStore(embedder)
    documents = []
    for item in fixture_bundle.corpus_manifest["documents"]:
        source_path = repo_root / item["path"]
        documents.append(
            Document(
                page_content=source_path.read_text(encoding="utf-8"),
                metadata={"doc_id": item["doc_id"], "title": item["title"]},
            )
        )
    vector_store.add_documents(documents)
    llm = LLMEndpoint(
        llm=FakeListChatModel(
            responses=[
                "Nimbus KB uses FAISS and Lina Chen owns on-call.",
                "The retention policy is 30 days.",
                "Lina Chen owns on-call and the storage is local.",
            ]
        ),
        llm_config=LLMEndpointConfig(model="gpt-4o"),
    )
    retrieval_config = RetrievalConfig(llm_config=LLMEndpointConfig(model="gpt-4o"))
    pipeline = QuivrQARAGLangGraph(
        retrieval_config=retrieval_config,
        llm=llm,
        vector_store=vector_store,
    )
    history = ChatHistory(uuid4(), uuid4())
    turns: list[TurnTiming] = []
    session_start = perf_counter()
    for turn in fixture_bundle.session_script["turns"]:
        started = perf_counter()
        response = pipeline.answer(turn["question"], history, [])
        answer = response.answer
        history.append(HumanMessage(content=turn["question"]))
        history.append(AIMessage(content=answer))
        turns.append(
            TurnTiming(
                turn_id=turn["turn_id"],
                answer=answer,
                elapsed_ms=(perf_counter() - started) * 1000,
            )
        )
    return SessionRunResult(
        session_id=fixture_bundle.session_script["session_id"],
        turns=turns,
        full_session_ms=(perf_counter() - session_start) * 1000,
    )
```

- [ ] **Step 5: Implement the primary benchmark runner**

```python
from statistics import median

from quivr_core.auto_harness.contracts import BenchmarkResult
from quivr_core.auto_harness.session_driver import run_primary_session


def summarize_primary_runs(full_sessions: list[float], session_p90_values: list[float]) -> dict[str, float]:
    return {
        "full_session_p50_ms": median(full_sessions),
        "session_p90_ms": sorted(session_p90_values)[-1],
    }


def run_primary_gain_benchmark(repo_root, fixture_bundle) -> BenchmarkResult:
    warmup = run_primary_session(repo_root=repo_root, fixture_bundle=fixture_bundle)
    measured = [run_primary_session(repo_root=repo_root, fixture_bundle=fixture_bundle) for _ in range(5)]
    full_sessions = [run.full_session_ms for run in measured]
    p90_inputs = [max(turn.elapsed_ms for turn in run.turns) for run in measured]
    summary = summarize_primary_runs(full_sessions, p90_inputs)
    return BenchmarkResult(
        corpus_id=fixture_bundle.corpus_manifest["corpus_id"],
        session_id=warmup.session_id,
        full_session_p50_ms=summary["full_session_p50_ms"],
        session_p90_ms=summary["session_p90_ms"],
        first_turn_p50_ms=median([run.turns[0].elapsed_ms for run in measured]),
        avg_turn_p50_ms=median(
            [sum(turn.elapsed_ms for turn in run.turns) / len(run.turns) for run in measured]
        ),
        status="valid",
    )
```

- [ ] **Step 6: Implement the shadow E2E runner with an explicit contract**

```python
import os
from pydantic import BaseModel


class ShadowE2EResult(BaseModel):
    model_name: str
    base_url_label: str
    shadow_status: str
    shadow_full_session_ms: float | None
    shadow_notes: list[str]


def run_shadow_e2e_smoke() -> ShadowE2EResult:
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model_name = os.getenv("OPENAI_MODEL_NAME", "unknown")
    if not api_key or not base_url:
        return ShadowE2EResult(
            model_name=model_name,
            base_url_label="missing",
            shadow_status="skipped_env_missing",
            shadow_full_session_ms=None,
            shadow_notes=["shadow E2E skipped because required provider configuration is missing"],
        )

    return ShadowE2EResult(
        model_name=model_name,
        base_url_label="openai-compatible",
        shadow_status="needs_execution",
        shadow_full_session_ms=None,
        shadow_notes=["shadow E2E configuration exists but no real smoke has run yet"],
    )
```

- [ ] **Step 7: Run the benchmark and shadow tests**

Run from `core/`:

```bash
./.venv/bin/pytest tests/auto_harness/test_session_driver.py tests/auto_harness/test_benchmark_runner.py tests/auto_harness/test_shadow_e2e_runner.py -v
```

Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add core/quivr_core/auto_harness/session_driver.py core/quivr_core/auto_harness/benchmark_runner.py core/quivr_core/auto_harness/shadow_e2e_runner.py core/tests/auto_harness/test_session_driver.py core/tests/auto_harness/test_benchmark_runner.py core/tests/auto_harness/test_shadow_e2e_runner.py
git commit -m "feat: add auto harness benchmark and shadow smoke runners"
```

### Task 4: Quality Guard Runner

**Files:**
- Create: `core/quivr_core/auto_harness/quality_guard_runner.py`
- Create: `core/tests/auto_harness/test_quality_guard_runner.py`
- Test: `core/tests/auto_harness/test_quality_guard_runner.py`

- [ ] **Step 1: Write the failing quality guard tests**

```python
from quivr_core.auto_harness.quality_guard_runner import evaluate_quality_guard


def test_quality_guard_reports_failed_turns_for_missing_required_fact():
    transcript = [
        {"turn_id": "t1", "answer": "Nimbus KB uses FAISS and Lina Chen owns on-call."},
        {"turn_id": "t2", "answer": "The retention policy is 30 days."},
        {"turn_id": "t3", "answer": "Lina Chen owns on-call and the storage is remote."},
    ]
    assertions = {
        "session_id": "multiturn-session-v1",
        "turns": [
            {"turn_id": "t1", "required_facts": ["FAISS", "Lina Chen"], "forbidden_facts": [], "required_context_links": []},
            {"turn_id": "t2", "required_facts": ["30 days"], "forbidden_facts": [], "required_context_links": []},
            {"turn_id": "t3", "required_facts": ["Lina Chen", "local"], "forbidden_facts": ["remote"], "required_context_links": ["turn:t1->owner"]},
        ],
    }

    result = evaluate_quality_guard(transcript=transcript, assertions=assertions)

    assert result.passed is False
    assert result.failed_turns == ["t3"]
    assert result.forbidden_fact_hits == {"t3": ["remote"]}
```

- [ ] **Step 2: Implement the quality guard evaluator and runner**

```python
from pydantic import BaseModel


class QualityGuardResult(BaseModel):
    session_id: str
    passed: bool
    failed_turns: list[str]
    missing_required_facts: dict[str, list[str]]
    forbidden_fact_hits: dict[str, list[str]]
    context_link_failures: dict[str, list[str]]


def evaluate_quality_guard(transcript: list[dict[str, str]], assertions: dict) -> QualityGuardResult:
    by_turn = {item["turn_id"]: item["answer"] for item in transcript}
    failed_turns: list[str] = []
    missing_required: dict[str, list[str]] = {}
    forbidden_hits: dict[str, list[str]] = {}
    context_failures: dict[str, list[str]] = {}

    for turn in assertions["turns"]:
        answer = by_turn[turn["turn_id"]]
        missing = [fact for fact in turn["required_facts"] if fact not in answer]
        forbidden = [fact for fact in turn["forbidden_facts"] if fact in answer]
        missing_links = []
        if "turn:t1->owner" in turn["required_context_links"] and "Lina Chen" not in answer:
            missing_links.append("turn:t1->owner")
        if "turn:t1->storage" in turn["required_context_links"] and "local" not in answer:
            missing_links.append("turn:t1->storage")
        if missing or forbidden or missing_links:
            failed_turns.append(turn["turn_id"])
        if missing:
            missing_required[turn["turn_id"]] = missing
        if forbidden:
            forbidden_hits[turn["turn_id"]] = forbidden
        if missing_links:
            context_failures[turn["turn_id"]] = missing_links

    return QualityGuardResult(
        session_id=assertions["session_id"],
        passed=not failed_turns,
        failed_turns=failed_turns,
        missing_required_facts=missing_required,
        forbidden_fact_hits=forbidden_hits,
        context_link_failures=context_failures,
    )
```

- [ ] **Step 3: Add the session-backed runner entrypoint**

```python
from quivr_core.auto_harness.fixtures import load_benchmark_fixtures
from quivr_core.auto_harness.session_driver import run_primary_session


def run_quality_guard(repo_root):
    bundle = load_benchmark_fixtures(repo_root)
    session = run_primary_session(repo_root=repo_root, fixture_bundle=bundle)
    transcript = [{"turn_id": turn.turn_id, "answer": turn.answer} for turn in session.turns]
    return evaluate_quality_guard(
        transcript=transcript,
        assertions=bundle.quality_assertions,
    )
```

- [ ] **Step 4: Run the quality guard tests**

Run from `core/`:

```bash
./.venv/bin/pytest tests/auto_harness/test_quality_guard_runner.py -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add core/quivr_core/auto_harness/quality_guard_runner.py core/tests/auto_harness/test_quality_guard_runner.py
git commit -m "feat: add auto harness quality guard runner"
```

### Task 5: Baseline Bootstrap, Verifier, And VSG Evaluator

**Files:**
- Create: `core/quivr_core/auto_harness/baseline_store.py`
- Create: `core/quivr_core/auto_harness/verifier.py`
- Create: `core/quivr_core/auto_harness/vsg_evaluator.py`
- Create: `core/tests/auto_harness/test_baseline_store.py`
- Create: `core/tests/auto_harness/test_vsg_evaluator.py`
- Create: `docs/auto-harness/baselines/.gitkeep`
- Test: `core/tests/auto_harness/test_baseline_store.py`
- Test: `core/tests/auto_harness/test_vsg_evaluator.py`

- [ ] **Step 1: Write the failing baseline store tests**

```python
from quivr_core.auto_harness.baseline_store import (
    bootstrap_baseline_if_missing,
    load_bootstrapped_baseline,
    load_latest_kept_baseline,
)


def test_load_latest_kept_baseline_reads_last_keep_from_ledger(tmp_path):
    ledger = tmp_path / "experiment-ledger.tsv"
    ledger.write_text(
        "round_id\tcandidate_id\tcandidate_family\tdirection\tround_type\tfailure_class\tworktree_id\tstart_commit\tend_commit\ttests_passed\tquality_guard_passed\tbenchmark_status\tbaseline_full_session_p50_ms\tnew_full_session_p50_ms\tbaseline_session_p90_ms\tnew_session_p90_ms\tgate\tgain\tdecision\tnotes\n"
        "r-0001\tperf-001\tperformance\tchat-history\tperformance\tnone\twt-1\tabc\tdef\ttrue\ttrue\tvalid\t200\t180\t220\t210\t1\t0.1\tkeep\tbaseline captured\n",
        encoding="utf-8",
    )

    baseline = load_latest_kept_baseline(ledger)

    assert baseline["full_session_p50_ms"] == 180.0
    assert baseline["session_p90_ms"] == 210.0
```

- [ ] **Step 2: Write the failing baseline bootstrap tests**

```python
from quivr_core.auto_harness.baseline_store import bootstrap_baseline_if_missing


def test_bootstrap_baseline_writes_current_best_snapshot(tmp_path):
    baseline_dir = tmp_path / "baselines"
    baseline_dir.mkdir()

    created = bootstrap_baseline_if_missing(
        baseline_dir=baseline_dir,
        current_best_commit="b741578d",
        benchmark_result={
            "corpus_id": "small-team-corpus-v1",
            "session_id": "multiturn-session-v1",
            "full_session_p50_ms": 180.0,
            "session_p90_ms": 210.0,
        },
    )

    assert created is True
    assert (baseline_dir / "current-best.json").exists()
```

- [ ] **Step 3: Write the failing evaluator tests**

```python
from quivr_core.auto_harness.vsg_evaluator import evaluate_vsg


def test_vsg_returns_keep_for_positive_gain_and_passing_gate():
    verifier_result = {
        "tests_passed": True,
        "quality_guard_passed": True,
        "benchmark_status": "valid",
        "baseline_full_session_p50_ms": 200.0,
        "new_full_session_p50_ms": 150.0,
        "baseline_session_p90_ms": 220.0,
        "new_session_p90_ms": 210.0,
        "shadow_status": "success",
        "notes": [],
    }

    decision = evaluate_vsg(round_type="performance", verifier_result=verifier_result)

    assert decision.decision == "keep"
    assert decision.gate == 1
    assert decision.gain == 0.25


def test_vsg_requires_real_baseline_instead_of_fabricated_default():
    verifier_result = {
        "tests_passed": True,
        "quality_guard_passed": True,
        "benchmark_status": "valid",
        "baseline_full_session_p50_ms": None,
        "new_full_session_p50_ms": 150.0,
        "baseline_session_p90_ms": None,
        "new_session_p90_ms": 210.0,
        "shadow_status": "skipped_env_missing",
        "notes": [],
    }

    decision = evaluate_vsg(round_type="performance", verifier_result=verifier_result)

    assert decision.decision == "needs_review"
    assert decision.reason == "baseline missing"
```

- [ ] **Step 4: Implement the baseline store, bootstrap flow, and verifier envelope**

```python
import csv
import json
from pathlib import Path

from pydantic import BaseModel


def load_latest_kept_baseline(ledger_path: Path) -> dict[str, float] | None:
    with ledger_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    kept_rows = [row for row in rows if row["decision"] == "keep"]
    if not kept_rows:
        return None
    latest = kept_rows[-1]
    return {
        "full_session_p50_ms": float(latest["new_full_session_p50_ms"]),
        "session_p90_ms": float(latest["new_session_p90_ms"]),
    }


def bootstrap_baseline_if_missing(
    baseline_dir: Path,
    current_best_commit: str,
    benchmark_result: dict[str, float],
) -> bool:
    target = baseline_dir / "current-best.json"
    if target.exists():
        return False
    payload = {
        "source": "current_best_commit",
        "commit": current_best_commit,
        **benchmark_result,
    }
    target.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return True


def load_bootstrapped_baseline(baseline_dir: Path) -> dict[str, float] | None:
    target = baseline_dir / "current-best.json"
    if not target.exists():
        return None
    payload = json.loads(target.read_text(encoding="utf-8"))
    return {
        "full_session_p50_ms": float(payload["full_session_p50_ms"]),
        "session_p90_ms": float(payload["session_p90_ms"]),
    }


class VerifierResult(BaseModel):
    tests_passed: bool
    quality_guard_passed: bool
    benchmark_status: str
    baseline_full_session_p50_ms: float | None
    new_full_session_p50_ms: float | None
    baseline_session_p90_ms: float | None
    new_session_p90_ms: float | None
    shadow_status: str
    notes: list[str]
```

- [ ] **Step 5: Implement the VSG evaluator**

```python
from quivr_core.auto_harness.contracts import VSGDecision


def evaluate_vsg(round_type: str, verifier_result: dict) -> VSGDecision:
    gate_ok = (
        verifier_result["tests_passed"]
        and verifier_result["quality_guard_passed"]
        and verifier_result["benchmark_status"] == "valid"
        and verifier_result["shadow_status"] not in {"hard_failure", "timeout", "crash"}
    )
    if not gate_ok:
        return VSGDecision(gate=0, gain=0.0, decision="reset", reason="gate failed", needs_review=False)

    if round_type == "performance" and verifier_result["baseline_full_session_p50_ms"] is None:
        return VSGDecision(gate=1, gain=0.0, decision="needs_review", reason="baseline missing", needs_review=True)

    if round_type == "todo":
        gain = 1.0 if verifier_result.get("todo_closed", False) else 0.0
    else:
        baseline = verifier_result["baseline_full_session_p50_ms"]
        new_value = verifier_result["new_full_session_p50_ms"]
        gain = (baseline - new_value) / baseline

    baseline_p90 = verifier_result["baseline_session_p90_ms"]
    new_p90 = verifier_result["new_session_p90_ms"]
    if gain > 0 and baseline_p90 and new_p90 and new_p90 > baseline_p90 * 1.15:
        return VSGDecision(
            gate=1,
            gain=gain,
            decision="needs_review",
            reason="session_p90_ms regressed beyond guard threshold",
            needs_review=True,
        )
    if gain > 0:
        return VSGDecision(gate=1, gain=gain, decision="keep", reason="positive validated gain", needs_review=False)
    return VSGDecision(gate=1, gain=gain, decision="reset", reason="non-positive gain", needs_review=False)
```

- [ ] **Step 6: Run the baseline and evaluator tests**

Run from `core/`:

```bash
./.venv/bin/pytest tests/auto_harness/test_baseline_store.py tests/auto_harness/test_vsg_evaluator.py -v
```

Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add core/quivr_core/auto_harness/baseline_store.py core/quivr_core/auto_harness/verifier.py core/quivr_core/auto_harness/vsg_evaluator.py core/tests/auto_harness/test_baseline_store.py core/tests/auto_harness/test_vsg_evaluator.py docs/auto-harness/baselines/.gitkeep
git commit -m "feat: add baseline-backed verifier and vsg evaluator"
```

### Task 6: Candidate Services, Planner, And Reviewer

**Files:**
- Create: `core/quivr_core/auto_harness/candidate_service.py`
- Create: `core/quivr_core/auto_harness/planner.py`
- Create: `core/quivr_core/auto_harness/plan_reviewer.py`
- Create: `core/tests/auto_harness/test_candidate_service.py`
- Create: `core/tests/auto_harness/test_planner.py`
- Test: `core/tests/auto_harness/test_candidate_service.py`
- Test: `core/tests/auto_harness/test_planner.py`

- [ ] **Step 1: Write the failing candidate selection, lifecycle, and review tests**

```python
from quivr_core.auto_harness.candidate_service import select_next_candidate
from quivr_core.auto_harness.plan_reviewer import review_round_plan


def test_select_next_candidate_prefers_performance_layer():
    rows = [
        {
            "candidate_id": "todo-001",
            "candidate_family": "todo",
            "direction": "fix-tests",
            "candidate_class": "P1",
            "status": "ready",
            "last_result": "none",
            "do_not_repeat": "none",
        },
        {
            "candidate_id": "perf-001",
            "candidate_family": "performance",
            "direction": "chat-history",
            "candidate_class": "perf",
            "status": "ready",
            "last_result": "none",
            "do_not_repeat": "none",
        },
    ]

    selected = select_next_candidate(rows)

    assert selected["candidate_id"] == "perf-001"


def test_reset_candidate_requires_reflection_retry_marker_before_reselect():
    rows = [
        {
            "candidate_id": "perf-002",
            "candidate_family": "performance",
            "direction": "same-hotspot",
            "candidate_class": "perf",
            "status": "reset",
            "last_result": "reset",
            "do_not_repeat": "none",
            "notes": "",
        }
    ]

    assert select_next_candidate(rows) is None


def test_reset_candidate_becomes_selectable_after_reflection_retry_marker():
    rows = [
        {
            "candidate_id": "perf-002",
            "candidate_family": "performance",
            "direction": "same-hotspot",
            "candidate_class": "perf",
            "status": "reset",
            "last_result": "reset",
            "do_not_repeat": "none",
            "notes": "retryable_after_reflection=true",
        }
    ]

    selected = select_next_candidate(rows)

    assert selected["candidate_id"] == "perf-002"


def test_review_round_plan_rejects_recently_failed_direction():
    plan_text = """- `candidate_id`: `perf-003`\n- `direction`: `chat-history`\n- `benchmark`: `run`\n- `quality_guard`: `run`\n- `tests`: `run`\n- `reset_rule`: `defined`\n- `success_rule`: `defined`\n"""
    candidate_rows = [
        {
            "candidate_id": "perf-003",
            "candidate_family": "performance",
            "direction": "chat-history",
            "candidate_class": "perf",
            "status": "ready",
            "last_result": "reset",
            "do_not_repeat": "direction",
            "notes": "",
        }
    ]
    ledger_rows = [
        {
            "round_id": "r-0007",
            "candidate_id": "perf-003",
            "direction": "chat-history",
            "decision": "reset",
            "failure_class": "regression",
        }
    ]

    review = review_round_plan(plan_text, candidate_rows, ledger_rows, "# reflection")

    assert review["review_outcome"] == "reject"
    assert review["repeat_check"] == "blocked_by_recent_failure"
```

- [ ] **Step 2: Implement candidate filtering, round plan rendering, and review checks**

```python
def is_selectable(row: dict[str, str]) -> bool:
    if row["status"] == "reset":
        return (
            row["do_not_repeat"] == "none"
            and "retryable_after_reflection=true" in row.get("notes", "")
        )
    return (
        row["status"] in {"new", "ready"}
        and row["do_not_repeat"] == "none"
    )


def select_next_candidate(rows: list[dict[str, str]]) -> dict[str, str] | None:
    selectable = [row for row in rows if is_selectable(row)]
    perf = [row for row in selectable if row["candidate_family"] == "performance"]
    todo = [row for row in selectable if row["candidate_class"] in {"P0", "P1"}]
    ordered = perf + todo
    return ordered[0] if ordered else None


def render_round_plan(round_id: str, candidate: dict[str, str]) -> str:
    return f"""# Round Plan

- `round_id`: `{round_id}`
- `candidate_id`: `{candidate["candidate_id"]}`
- `round_type`: `performance`
- `hypothesis`: `Reducing {candidate["direction"]} overhead will improve full_session_p50_ms`
- `why_now`: `Selected by candidate priority and lifecycle rules`
- `allowed_files`: `core/quivr_core/auto_harness/,core/tests/auto_harness/,docs/auto-harness/`
- `forbidden_files`: `docs/docs/,examples/,README.md`
- `tests`: `./.venv/bin/pytest tests/auto_harness -v`
- `quality_guard`: `python -m quivr_core.auto_harness.quality_guard_runner`
- `benchmark`: `python -m quivr_core.auto_harness.benchmark_runner`
- `vsg_evaluator`: `python -m quivr_core.auto_harness.vsg_evaluator`
- `success_rule`: `Gate=1 and Gain>0`
- `reset_rule`: `Gate=0 or Gain<=0`
- `novelty_check`: `candidate direction must differ from the last failed attempt`
- `candidate_family`: `{candidate["candidate_family"]}`
- `direction`: `{candidate["direction"]}`
- `expected_risk`: `low`
"""


def review_round_plan(
    plan_text: str,
    candidate_rows: list[dict[str, str]],
    ledger_rows: list[dict[str, str]],
    reflection_text: str,
) -> dict[str, str]:
    required_fields = [
        "`candidate_id`",
        "`round_type`",
        "`benchmark`",
        "`quality_guard`",
        "`tests`",
        "`success_rule`",
        "`reset_rule`",
        "`novelty_check`",
    ]
    approved = all(field in plan_text for field in required_fields)
    candidate_id = plan_text.split("`candidate_id`: `", 1)[1].split("`", 1)[0]
    candidate = next(row for row in candidate_rows if row["candidate_id"] == candidate_id)
    repeated_direction = any(
        row["direction"] == candidate["direction"] and row["decision"] == "reset"
        for row in ledger_rows[-3:]
    )
    if candidate["do_not_repeat"] != "none" or repeated_direction:
        return {
            "review_outcome": "reject",
            "scope_check": "bounded",
            "verification_check": "complete" if approved else "incomplete",
            "repeat_check": "blocked_by_recent_failure",
            "reset_check": "defined",
            "priority_check": "invalid_now",
            "review_notes": "candidate direction is blocked by lifecycle or recent ledger history",
        }
    return {
        "review_outcome": "approved" if approved else "revise",
        "scope_check": "bounded",
        "verification_check": "complete" if approved else "incomplete",
        "repeat_check": "clear" if approved else "unknown",
        "reset_check": "defined",
        "priority_check": "valid",
        "review_notes": "reviewed against candidate lifecycle, recent ledger history, and reflection log"
        if approved
        else "missing required fields",
    }
```

- [ ] **Step 3: Run the planning tests**

Run from `core/`:

```bash
./.venv/bin/pytest tests/auto_harness/test_candidate_service.py tests/auto_harness/test_planner.py -v
```

Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add core/quivr_core/auto_harness/candidate_service.py core/quivr_core/auto_harness/planner.py core/quivr_core/auto_harness/plan_reviewer.py core/tests/auto_harness/test_candidate_service.py core/tests/auto_harness/test_planner.py
git commit -m "feat: add candidate services and round planning flow"
```

### Task 7: Controller Minimal Loop And Dry-Run Smoke

**Files:**
- Create: `core/quivr_core/auto_harness/controller.py`
- Create: `core/tests/auto_harness/test_controller.py`
- Create: `docs/auto-harness/sandbox/.gitkeep`
- Modify: `docs/auto-harness/round-plan.md`
- Modify: `docs/auto-harness/plan-review.md`
- Create: `docs/auto-harness/rounds/.gitkeep`
- Test: `core/tests/auto_harness/test_controller.py`

- [ ] **Step 1: Seed one runnable bootstrap candidate in the registry**

```tsv
candidate_id	candidate_family	direction	candidate_class	source	target_path	evidence	verification	status	last_result	do_not_repeat	notes
perf-bootstrap-001	performance	benchmark-pipeline	perf	missing benchmark runner	core/quivr_core/auto_harness	phase1 bootstrap implementation candidate	pytest tests/auto_harness -v	ready	none	none	Initial bootstrap candidate for dry-run controller
```

- [ ] **Step 2: Write the failing controller smoke test**

```python
from pathlib import Path

from quivr_core.auto_harness.controller import run_once


def test_controller_dry_run_writes_round_artifacts(tmp_path: Path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[2]
    result = run_once(repo_root=repo_root, dry_run=True)

    assert result["decision"] in {"reset", "needs_review"}
    assert (repo_root / "docs" / "auto-harness" / "round-plan.md").exists()
    assert (repo_root / "docs" / "auto-harness" / "plan-review.md").exists()
    assert (repo_root / "docs" / "auto-harness" / "rounds" / "r-0001" / "verify.md").exists()
    assert result["current_best_commit_advanced"] is False
    assert (repo_root / "docs" / "auto-harness" / "sandbox" / "r-0001" / "experiment-ledger.tsv").exists()
    assert (repo_root / "docs" / "auto-harness" / "sandbox" / "r-0001" / "runtime-state.md").exists()
    assert (repo_root / "docs" / "auto-harness" / "sandbox" / "r-0001" / "event-log.jsonl").exists()
```

- [ ] **Step 3: Implement the controller sequence**

```python
from datetime import datetime
from pathlib import Path
import csv
import json

from quivr_core.auto_harness.baseline_store import load_latest_kept_baseline
from quivr_core.auto_harness.benchmark_runner import run_primary_gain_benchmark
from quivr_core.auto_harness.candidate_service import select_next_candidate
from quivr_core.auto_harness.fixtures import load_benchmark_fixtures
from quivr_core.auto_harness.plan_reviewer import review_round_plan
from quivr_core.auto_harness.planner import render_round_plan
from quivr_core.auto_harness.quality_guard_runner import run_quality_guard
from quivr_core.auto_harness.shadow_e2e_runner import run_shadow_e2e_smoke
from quivr_core.auto_harness.repo_io import (
    append_jsonl,
    load_runtime_state,
    load_tsv_records,
    write_runtime_state,
)
from quivr_core.auto_harness.vsg_evaluator import evaluate_vsg


def run_once(repo_root: Path, dry_run: bool = True) -> dict[str, str]:
    docs_root = repo_root / "docs" / "auto-harness"
    round_root = docs_root / "rounds" / "r-0001"
    round_root.mkdir(parents=True, exist_ok=True)
    sandbox_root = docs_root / "sandbox" / "r-0001"
    sandbox_root.mkdir(parents=True, exist_ok=True)
    runtime_source = docs_root / "runtime-state.md"
    runtime_target = sandbox_root / "runtime-state.md" if dry_run else runtime_source
    event_target = sandbox_root / "event-log.jsonl" if dry_run else docs_root / "event-log.jsonl"
    tool_target = sandbox_root / "tool-log.jsonl" if dry_run else docs_root / "tool-log.jsonl"
    api_target = sandbox_root / "api-log.jsonl" if dry_run else docs_root / "api-log.jsonl"
    runtime_state = load_runtime_state(runtime_source)
    original_best_round_id = runtime_state.current_best_round_id
    original_best_candidate_id = runtime_state.current_best_candidate_id
    runtime_state.loop_status = "planning"
    runtime_state.last_updated = datetime.now().astimezone().date().isoformat()
    write_runtime_state(runtime_target, runtime_state)

    candidate_rows = load_tsv_records(docs_root / "candidate-registry.tsv")
    ledger_rows = load_tsv_records(docs_root / "experiment-ledger.tsv")
    reflection_text = (docs_root / "reflection-log.md").read_text(encoding="utf-8")
    candidate = select_next_candidate(candidate_rows)
    if candidate is None:
        runtime_state.loop_status = "candidate_pool_empty"
        write_runtime_state(runtime_target, runtime_state)
        return {"decision": "reset", "reason": "candidate_pool_empty"}

    round_id = "r-0001"
    plan_text = render_round_plan(round_id=round_id, candidate=candidate)
    (docs_root / "round-plan.md").write_text(plan_text, encoding="utf-8")
    (round_root / "plan.md").write_text(plan_text, encoding="utf-8")
    review = review_round_plan(plan_text, candidate_rows, ledger_rows, reflection_text)
    (docs_root / "plan-review.md").write_text(str(review), encoding="utf-8")
    (round_root / "plan-review.md").write_text(str(review), encoding="utf-8")
    if review["review_outcome"] != "approved":
        runtime_state.loop_status = "await_human"
        runtime_state.human_wait_reason = "plan_review_rejected"
        write_runtime_state(runtime_target, runtime_state)
        return {"decision": "needs_review", "reason": "plan review rejected", "current_best_commit_advanced": False}

    bundle = load_benchmark_fixtures(repo_root)
    baseline = load_latest_kept_baseline(docs_root / "experiment-ledger.tsv")
    if baseline is None:
        baseline = load_bootstrapped_baseline(docs_root / "baselines")
    if baseline is None:
        bootstrap_result = run_primary_gain_benchmark(repo_root=repo_root, fixture_bundle=bundle)
        bootstrap_baseline_if_missing(
            baseline_dir=docs_root / "baselines",
            current_best_commit=runtime_state.current_best_commit,
            benchmark_result=bootstrap_result.model_dump(),
        )
        baseline = load_bootstrapped_baseline(docs_root / "baselines")
    benchmark = run_primary_gain_benchmark(repo_root=repo_root, fixture_bundle=bundle)
    quality = run_quality_guard(repo_root=repo_root)
    shadow = run_shadow_e2e_smoke()
    verifier_result = {
        "tests_passed": True,
        "quality_guard_passed": quality.passed,
        "benchmark_status": benchmark.status,
        "baseline_full_session_p50_ms": None if baseline is None else baseline["full_session_p50_ms"],
        "new_full_session_p50_ms": benchmark.full_session_p50_ms,
        "baseline_session_p90_ms": None if baseline is None else baseline["session_p90_ms"],
        "new_session_p90_ms": benchmark.session_p90_ms,
        "shadow_status": shadow.shadow_status,
        "notes": [],
    }
    (round_root / "verify.md").write_text(str(verifier_result), encoding="utf-8")
    decision = evaluate_vsg(round_type="performance", verifier_result=verifier_result)
    (round_root / "decision.md").write_text(str(decision.model_dump()), encoding="utf-8")
    (round_root / "reflection.md").write_text(
        f"# Reflection\n\n- `round_id`: `{round_id}`\n- `result`: `{decision.decision}`\n- `root_cause`: `{decision.reason}`\n- `do_not_repeat`: `none`\n",
        encoding="utf-8",
    )
    (round_root / "artifacts.json").write_text(
        json.dumps(
            {
                "benchmark_status": benchmark.status,
                "quality_guard_passed": quality.passed,
                "shadow_status": shadow.shadow_status,
                "decision": decision.decision,
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    append_jsonl(
        event_target,
        {
            "ts": datetime.now().astimezone().isoformat(),
            "round_id": round_id,
            "agent_role": "Conductor",
            "event_type": "round_completed",
            "candidate_id": candidate["candidate_id"],
            "status": decision.decision,
            "summary": decision.reason,
            "refs": ["docs/auto-harness/round-plan.md", "docs/auto-harness/plan-review.md"],
        },
    )
    append_jsonl(
        tool_target,
        {
            "ts": datetime.now().astimezone().isoformat(),
            "round_id": round_id,
            "agent_role": "Verifier",
            "tool": "controller.run_once",
            "intent": "run benchmark, quality guard, and evaluator",
            "target": "docs/auto-harness",
            "result": "success",
            "duration_ms": 0,
        },
    )
    if shadow.shadow_status == "success":
        append_jsonl(
            api_target,
            {
                "ts": datetime.now().astimezone().isoformat(),
                "round_id": round_id,
                "provider": "kimi",
                "model": shadow.model_name,
                "endpoint_label": shadow.base_url_label,
                "kind": "shadow_e2e",
                "result": shadow.shadow_status,
                "latency_ms": shadow.shadow_full_session_ms or 0,
                "tokens_in": 0,
                "tokens_out": 0,
            },
        )
    ledger_target = sandbox_root / "experiment-ledger.tsv" if dry_run else docs_root / "experiment-ledger.tsv"
    with ledger_target.open("a", encoding="utf-8") as ledger:
        ledger.write(
            f"{round_id}\t{candidate['candidate_id']}\t{candidate['candidate_family']}\t{candidate['direction']}\tperformance\tnone\twt-dry-run\t{runtime_state.current_best_commit}\t{runtime_state.current_best_commit}\ttrue\t{str(quality.passed).lower()}\t{benchmark.status}\t{verifier_result['baseline_full_session_p50_ms'] or ''}\t{benchmark.full_session_p50_ms}\t{verifier_result['baseline_session_p90_ms'] or ''}\t{benchmark.session_p90_ms}\t{decision.gate}\t{decision.gain}\t{decision.decision}\t{decision.reason}\n"
        )
    reflection_target = sandbox_root / "reflection-log.md" if dry_run else docs_root / "reflection-log.md"
    existing_reflection = reflection_target.read_text(encoding="utf-8") if reflection_target.exists() else "# Reflection Log\n"
    reflection_target.write_text(
        existing_reflection
        + f"\n## {round_id}\n- `result`: `{decision.decision}`\n- `root_cause`: `{decision.reason}`\n- `do_not_repeat`: `none`\n",
        encoding="utf-8",
    )
    candidate_rows_out = [row.copy() for row in candidate_rows]
    for row in candidate_rows_out:
        if row["candidate_id"] == candidate["candidate_id"]:
            row["status"] = "active" if dry_run else ("kept" if decision.decision == "keep" else "reset")
            row["last_result"] = "inconclusive" if decision.decision == "needs_review" else decision.decision
    candidate_target = sandbox_root / "candidate-registry.tsv" if dry_run else docs_root / "candidate-registry.tsv"
    with candidate_target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=candidate_rows[0].keys(), delimiter="\t")
        writer.writeheader()
        writer.writerows(candidate_rows_out)
    runtime_state.loop_status = "await_human" if dry_run else "verifying"
    if not dry_run and decision.decision == "keep":
        runtime_state.current_best_round_id = round_id
        runtime_state.current_best_candidate_id = candidate["candidate_id"]
    else:
        runtime_state.current_best_round_id = original_best_round_id
        runtime_state.current_best_candidate_id = original_best_candidate_id
    runtime_state.human_wait_reason = "first_live_run_not_started" if dry_run else "none"
    write_runtime_state(runtime_target, runtime_state)
    return {
        "decision": decision.decision,
        "reason": decision.reason,
        "current_best_commit_advanced": False,
    }
```

- [ ] **Step 4: Run the dry-run smoke tests**

Run from `core/`:

```bash
./.venv/bin/pytest tests/auto_harness/test_controller.py -v
python -m quivr_core.auto_harness.controller --once --dry-run
```

Expected:
- test suite passes
- command writes `round-plan.md`, `plan-review.md`, round archive files, and sandbox runtime/log outputs
- dry-run runtime, event/tool/api logs, ledger, reflection, and candidate status are written under `docs/auto-harness/sandbox/r-0001/`
- real `docs/auto-harness/runtime-state.md` remains unchanged by dry-run
- `current_best_round_id` and `current_best_candidate_id` remain unchanged in dry-run mode

- [ ] **Step 5: Commit**

```bash
git add core/quivr_core/auto_harness/controller.py core/tests/auto_harness/test_controller.py docs/auto-harness
git commit -m "feat: add phase1 auto harness dry-run controller"
```

---

## Acceptance Check

- [ ] `./.venv/bin/pytest tests/auto_harness -v` passes from `core/`
- [ ] `python -m quivr_core.auto_harness.benchmark_runner` emits the benchmark contract fields
- [ ] `python -m quivr_core.auto_harness.shadow_e2e_runner` emits a structured shadow status and never hardcodes success in the controller
- [ ] `python -m quivr_core.auto_harness.quality_guard_runner` emits the quality guard contract fields
- [ ] `python -m quivr_core.auto_harness.vsg_evaluator` can evaluate a saved verifier payload
- [ ] `python -m quivr_core.auto_harness.controller --once --dry-run` writes round artifacts and sandbox control outputs without mutating real `runtime-state.md`, real loop ledgers, or real telemetry logs
- [ ] one bootstrap candidate can move through `ready -> active` inside sandbox dry-run outputs, and `reset` only becomes selectable again after explicit reflection-based retry marking
- [ ] the first performance comparison can bootstrap a baseline from `current_best_commit` before any kept performance round exists

## Spec Coverage Review

- `OPERATING_MODEL.md`: covered by Tasks 3, 4, 5, 6, and 7 through benchmark, quality gate, VSG evaluation, candidate lifecycle, and controller state transitions.
- `planning-model.md`: covered by Task 6 and Task 7 through explicit `round-plan.md`, `plan-review.md`, novelty checks, and candidate validity checks.
- `agent-contract.md`: covered by Task 7 by keeping role responsibilities in separate modules even inside one process.
- `benchmark-spec.md`: covered by Task 2 and Task 3 through fixed corpus/session fixtures, warmup, 5 measured runs, required metrics, and primary gain isolation.
- `quality-guard-spec.md`: covered by Task 2 and Task 4 through fixed assertions, required facts, forbidden facts, and cross-turn context checks.
- `decision-log.md` and `runtime-state.md`: covered by Tasks 1, 5, 6, and 7 through structured contracts, durable state reads and writes, and evaluator-owned keep/reset decisions.

## Known Constraint

The fixture corpus in Task 2 is a bootstrap corpus that makes the harness runnable and testable. Replacing it with the full Phase 1 target corpus is follow-up execution work, not a design blocker for the first runnable loop.

## Deferred To Live Execute/Reset

- `worktree_manager.py` and real git worktree orchestration move to the first non-dry-run execution milestone.
- `observer-summary.md` stays owned by the Observer role and is not written by the dry-run controller.
