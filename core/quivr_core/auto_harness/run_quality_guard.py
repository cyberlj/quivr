from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel
from langchain_core.vectorstores import InMemoryVectorStore


QUALITY_SESSION = [
    {
        "turn_id": "turn-1",
        "question": "Where does Project Atlas keep notes?",
        "required_facts": ["Project Atlas", "Paris"],
        "forbidden_facts": ["Berlin"],
        "required_context_links": [],
    },
    {
        "turn_id": "turn-2",
        "question": "What is the release codename?",
        "required_facts": ["Orchid", "Q3 2026"],
        "forbidden_facts": ["Violet"],
        "required_context_links": [],
    },
    {
        "turn_id": "turn-3",
        "question": "Summarize the project with prior context.",
        "required_facts": ["Project Atlas", "Orchid"],
        "forbidden_facts": ["Violet"],
        "required_context_links": ["Paris"],
    },
]

FIXED_CORPUS = [
    "Project Atlas keeps notes in Paris.",
    "The release codename is Orchid and the timeline is Q3 2026.",
]


def _normalize_answer(result) -> str:
    if hasattr(result, "content"):
        content = result.content
        return content if isinstance(content, str) else str(content)
    return str(result)


def run_quality_guard(
    worktree: str | Path,
    scripted_answers: list[str] | None = None,
) -> dict:
    worktree = Path(worktree)
    storage_path = worktree / ".runtime" / "storage"
    storage_path.mkdir(parents=True, exist_ok=True)
    os.environ["QUIVR_LOCAL_STORAGE"] = str(storage_path)

    embedder = DeterministicFakeEmbedding(size=20)
    llm = FakeListChatModel(responses=scripted_answers or [])
    vector_store = InMemoryVectorStore(embedder)
    if hasattr(vector_store, "add_texts"):
        vector_store.add_texts(FIXED_CORPUS)

    missing_required_facts: dict[str, list[str]] = {}
    forbidden_fact_hits: dict[str, list[str]] = {}
    context_link_failures: dict[str, list[str]] = {}
    failed_turns: list[str] = []

    for turn in QUALITY_SESSION:
        answer = _normalize_answer(llm.invoke(turn["question"]))

        missing = [fact for fact in turn["required_facts"] if fact not in answer]
        forbidden = [fact for fact in turn["forbidden_facts"] if fact in answer]
        context_missing = [fact for fact in turn["required_context_links"] if fact not in answer]

        if missing:
            missing_required_facts[turn["turn_id"]] = missing
        if forbidden:
            forbidden_fact_hits[turn["turn_id"]] = forbidden
        if context_missing:
            context_link_failures[turn["turn_id"]] = context_missing
        if missing or forbidden or context_missing:
            failed_turns.append(turn["turn_id"])

    return {
        "session_id": "quality-guard-phase1",
        "passed": not failed_turns,
        "failed_turns": failed_turns,
        "missing_required_facts": missing_required_facts,
        "forbidden_fact_hits": forbidden_fact_hits,
        "context_link_failures": context_link_failures,
        "storage_path": str(storage_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", required=True, type=Path)
    args = parser.parse_args()
    result = run_quality_guard(args.worktree)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
