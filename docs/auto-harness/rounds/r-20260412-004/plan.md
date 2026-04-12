# Round Plan

- `round_id`: `r-20260412-004`
- `candidate_id`: `perf-context-001`
- `round_type`: `performance`
- `hypothesis`: Optimize context-pack in quivr_rag.py.
- `allowed_files`: `core/quivr_core/rag/quivr_rag.py`
- `tests`: `python -m pytest tests/test_quivr_rag.py tests/test_chat_history.py -v`
- `quality_guard`: `python -m quivr_core.auto_harness.run_quality_guard`
- `benchmark`: `python -m quivr_core.auto_harness.run_benchmark`
- `shadow`: `python -m quivr_core.auto_harness.run_shadow_e2e`
- `vsg_evaluator`: `python -m quivr_core.auto_harness.vsg`
- `success_rule`: Keep only if deterministic gates stay green and p50 improves.
- `reset_rule`: Reset immediately on failed tests, failed quality guard, or invalid benchmark.
