# Phase 1 MVP Runtime Design

## Goal

把 `quivr-auto-harness` 做成一个能真实运行的最小自治优化系统，不只是控制文档集合。

Phase 1-MVP 要解决的是：

- 多 agent 如何在真实仓库里协作
- 哪些状态是机器真相源
- 哪些动作必须被工具强制
- Quivr 的 benchmark、quality、shadow 在真实环境下怎样稳定运行
- round 怎样 keep/reset 而不污染 baseline

## Actual Runtime Scene

Phase 1 运行场景不是抽象 Harness，而是当前 Quivr 仓库里的真实执行环境：

- 控制面文件在 `docs/auto-harness/`
- 可变代码主要在 `core/quivr_core/`
- 测试通过 `uv` 和 `pytest` 运行
- Quivr 的真实运行路径依赖：
  - LLM provider 配置
  - embeddings
  - vector store
  - 本地文件存储
- 真实 provider 延迟和稳定性不可靠
- 本地缓存与文件系统有副作用

这决定了 Phase 1 必须把验证分成两层：

1. 主判定层
   - 本地、确定性、可重复
2. 影子真实层
   - 真实 provider、只做兼容性与烟测确认

## Quivr-Specific Constraints

### 1. Provider 漂移

`LLMEndpoint` 支持多个供应商和真实远程模型。真实 provider 的速度、限流、可用性、模型升级都会漂移。[llm_endpoint.py](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/core/quivr_core/llm/llm_endpoint.py:1)

结论：

- 主 keep/reset 不能锚定真实 provider latency
- shadow E2E 必须独立于主 gain

### 2. 本地存储副作用

`LocalStorage` 默认写 `~/.cache/quivr/files`，这意味着 round 之间如果不隔离，会共享文件副作用。[local_storage.py](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/core/quivr_core/storage/local_storage.py:1)

结论：

- 每轮 benchmark/quality 运行必须显式覆盖存储目录
- 不能让多个 round 共用默认本地存储目录

### 3. 测试夹具已经有可复用的确定性基座

仓库已有：

- `DeterministicFakeEmbedding`
- `FakeListChatModel`
- `InMemoryVectorStore`

这些足够支撑主 benchmark 和质量门的确定性路径。[conftest.py](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/core/tests/conftest.py:1)

结论：

- 主 benchmark 与 quality guard 应优先复用这些夹具
- 真实 provider 只留给 shadow E2E

### 4. RAG 热点集中

Phase 1 优化面应先集中在：

- `core/quivr_core/rag/quivr_rag.py`
- `core/quivr_core/rag/quivr_rag_langgraph.py`

这里覆盖了 chat history、retrieval、rerank、context assembly、tool routing 等关键路径。[quivr_rag.py](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/core/quivr_core/rag/quivr_rag.py:1) [quivr_rag_langgraph.py](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/core/quivr_core/rag/quivr_rag_langgraph.py:1)

## Design Principles

### 1. 机器真相源优先

控制状态不用 Markdown 做真相源。Markdown 只做视图。

### 1.5 文档一致性可机械检查

`docs/auto-harness/` 是系统记录，不能让设计、计划和 ownership 靠人工对齐。

Phase 1 需要一个最小 `docs_lint`，持续检查：

- role ownership
- review outcome 语义
- round archive 结构
- recorder / verifier / controller 写入边界

### 2. 单一入口

每轮只能通过一个 controller 入口启动。

### 3. 单一写者

Phase 1 每轮只允许一个 code-writing worker。

多 agent 可以存在，但不能有多个 agent 同时修改同一 mutable surface。

### 4. 全局不变量和局部策略分离

- 全局不变量：所有 agent 都一样
- 局部策略：按 role 和 agent manifest 动态决定

### 5. 主判定与真实烟测分离

- 主判定：本地确定性
- 真实烟测：真实 provider

## Topology

### Control Plane Agents

运行在 control worktree：

- Conductor
- Planner
- Plan Reviewer
- Reflector
- Recorder
- Observer

职责：

- 管状态
- 管计划
- 管候选池
- 管 reflection
- 管日志与归档

### Execution Plane Agents

运行在 round execution worktree：

- Worker
- Verifier

Phase 1-MVP 只允许一个 Worker。

如果需要额外分析 agent，它们只能是只读助手，不能直接改 code。

### Human

人不参与每轮执行，但必须保留这些入口：

- 首次 live run 放行
- `needs_review`
- `await_human`
- mutable surface 扩大
- 新依赖引入

## Worktree Model

### Control Worktree

长期存在，承载：

- `docs/auto-harness/`
- 主分支状态
- 归档与日志

### Round Worktree

每轮一个独立 worktree：

- 来源：`current_best_commit`
- 命名：`wt-<round_id>`
- 路径：`<repo_root>/.worktrees/wt-<round_id>`

Worker 和 Verifier 只在这个 worktree 里运行。

### Why One Worker Per Round

当前场景下，多 writer 并行的收益低于复杂度：

- Hook 和 manifest 会变复杂
- merge 冲突会污染 benchmark 解释
- reset 成本会升高

Phase 1 先做：

- 多 agent
- 单 writer
- 多 reader / reviewer / verifier / observer

## State Model

### 1. Runtime State

路径：

```text
docs/auto-harness/state/runtime-state.json
```

用途：

- 当前 loop 状态
- 当前 best baseline
- 当前 active round

### 2. Round State

路径：

```text
docs/auto-harness/state/rounds/<round_id>/round.json
```

用途：

- 当前 round 的机器计划
- candidate
- commands
- execution worktree

### 3. Agent Manifest

路径：

```text
docs/auto-harness/state/rounds/<round_id>/agents/<agent_id>.json
```

示例：

```json
{
  "round_id": "r-20260411-001",
  "agent_id": "worker-1",
  "role": "Worker",
  "worktree": "/abs/path/.worktrees/wt-r-20260411-001",
  "allowed_files": [
    "core/quivr_core/rag/quivr_rag.py"
  ],
  "forbidden_actions": [
    "keep",
    "reset",
    "edit_runtime_state"
  ],
  "allowed_commands": [
    "core/scripts/auto_harness/execute_guard.sh worker --round-id r-20260411-001 --agent-id worker-1"
  ]
}
```

Hook 和 wrapper 不再猜测 agent 权限，只读 agent manifest。

### 4. Review / Verify / Decision State

路径：

```text
docs/auto-harness/state/rounds/<round_id>/review.json
docs/auto-harness/state/rounds/<round_id>/verify.json
docs/auto-harness/state/rounds/<round_id>/decision.json
docs/auto-harness/state/rounds/<round_id>/reflection.json
```

## Human Views

这些文件保留，但不再作为机器真相源：

```text
docs/auto-harness/runtime-state.md
docs/auto-harness/round-plan.md
docs/auto-harness/plan-review.md
docs/auto-harness/observer-summary.md
```

统一由 `render_views.py` 从 JSON 渲染。

## Agent Launch Model

### Single Launcher

所有 agent 都必须通过统一入口启动，例如：

```bash
uv run python -m quivr_core.auto_harness.controller --once
```

controller 内部再调用：

- `launch_planner(...)`
- `launch_reviewer(...)`
- `launch_worker(...)`
- `launch_verifier(...)`
- `launch_reflector(...)`
- `launch_observer(...)`

### Launcher 注入的运行时变量

每个 agent 启动时统一注入：

- `ROUND_ID`
- `AGENT_ID`
- `AGENT_ROLE`
- `AGENT_MANIFEST_PATH`
- `WORKTREE_PATH`

这样 wrapper 和 runner 能拿到正确上下文。

## Startup And Resume Surface

除了推进状态的 controller，还需要一个只读恢复入口：

```bash
uv run python -m quivr_core.auto_harness.doctor
```

用途：

- 新 session 快速恢复上下文
- live run 前检查环境是否完整
- 中断后确认 loop 是否可恢复

输出最小化即可：

- `loop_status`
- `active_round`
- `current_best_commit`
- candidate pool 概况
- 缺失环境项
- 推荐下一步命令

## Policy Gates

Phase 1 不绑定宿主特定 hook 系统，先做 repo-local wrapper。宿主支持原生 hook 时，再把 wrapper 接进去。

### Global Invariant Gates

所有 agent 共用：

- 没有 approved review，不能执行
- 没有 verify 和 decision，不能 keep
- 不能绕过 worktree
- 不能直接写机器真相源的未授权字段

### Agent-Local Policy Gates

按 manifest 生效：

- Worker 只能改 `allowed_files`
- Planner 不能改 `core/`
- Verifier 不能改业务代码
- Recorder 不能改 `runtime-state.json`

## Wrapper Design

### `edit_guard.sh`

输入：

- `AGENT_MANIFEST_PATH`
- 目标文件路径

检查：

- 角色是否允许 edit
- 文件是否在 `allowed_files`

### `execute_guard.sh`

检查：

- `review.json` 是否存在
- `review_outcome == approved`
- 当前 agent 是否允许执行本命令

### `post_edit_check.py`

这是最便宜的 L0 反馈层，在 worker 修改后立即执行。

检查：

- `py_compile`
- 目标模块 import smoke
- 未越出 `allowed_files`
- round state schema 仍合法

失败时直接阻断进入 verifier。

### `keep_guard.sh`

检查：

- `verify.json` 存在
- `decision.json` 存在
- `decision == keep` 时 shadow 与 API log 一致

### `finalize_guard.sh`

检查：

- `reflection.json` 存在
- round archive 完整

## Verification Model

### Layer 0: Post-Edit Checks

目标：

- 用最便宜的反馈尽早拦截明显坏改动

实现方式：

- `post_edit_check.py`
- 不跑完整 benchmark
- 不依赖远程 provider

### Layer 1: Related Tests

真实运行 `pytest`，不允许写死 `tests_passed = true`。

路径：

- `run_tests.py`

输出：

- `tests_passed`
- `failed_tests`
- `duration_ms`

### Layer 2: Quality Guard

本地、固定、确定性。

实现方式：

- 用固定 corpus
- 固定 multi-turn session
- 固定 assertions
- 运行时用 deterministic fake LLM / embedding / in-memory vector store

路径：

- `run_quality_guard.py`

### Layer 3: Primary Benchmark

目标：

- 主 keep/reset 判定
- 不受真实 provider 漂移影响

实现方式：

- 基于 Quivr 本地受控路径
- 用 fake LLM + deterministic embedding + in-memory vector store
- 测 retrieval / rerank / context assembly / history handling / prompt build

路径：

- `run_benchmark.py`

### Layer 4: Shadow E2E

目标：

- 检查真实 provider 路径是否还通

实现方式：

- 使用真实 provider 配置
- 真实调用
- 产出结构化 API summary payload，由 Recorder 落盘

规则：

- 没有 API 事件时，`shadow_status` 不允许为 `success`

路径：

- `run_shadow_e2e.py`

## Filesystem And Cache Isolation

### Storage Isolation

每轮运行前显式设置：

- `QUIVR_LOCAL_STORAGE=<round_worktree>/.runtime/storage`

避免共享 `~/.cache/quivr/files`。

### Temp Artifact Isolation

每轮只允许写：

- `<round_worktree>/.runtime/`
- `docs/auto-harness/state/rounds/<round_id>/`
- `docs/auto-harness/rounds/<round_id>/`

### Shared Read-Only Cache

可共享但不作为 round 真相源：

- tokenizer cache
- 已安装依赖

## Candidate Model

`candidate-registry.tsv` 保留，但 schema 固定为：

```text
candidate_id	candidate_family	direction	candidate_class	source	target_path	evidence	verification	status	last_result	do_not_repeat	notes
```

不再使用 `type`。

Phase 1-MVP 手工种候选项，不等自动发现。

第一批候选项：

1. `perf-history-001`
   - path: `core/quivr_core/rag/quivr_rag.py`
   - direction: `chat-history`

2. `perf-context-001`
   - path: `core/quivr_core/rag/quivr_rag.py`
   - direction: `context-assembly`

3. `perf-langgraph-001`
   - path: `core/quivr_core/rag/quivr_rag_langgraph.py`
   - direction: `tool-routing`

4. `todo-blocker-001`
   - class: `P1`
   - direction: `benchmark-fixture-gap`

## Mutable Surface

Phase 1 默认只允许 performance rounds 修改：

- `core/quivr_core/rag/quivr_rag.py`
- `core/quivr_core/rag/quivr_rag_langgraph.py`
- 必要时：
  - `core/quivr_core/rag/utils.py`

默认禁止：

- `docs/docs`
- `examples`
- root README
- dependency manifests
- 其他业务模块

这和 `auto-research` 的做法一致：先收窄自由度，再做真实 keep/reset。

## Round Lifecycle

1. Conductor 读取 `runtime-state.json`
2. 选 candidate
3. 生成唯一 `round_id`
4. 写 round state
5. 生成 Planner manifest
6. Planner 产出 plan
7. 生成 Reviewer manifest
8. Reviewer 产出 review
9. review 为 `revise` 或 `reject` 时优先回到 re-plan；只有硬停条件才进 `await_human`
10. 创建 round worktree
11. 生成 Worker manifest
12. Worker 在 round worktree 执行
13. 运行 `post_edit_check.py`
14. 生成 Verifier manifest
15. Verifier 跑 tests / quality / benchmark / shadow
16. VSG 产出 `decision.json`
17. keep 或 reset
18. 写 reflection
19. 更新 candidate lifecycle 与 shared ledger
20. Recorder 落盘 structured logs
21. Observer 刷新 `observer-summary.md`
22. 渲染 human views
23. 更新 runtime state
24. 删除 round worktree

## Keep / Reset Rules

### Keep

- `decision == keep`
- 推进 `current_best_commit`
- round commit 成为新 baseline

### Reset

- `decision == reset`
- 删除 round worktree
- baseline 不变
- round 记录保留

### Needs Review

- `decision == needs_review`
- 不推进 baseline
- 不自动重试
- 进入 `await_human`

## Round Archive

每轮必须归档：

```text
docs/auto-harness/rounds/<round_id>/
├── plan.md
├── plan-review.md
├── verify.md
├── decision.md
├── reflection.md
├── artifacts.json
└── summary.md
```

## MVP Scope

Phase 1-MVP 只实现：

- JSON state store
- single controller
- round worktree
- single worker per round
- related tests
- deterministic quality guard
- deterministic primary benchmark
- real shadow E2E
- agent manifest
- wrapper-based policy gates
- `doctor` 恢复入口
- `docs_lint`
- minimal `Observer`
- round archive

## Acceptance Criteria

设计成立的最低标准：

- 能启动一轮真实 round
- 能生成唯一 `round_id`
- 能生成 per-agent manifest
- 多 agent 运行时拿到不同权限
- Worker 越界改文件会被阻断
- worker 修改后会先经过 L0 post-edit checks
- 没有 approved review 不能执行
- 没有真实 verify / decision 不能 keep
- 没有 `reflection.json` 不能 finalize
- 没有真实 API 事件时 shadow 不能报 success
- 新 session 能通过 `doctor` 在只读模式下恢复上下文
- keep 后 `current_best_commit` 推进
- reset 后 baseline 不变，round 记录保留

## Next Document

这份文档之后应直接进入实现计划：

- `docs/auto-harness/phase1-mvp-implementation-plan.md`

它只拆实现任务，不再重复运行设计背景。
