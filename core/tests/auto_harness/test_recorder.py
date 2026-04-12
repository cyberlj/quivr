import json

from quivr_core.auto_harness.recorder import Recorder


def make_event_handoff() -> dict:
    return {
        "event_id": "evt-20260411-001",
        "round_id": "r-20260411-001",
        "kind": "runtime_transition",
        "payload": {"from": "verifying", "to": "resetting"},
        "recorded_at": "2026-04-11T12:00:00Z",
        "origin_role": "Conductor",
    }


def test_recorder_appends_one_normalized_event_per_handoff(tmp_path):
    docs_root = tmp_path / "docs" / "auto-harness"
    recorder = Recorder(docs_root)

    appended = recorder.record_event_handoff(make_event_handoff())

    lines = (docs_root / "event-log.jsonl").read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[0])

    assert appended is True
    assert len(lines) == 1
    assert payload["event_id"] == "evt-20260411-001"
    assert payload["origin_role"] == "Conductor"
    assert payload["kind"] == "runtime_transition"


def test_recorder_does_not_double_write_on_repeated_controller_invocation(tmp_path):
    docs_root = tmp_path / "docs" / "auto-harness"
    recorder = Recorder(docs_root)
    handoff = make_event_handoff()

    first = recorder.record_event_handoff(handoff)
    second = recorder.record_event_handoff(handoff)

    lines = (docs_root / "event-log.jsonl").read_text(encoding="utf-8").splitlines()

    assert first is True
    assert second is False
    assert len(lines) == 1
