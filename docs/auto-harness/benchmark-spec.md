# Benchmark Spec

This document defines the Phase 1 performance benchmark for the current repository.

## Purpose

The benchmark measures application-level performance for the target scenario:

- small teams
- local or lightweight vector storage
- around 1 GB of knowledge
- continuous multi-turn question answering
- real Kimi model calls in the answer path

## Benchmark layers

Phase 1 uses two layers:

- `Gain benchmark`
  - real application path
  - real Kimi-backed answer generation
  - used for keep or reset decisions
- `Micro benchmark`
  - local sub-path timing
  - used only for diagnosis
  - never used alone for keep decisions

## Fixed inputs

The benchmark must run with fixed inputs.

### Corpus

Phase 1 uses one versioned corpus definition:

- `corpus_id`: `small-team-corpus-v1`
- target size: around 1 GB
- format mix should reflect real Quivr usage
- corpus manifest must be versioned in-repo once created

Until the dataset artifact exists, the harness design is complete but the benchmark implementation remains pending.

### Session script

Phase 1 uses one versioned conversation script:

- `session_id`: `multiturn-session-v1`
- fixed query order
- fixed turn count
- designed to exercise continuity across turns

### Model configuration

The benchmark runs against the real configured model:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- model name set to the active Kimi model

The benchmark runner must print the resolved model configuration, excluding secrets.

## Run protocol

Each benchmark run must follow this protocol:

1. prepare corpus and storage
2. run 1 warmup session
3. run 5 measured sessions
4. collect per-turn and full-session timing
5. compute the required statistics

## Primary metric

Primary metric:

- `full_session_p50_ms`

This is the median total elapsed time for one full multi-turn session across the 5 measured runs.

## Guard metrics

Guard metrics:

- `session_p90_ms`
- `first_turn_p50_ms`
- `avg_turn_p50_ms`

The primary keep decision uses `full_session_p50_ms`. Guard metrics prevent false keeps that only improve one narrow slice while degrading the rest.

## Comparison rule

The benchmark comparison formula is:

`Gain = (baseline_full_session_p50_ms - new_full_session_p50_ms) / baseline_full_session_p50_ms`

Interpretation:

- `Gain > 0`: faster
- `Gain = 0`: no measurable change
- `Gain < 0`: slower

## Invalid or noisy results

A benchmark result is invalid for keep decisions when:

- benchmark execution crashes
- benchmark execution times out
- configuration differs from the baseline run
- improvement is below 5 percent
- reruns disagree on direction

If `full_session_p50_ms` improves but `session_p90_ms` regresses by more than 15 percent:

- mark result as `needs_review`
- do not auto-keep in Phase 1

## Output contract

The benchmark runner must output at least:

- `corpus_id`
- `session_id`
- `model_name`
- `base_url_label`
- `full_session_p50_ms`
- `session_p90_ms`
- `first_turn_p50_ms`
- `avg_turn_p50_ms`
- `status`

## Keep decision dependency

The benchmark never decides a keep by itself.

A performance keep requires:

- benchmark status is valid
- `Gate = 1`
- `Gain > 0`
- no guard threshold violation
