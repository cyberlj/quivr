# Observation Model

This document defines the observation layer for the Phase 1 auto harness.

## Purpose

The harness must be observable while it runs.

Observation serves four goals:

- let a human see what the system is doing now
- let the system explain what just happened
- let failed or successful rounds be replayed later
- let the loop detect unhealthy patterns before they become silent drift

The observation layer does not decide keep or reset. It records, summarizes, and alerts.

## Roles

Phase 1 observation uses three roles:

- `Recorder`
  - writes raw facts
  - does not interpret
- `Observer`
  - reads recorded facts
  - writes summaries and alerts
- `Dashboard`
  - read-only presentation layer

## Core files

The observation layer adds these repository assets:

- `docs/auto-harness/event-log.jsonl`
- `docs/auto-harness/tool-log.jsonl`
- `docs/auto-harness/api-log.jsonl`
- `docs/auto-harness/observer-summary.md`
- `docs/auto-harness/rounds/<round_id>/...`

## What each file is for

### `runtime-state.md`

Current snapshot of loop state.

Use it to answer:

- what the system is doing now
- which round is active
- which candidate is active
- which commit is the current best baseline

### `event-log.jsonl`

Global event stream.

Use it to answer:

- what happened just now
- which state changes happened
- which major lifecycle events occurred

### `tool-log.jsonl`

Structured tool execution log.

Use it to answer:

- which tools were called
- by which role
- for what intent
- whether they succeeded

### `api-log.jsonl`

Structured external API interaction summary.

Use it to answer:

- when real-provider paths were exercised
- what provider and model were involved
- whether calls succeeded
- what the latency profile looked like

This file must not contain raw secrets.

### `observer-summary.md`

Periodic human-readable summary.

Use it to answer:

- is the loop healthy
- what the recent trend is
- whether human attention is needed

### `rounds/<round_id>/`

Round-local archive.

Use it to answer:

- why this round existed
- how it was reviewed
- how it was verified
- why it was kept or reset

## Write responsibilities

### Conductor

Writes:

- `runtime-state.md`
- major state events

### Planner

Writes:

- `rounds/<round_id>/plan.md`

### Plan Reviewer

Writes:

- `rounds/<round_id>/plan-review.md`

### Worker

Writes:

- tool events for code-change actions
- round change summary

### Verifier

Writes:

- `rounds/<round_id>/verify.md`
- benchmark events
- test events
- API interaction summaries

### Reflector

Writes:

- `rounds/<round_id>/reflection.md`
- reflection summary events

### Observer

Writes:

- `observer-summary.md`
- alert events

### Recorder

Recorder does not own loop state.

Recorder writes:

- normalized event entries explicitly handed off by control or execution roles
- normalized tool and API summaries that originate from non-observation roles

Recorder must not:

- overwrite `runtime-state.md`
- create a second competing copy of the same state transition
- log its own logging writes as tool events
- recurse on observation-only maintenance actions

## Alert policy

The observation layer must surface these conditions clearly:

- repeated resets
- repeated inconclusive or noisy benchmarks
- candidate pool exhaustion
- blocked state
- await-human state
- shadow E2E degradation
- abnormal tool or API failure bursts

## Non-recursion rule

Observation must not become a meta-log spiral.

These writes are excluded from recursive event or tool logging:

- appending to observation logs
- refreshing `observer-summary.md`
- observation-only formatting or aggregation work

Tool and event logs describe the primary harness workflow, not the recorder observing itself.

## Dashboard scope

Phase 1 dashboard is intentionally small.

It should show:

- current loop state
- current round
- current best commit
- recent keep or reset outcomes
- failure distribution
- shadow E2E health

The dashboard remains read-only.
