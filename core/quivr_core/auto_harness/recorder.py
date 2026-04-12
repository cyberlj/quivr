from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Recorder:
    def __init__(self, docs_root: str | Path):
        self.docs_root = Path(docs_root)

    def record_event_handoff(self, handoff: dict[str, Any]) -> bool:
        return self._record_unique(
            self.docs_root / "event-log.jsonl",
            self._normalize_event_handoff(handoff),
        )

    def record_tool_handoff(self, handoff: dict[str, Any]) -> bool:
        return self._record_unique(
            self.docs_root / "tool-log.jsonl",
            self._normalize_tool_handoff(handoff),
        )

    def record_api_handoff(self, handoff: dict[str, Any]) -> bool:
        return self._record_unique(
            self.docs_root / "api-log.jsonl",
            self._normalize_api_handoff(handoff),
        )

    def _record_unique(self, path: Path, entry: dict[str, Any]) -> bool:
        if entry.get("observation_maintenance", False):
            return False

        path.parent.mkdir(parents=True, exist_ok=True)
        event_id = entry["event_id"]
        if event_id in self._existing_event_ids(path):
            return False

        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True))
            handle.write("\n")
        return True

    def _existing_event_ids(self, path: Path) -> set[str]:
        if not path.exists():
            return set()
        event_ids: set[str] = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            event_id = payload.get("event_id")
            if event_id:
                event_ids.add(str(event_id))
        return event_ids

    def _normalize_event_handoff(self, handoff: dict[str, Any]) -> dict[str, Any]:
        return {
            "event_id": handoff["event_id"],
            "round_id": handoff["round_id"],
            "kind": handoff["kind"],
            "payload": handoff["payload"],
            "recorded_at": handoff["recorded_at"],
            "origin_role": handoff.get("origin_role", "unknown"),
            "observation_maintenance": bool(handoff.get("observation_maintenance", False)),
        }

    def _normalize_tool_handoff(self, handoff: dict[str, Any]) -> dict[str, Any]:
        return {
            "event_id": handoff["event_id"],
            "round_id": handoff["round_id"],
            "agent_id": handoff.get("agent_id", "unknown"),
            "origin_role": handoff.get("origin_role", "unknown"),
            "tools": list(handoff.get("tools", [])),
            "recorded_at": handoff["recorded_at"],
            "observation_maintenance": bool(handoff.get("observation_maintenance", False)),
        }

    def _normalize_api_handoff(self, handoff: dict[str, Any]) -> dict[str, Any]:
        return {
            "event_id": handoff["event_id"],
            "round_id": handoff["round_id"],
            "api_event_id": handoff.get("api_event_id"),
            "provider": handoff.get("provider", "unknown"),
            "status": handoff.get("status", "unknown"),
            "recorded_at": handoff["recorded_at"],
            "origin_role": handoff.get("origin_role", "unknown"),
            "observation_maintenance": bool(handoff.get("observation_maintenance", False)),
        }
