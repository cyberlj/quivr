# Auto Harness Review Findings

本文件记录对当前 `quivr-auto-harness` Phase 1 方案的审查结论。

审查基准：

- 当前仓库 `docs/auto-harness/` 的控制面设计与 `implementation-plan.md`
- `Harness engineering codex` 强调的 repo-local system of record、机械化约束、worktree 隔离、固定反馈回路
- `Agent Harness 实战指南` 强调的 planning gate、eval gate、hooks、workflow、可执行工具约束
- `auto-research` 的最小闭环做法：固定评测基座、收窄可变面、真实 keep/reset

## Findings

### 1. 高优先级：当前方案控制面完整，执行面还没有最小可跑闭环

`active-plan.md` 的目标仍然偏“设计完成”，不偏“跑通第一条真实 round”。[active-plan.md:5](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/active-plan.md:5) [active-plan.md:20](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/active-plan.md:20)

这和 `auto-research` 的关键做法不同。`auto-research` 先把固定基座、单轮实验、keep/reset 做成真闭环，再逐步扩组织层。Quivr 当前已经有更强的控制文档，但还没有把它收缩成第一条可执行 spine。

建议：

- 把 Phase 1 首要验收目标改成“跑通一条真实 round”
- 这条 round 必须真实经过：
  - candidate selection
  - round plan
  - independent review
  - worktree execution
  - tests
  - quality guard
  - benchmark
  - VSG
  - keep/reset

### 2. 高优先级：关键状态仍然主要靠 Markdown 承载，缺少机器真相源

当前 `runtime-state.md`、`round-plan.md`、`plan-review.md` 都是 Markdown-first。[runtime-state.md:1](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/runtime-state.md:1) [round-plan.md:1](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/round-plan.md:1) [plan-review.md:1](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/plan-review.md:1)

对人可读没有问题，对 Harness 不够硬。真正需要的是：

- 机器读取稳定
- 字段校验稳定
- 状态迁移稳定
- hook 和 workflow 可直接消费

建议：

- 新增 `docs/auto-harness/state/` 作为机器真相源
- 至少拆出：
  - `runtime-state.json`
  - `current-round.json`
  - `plan-review.json`
  - `decision.json`
- Markdown 保留为人类视图，由脚本从 JSON 生成

### 3. 高优先级：缺少固定 workflow 入口，当前流程仍然依赖角色自觉

你已经定义了角色、状态、round loop、handoff，但还没有定义“唯一允许的执行路径”。[OPERATING_MODEL.md:191](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/OPERATING_MODEL.md:191) [agent-contract.md:228](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/agent-contract.md:228)

这会让流程退化成：

- 文档说应该怎么做
- agent 自己决定是否照做

建议：

- 固定一个总入口，例如：
  - `uv run python -m quivr_core.auto_harness.controller --once`
- controller 内部顺序固定，不允许跳步：
  1. 读 state
  2. 选 candidate
  3. 生成 round JSON
  4. 跑 review
  5. 建 worktree
  6. 执行 worker
  7. 跑 verifier
  8. 跑 VSG
  9. keep/reset
  10. 归档 round

### 4. 高优先级：缺少 hook 或 wrapper 约束，allowed scope 仍然只是文字规则

当前文档已经定义：

- 不能跳过 review
- 不能越过 allowed files
- 不能没有 evaluator 就 keep
- 不能修改未授权范围

但这些还没有被编译成 hook 或 wrapper 脚本。[AGENTS.md:14](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/AGENTS.md:14) [planning-model.md:58](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/planning-model.md:58)

建议先落这 5 类约束：

- `pre-edit`：改动文件不在 `allowed_files` 内时直接阻断
- `pre-execute`：没有 `plan-review.json` 或 review 不为 `approved` 时阻断执行
- `pre-keep`：没有 fresh `verify.json` 和 `decision.json` 时阻断 keep
- `post-commit`：自动写回 `end_commit`、时间戳、worktree_id
- `post-round`：没有 `reflection.json` 不允许 round 结束

如果宿主环境没有原生 hook，就用 wrapper script 代替，不允许 agent 直连底层命令。

### 5. 高优先级：worktree 是核心控制约束，当前计划仍然把它放在后面

`worktree-strategy.md` 已经把每轮一个 execution worktree 定义为标准模式。[worktree-strategy.md:21](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/worktree-strategy.md:21)

但当前实现计划里的 `run_once()` 草案仍然主要在控制工作区内操作，而且 `review-findings` 已经指出这点。[implementation-plan.md:1383](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/implementation-plan.md:1383) [review-findings.md:1](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/review-findings.md:1)

建议：

- 把 worktree 从“后续 live 能力”提升为“首条 round 必需能力”
- 第一版只需要：
  - 从 `current_best_commit` 建唯一 worktree
  - Worker 和 Verifier 只在该 worktree 里工作
  - round 结束后销毁 worktree

### 6. 高优先级：tests、quality guard、benchmark、shadow 还没有都变成固定脚本入口

当前控制面已经把 Gate 写清楚了，但还没有完全落成固定脚本面。[OPERATING_MODEL.md:53](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/OPERATING_MODEL.md:53)

真正需要的不是“文档里写要跑什么”，而是 round 里只允许出现固定命令模板，例如：

- `tests_command`
- `quality_guard_command`
- `benchmark_command`
- `vsg_command`

建议：

- 不让 Planner 写自由文本命令
- 由脚本根据 candidate 和 round type 生成固定命令
- 至少固化为这几个模块入口：
  - `run_tests.py`
  - `run_quality_guard.py`
  - `run_benchmark.py`
  - `run_shadow_e2e.py`
  - `evaluate_vsg.py`

### 7. 高优先级：shadow E2E 不能以“配置存在”代替“真实成功”

当前 `implementation-plan.md` 的 shadow runner 设计已经从假成功退到 `needs_execution`，这是对的，但它仍然没有变成“真实调用才算 success”的硬约束。[implementation-plan.md:698](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/implementation-plan.md:698)

建议把规则定死：

- 只有真实调用发生且写入 `api-log.jsonl`，`shadow_status` 才允许为 `success`
- 没有 API 记录时，`shadow_status` 只能是：
  - `skipped_env_missing`
  - `failure`
  - `needs_execution`
- `pre-keep` 必须校验 shadow 结果与 API log 一致

### 8. 高优先级：系统当前无法自启动，因为 candidate pool 仍然为空

`candidate-registry.tsv` 仍然只有表头。[candidate-registry.tsv:1](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/candidate-registry.tsv:1)

这意味着第一轮只会掉进 `candidate_pool_empty`，控制流能演练，优化流不能演练。

建议：

- 先手工种入 3 到 5 个 bootstrap candidates
- 不等自动 discovery 才开始
- 第一批 candidate 直接绑定 Quivr 热点，而不是先优化 harness 自己

### 9. 高优先级：`implementation-plan.md` 里的 controller 草案仍有三个阻塞级问题

现有草案里这三项必须视为合并阻塞：

- `round_id` 固定为 `r-0001`。[implementation-plan.md:1410](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/implementation-plan.md:1410)
- `tests_passed` 直接写死为 `True`。[implementation-plan.md:1438](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/implementation-plan.md:1438)
- keep 后不推进 `current_best_commit`。[implementation-plan.md:1535](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/implementation-plan.md:1535)

建议在测试里强制校验：

- 连续两次 dry-run 生成不同 `round_id`
- 测试失败时 `tests_passed = false`
- keep 后 `current_best_commit` 变化

### 10. 中优先级：候选项 schema 已出现字段漂移，必须尽快统一

`OPERATING_MODEL.md` 使用 `type`，TSV 与实现计划使用 `candidate_class`。[OPERATING_MODEL.md:144](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/OPERATING_MODEL.md:144) [candidate-registry.tsv:1](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/candidate-registry.tsv:1)

建议：

- 统一为一个字段名
- 更建议统一成 `candidate_class`
- 在 contracts 和 repo I/O 层强校验，禁止 silent drift

### 11. 中优先级：质量门适合 smoke gate，不适合作为唯一长期质量面

固定 deterministic assertions 是对的，但如果长期只有一套 session + 一套 assertions，loop 很容易对单一题集过拟合。[quality-guard-spec.md:13](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/quality-guard-spec.md:13)

建议：

- Phase 1 仍保留 deterministic assertions 作为硬门
- 但把质量资产拆成至少 3 个固定 bundle：
  - `continuity-smoke`
  - `retrieval-relevance-smoke`
  - `regression-smoke`
- `Gate` 只依赖最小 smoke 套件
- 其他 bundle 放到 secondary observation 或 nightly regression

### 12. 中优先级：Phase 1 角色拆分偏重，首轮实现应先压缩

当前最小拓扑是 8 个角色加可选 Dashboard。[agent-contract.md:243](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/agent-contract.md:243)

边界定义没问题，但对第一条可跑 loop 来说过重。

建议 Phase 1-MVP 先压缩成 4 组：

- `Conductor`
- `Planner + Plan Reviewer`
- `Worker`
- `Verifier + VSG`

并且：

- `Recorder` 先内嵌到 controller
- `Observer` 先做轮后 summary
- `Dashboard` 延后

### 13. 中优先级：还没有像 `auto-research` 那样真正收窄 mutable surface

`auto-research` 真正有效的地方，是把可变面压到极小范围，再配合固定评测闭环去搜索。

Quivr 当前也需要同样处理。Phase 1 不应默认把整个 `core/quivr_core` 当成可变面。

建议第一批 performance candidate 只落在真实热点文件：

- [quivr_rag.py](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/core/quivr_core/rag/quivr_rag.py:1)
- [quivr_rag_langgraph.py](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/core/quivr_core/rag/quivr_rag_langgraph.py:1)

并通过 `allowed_files` + hook 真正卡死范围。

## 建议的 Phase 1-MVP

第一条可跑闭环只做这些事：

1. 从 `candidate-registry.tsv` 选一个 bootstrap candidate
2. 生成唯一 `round_id`
3. 写 `state/current-round.json`
4. 跑 review，写 `state/plan-review.json`
5. 建 execution worktree
6. Worker 只在 allowed files 内改动
7. Verifier 跑固定脚本：
   - tests
   - quality guard
   - primary benchmark
   - shadow E2E
8. VSG 输出 `decision.json`
9. keep 或 reset
10. 归档到 `rounds/<round_id>/`

## 建议的第一批工具化改造

- `state/*.json` 作为机器真相源
- 一个固定 controller 入口
- hooks 或 wrapper scripts 约束流程
- 固定 verifier 脚本入口
- execution worktree 真正落地
- round archive 固定产物：
  - `plan.json`
  - `review.json`
  - `verify.json`
  - `decision.json`
  - `reflection.json`
  - `summary.md`

## 结论

当前方案的问题不是“没有 Harness 认知”，而是“规则还没有被编译成工具约束”。

下一阶段的重点不是继续补控制文档，而是把这些规则编译成：

- JSON contract
- fixed workflow
- hooks / wrappers
- verifier scripts
- worktree isolation

当第一条 round 只能按这条路径执行，Harness 才真正开始成立。
