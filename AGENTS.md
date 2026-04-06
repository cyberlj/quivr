# Repository Guidelines

## 项目结构与模块组织

本仓库的核心代码在 `core/`，其中 `core/quivr_core` 是可复用的 Python 包。`brain/` 负责顶层 `Brain` 抽象，`rag/` 负责检索与工作流编排，`processor/` 负责文件解析和切块，`llm/` 与 `llm_tools/` 负责模型与工具接入，`storage/` 负责文件存储后端。测试位于 `core/tests/`。文档源码位于 `docs/docs/`。可运行示例位于 `examples/`，例如 `examples/chatbot/` 与 `examples/simple_question/`。

## 构建、测试与开发命令

- `cd core && pytest tests/ -v`：运行核心测试集。
- `cd core && pytest tests/ -m "not base"`：跳过依赖可选扩展的测试。
- `cd core && tox`：按 `core/tox.ini` 运行多套测试环境。
- `cd core && pre-commit run --all-files`：运行 Ruff、格式化、mypy 和基础文件检查。
- `cd docs && rye run docs`：本地启动 MkDocs 文档站点。
- `cd docs && rye run build_docs`：严格模式构建文档。
- `cd examples/chatbot && rye sync && chainlit run main.py`：启动示例聊天机器人。

## 编码风格与命名约定

`core/` 使用 Python 3.11。统一使用 4 空格缩进，公共接口尽量补全类型注解，模块职责保持单一。函数、变量、文件名使用 `snake_case`，类名使用 `PascalCase`。测试名称应直接表达行为，例如 `test_dynamic_retrieve_stops_on_context_limit`。格式化与静态检查由 Ruff、`ruff-format` 和 mypy 负责，提交前应先通过这些检查。

## 测试规范

测试框架为 Pytest。测试文件放在 `core/tests/` 下，命名为 `test_*.py`。优先为改动模块补充最小可验证单元测试，再逐步扩大测试范围。注意现有 marker：`base`、`tika`、`unstructured`、`slow`。涉及特定解析器或外部依赖时，只运行对应子集，避免无关失败。

## 提交与 Pull Request 规范

从 `CHANGELOG.md` 可以看出仓库采用类似 Conventional Commits 的风格，如 `feat:`、`fix:`、`docs:`、`chore:`，也常带 scope，例如 `fix(core):`、`feat(frontend):`。提交信息保持简短、直接、使用祈使句。PR 需要说明改动内容、影响模块、关联 issue；如果改动了文档、示例或交互行为，附上截图或关键终端输出。

## 安全与配置提示

不要提交 API Key 或私密配置。常见配置通过环境变量提供，例如 `OPENAI_API_KEY`、`TAVILY_API_KEY`。`pre-commit` 已检查大文件、私钥和基础配置错误，本地生成产物不要提交，除非它们本身就是仓库需要维护的资产。

## 代码讲解规范

当用户要求“讲解代码”“带着看源码”“解释实现”时，统一参考 `docs/learning-plans/explain_code_example.md` 的表达方式，并默认使用中文。讲解顺序固定为：

1. 先讲这段代码解决什么问题，再讲代码本身。
2. 先给整体结构，再拆函数、类、配置和关键语句。
3. 每段代码后都补充 3 类说明：
   - **它做了什么**
   - **为什么这样设计**
   - **按执行顺序会发生什么**
4. 遇到抽象概念时，用一个具体例子解释，不停留在术语层面。
5. 讲完局部后，必须把它接回项目全链路，说明它的上游和下游。
6. 最后补一段“面试表达”，把技术理解转成可复述的话。

如果用户希望“直接在源码里做注释”，可以在相关源码中加入简洁中文注释辅助理解，但必须满足两点：
- 注释只解释关键逻辑、状态流转和设计意图，不写低价值废话。
- 不改变原有行为，不大面积污染文件；优先注释核心路径文件。

当源码注释用于教学时，标准提高为“教程式注释”：
- 不是只写“这段代码负责什么”，而是尽量让读者看懂每个关键语句在做什么。
- 注释要说明 4 件事：当前输入、这一句或这一小段代码产生的状态变化、输出结果、它在整个 RAG 系统里的角色。
- 对关键调用要标出它属于哪一层，例如“文件登记层”“文档标准化层”“向量建库层”“问答编排层”。
- 对容易混淆的步骤，要明确说明“这一步还没有发生什么”和“真正发生变化的是哪一步”。
