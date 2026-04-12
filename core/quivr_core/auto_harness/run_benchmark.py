from __future__ import annotations

import argparse
import json
import os
import statistics
from pathlib import Path

from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel
from langchain_core.vectorstores import InMemoryVectorStore

from quivr_core.auto_harness.run_quality_guard import FIXED_CORPUS


def _p90(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[-1]


def run_primary_benchmark(
    worktree: str | Path,
    measured_sessions: list[dict] | None = None,
    warmup_session: dict | None = None,
) -> dict:
    worktree = Path(worktree)
    storage_path = worktree / ".runtime" / "storage"
    temp_path = worktree / ".runtime" / "tmp"
    storage_path.mkdir(parents=True, exist_ok=True)
    temp_path.mkdir(parents=True, exist_ok=True)
    os.environ["QUIVR_LOCAL_STORAGE"] = str(storage_path)
    os.environ["TMPDIR"] = str(temp_path)

    embedder = DeterministicFakeEmbedding(size=20)
    llm = FakeListChatModel(responses=["alpha", "beta", "gamma"])
    vector_store = InMemoryVectorStore(embedder)
    if hasattr(vector_store, "add_texts"):
        vector_store.add_texts(FIXED_CORPUS)
    _ = llm

    sessions = measured_sessions or []
    _ = warmup_session

    if len(sessions) != 5:
        return {
            "corpus_id": "small-team-corpus-v1",
            "session_id": "multiturn-session-v1",
            "status": "invalid_run_count",
            "storage_path": str(storage_path),
            "temp_path": str(temp_path),
        }

    full_sessions = [session["full_session_ms"] for session in sessions]
    first_turns = [session["turns_ms"][0] for session in sessions]
    avg_turns = [sum(session["turns_ms"]) / len(session["turns_ms"]) for session in sessions]

    return {
        "corpus_id": "small-team-corpus-v1",
        "session_id": "multiturn-session-v1",
        "full_session_p50_ms": statistics.median(full_sessions),
        "session_p90_ms": _p90(full_sessions),
        "first_turn_p50_ms": statistics.median(first_turns),
        "avg_turn_p50_ms": statistics.median(avg_turns),
        "status": "valid",
        "storage_path": str(storage_path),
        "temp_path": str(temp_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", required=True, type=Path)
    args = parser.parse_args()
    result = run_primary_benchmark(args.worktree)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
