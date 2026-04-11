# Event Schema

This document defines the minimum structured schemas for the observation layer.

## General rules

- all logs are append-only
- one JSON object per line for `.jsonl` files
- timestamps must be ISO 8601 with timezone
- no raw secrets may be logged
- observation-maintenance actions must not recursively log themselves

## Event log schema

File:

- `docs/auto-harness/event-log.jsonl`

Minimum fields:

```json
{
  "ts": "2026-04-10T21:00:00+08:00",
  "round_id": "r-0001",
  "agent_role": "Verifier",
  "event_type": "benchmark_completed",
  "candidate_id": "perf-003",
  "status": "ok",
  "summary": "primary gain benchmark finished",
  "refs": ["docs/auto-harness/rounds/r-0001/verify.md"]
}
```

## Tool log schema

File:

- `docs/auto-harness/tool-log.jsonl`

Minimum fields:

```json
{
  "ts": "2026-04-10T21:00:05+08:00",
  "round_id": "r-0001",
  "agent_role": "Worker",
  "tool": "exec_command",
  "intent": "run unit tests",
  "target": "core/tests",
  "result": "success",
  "duration_ms": 1842
}
```

Tool log scope:

- include tool actions from planning, execution, verification, and reflection work that materially advance the harness loop
- exclude pure observation-maintenance writes such as appending logs or refreshing summaries

## API log schema

File:

- `docs/auto-harness/api-log.jsonl`

Minimum fields:

```json
{
  "ts": "2026-04-10T21:02:10+08:00",
  "round_id": "r-0001",
  "provider": "kimi",
  "model": "kimi-xxx",
  "endpoint_label": "openai-compatible",
  "kind": "shadow_e2e",
  "result": "success",
  "latency_ms": 920,
  "tokens_in": 1200,
  "tokens_out": 380
}
```

Do not log:

- raw API keys
- full prompt contents that may contain private data
- raw user documents unless explicitly intended for debugging and separately approved

## Observer summary schema

File:

- `docs/auto-harness/observer-summary.md`

The summary should contain:

- current `loop_status`
- current `round_id`
- current `current_best_commit`
- keep or reset ratio over the recent window
- failure-class distribution
- benchmark noise trend
- shadow E2E health
- recommendation: continue, watch, or intervene

## Round archive layout

Directory:

- `docs/auto-harness/rounds/<round_id>/`

Expected files:

- `plan.md`
- `plan-review.md`
- `verify.md`
- `decision.md`
- `reflection.md`
- `artifacts.json`
