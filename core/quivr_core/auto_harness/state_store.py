from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from quivr_core.auto_harness.contracts import (
    AgentManifest,
    DecisionResult,
    RecorderEvent,
    ReflectionResult,
    ReviewResult,
    RoundState,
    RuntimeState,
    VerifyResult,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class StateStore:
    def __init__(self, docs_root: str | Path):
        self.docs_root = Path(docs_root)
        self.state_root = self.docs_root / "state"

    def runtime_state_path(self) -> Path:
        return self.state_root / "runtime-state.json"

    def round_state_path(self, round_id: str) -> Path:
        return self._round_root(round_id) / "round.json"

    def agent_manifest_path(self, round_id: str, agent_id: str) -> Path:
        return self._round_root(round_id) / "agents" / f"{agent_id}.json"

    def review_result_path(self, round_id: str) -> Path:
        return self._round_root(round_id) / "review.json"

    def verify_result_path(self, round_id: str) -> Path:
        return self._round_root(round_id) / "verify.json"

    def decision_result_path(self, round_id: str) -> Path:
        return self._round_root(round_id) / "decision.json"

    def reflection_result_path(self, round_id: str) -> Path:
        return self._round_root(round_id) / "reflection.json"

    def recorder_events_path(self) -> Path:
        return self.state_root / "recorder-events.jsonl"

    def write_runtime_state(self, runtime_state: RuntimeState) -> Path:
        path = self.runtime_state_path()
        self._write_model(path, runtime_state)
        return path

    def load_runtime_state(self) -> RuntimeState:
        return self._load_model(self.runtime_state_path(), RuntimeState)

    def write_round_state(self, round_state: RoundState) -> Path:
        path = self.round_state_path(round_state.round_id)
        self._write_model(path, round_state)
        return path

    def load_round_state(self, round_id: str) -> RoundState:
        return self._load_model(self.round_state_path(round_id), RoundState)

    def write_agent_manifest(self, manifest: AgentManifest) -> Path:
        path = self.agent_manifest_path(manifest.round_id, manifest.agent_id)
        self._write_model(path, manifest)
        return path

    def load_agent_manifest(self, round_id: str, agent_id: str) -> AgentManifest:
        return self._load_model(self.agent_manifest_path(round_id, agent_id), AgentManifest)

    def write_review_result(self, review_result: ReviewResult) -> Path:
        path = self.review_result_path(review_result.round_id)
        self._write_model(path, review_result)
        return path

    def load_review_result(self, round_id: str) -> ReviewResult:
        return self._load_model(self.review_result_path(round_id), ReviewResult)

    def write_verify_result(self, verify_result: VerifyResult) -> Path:
        path = self.verify_result_path(verify_result.round_id)
        self._write_model(path, verify_result)
        return path

    def load_verify_result(self, round_id: str) -> VerifyResult:
        return self._load_model(self.verify_result_path(round_id), VerifyResult)

    def write_decision_result(self, decision_result: DecisionResult) -> Path:
        path = self.decision_result_path(decision_result.round_id)
        self._write_model(path, decision_result)
        return path

    def load_decision_result(self, round_id: str) -> DecisionResult:
        return self._load_model(self.decision_result_path(round_id), DecisionResult)

    def write_reflection_result(self, reflection_result: ReflectionResult) -> Path:
        path = self.reflection_result_path(reflection_result.round_id)
        self._write_model(path, reflection_result)
        return path

    def load_reflection_result(self, round_id: str) -> ReflectionResult:
        return self._load_model(self.reflection_result_path(round_id), ReflectionResult)

    def append_recorder_event(self, recorder_event: RecorderEvent) -> Path:
        path = self.recorder_events_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(recorder_event.model_dump(mode="json"), sort_keys=True))
            handle.write("\n")
        return path

    def _round_root(self, round_id: str) -> Path:
        return self.state_root / "rounds" / round_id

    def _write_model(self, path: Path, model: BaseModel) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        temp_path.write_text(
            json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(path)

    def _load_model(self, path: Path, model_type: type[ModelT]) -> ModelT:
        return model_type.model_validate_json(path.read_text(encoding="utf-8"))
