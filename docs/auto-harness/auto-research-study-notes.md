# Auto-Research Study Notes

## Source status

- Concept document: [harness engineering.md](/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/quivr-auto-harness/docs/auto-harness/harness%20engineering.md)
- Reference implementation: `/Users/wpp/Documents/LiJuanRoot/Codex/20-incubating/autoresearch`

This note records only the parts that matter for designing a reusable auto-research harness for the current `quivr-auto-harness` repository.

## Core framing from `harness engineering.md`

The article sharpens the main point:

- humans steer
- agents execute

The engineer's job shifts from writing code to designing:

- environments
- scaffolding
- repository-local knowledge
- feedback loops
- enforcement mechanisms

The article treats human time and attention as the scarce resource. That framing is important. A good harness is not the one that produces the most agent activity. It is the one that converts the least human attention into the most reliable forward motion.

## Harness engineering is environment design

The article's strongest claim is that slow progress usually comes from an underspecified environment, not from the agent "not trying hard enough".

When the agent fails, the right question is:

- what capability is missing
- how can that capability become legible to the agent
- how can it be enforced mechanically

This matches `autoresearch`: the repo does not rely on a smarter agent run. It narrows the task, fixes evaluation, and makes the loop explicit.

## What `autoresearch` actually is

`autoresearch` is not just a training repo. It is a minimal harness-engineering specimen with a strict split between:

- human-programmed harness policy: `program.md`
- agent-editable experiment surface: `train.py`
- fixed ground-truth environment: `prepare.py`

The repo keeps this split brutally small on purpose. The agent does not own the whole system. It owns one bounded mutation surface and operates inside a loop defined by the harness.

## The real harness contract

The core contract is not "let the agent improve the model". The real contract is:

1. Keep the search space narrow enough that autonomous iteration stays stable.
2. Keep evaluation fixed enough that results remain comparable.
3. Keep state transitions explicit enough that the agent can run unattended.
4. Keep rollback cheap enough that bad ideas do not poison progress.

`program.md` is therefore the true harness. It defines setup, autonomy, logging, rollback, failure handling, and keep/discard rules.

The article adds one more layer above this: the harness is not just the loop policy. It also includes every supporting system that makes code, UI, logs, metrics, architecture, and plans legible to the agent.

## Key design choices worth copying

### 1. Single mutable surface

The agent edits `train.py` only.

Implication:

- the search space is intentionally incomplete
- diffs stay reviewable
- failures are easier to localize
- rollback is trivial

For the current repository, this suggests a bounded mutation envelope is more important than raw flexibility.

### 2. Fixed evaluation harness

`prepare.py` is read-only and holds:

- time budget
- sequence length
- tokenizer training
- dataloader behavior
- evaluation metric

The agent cannot redefine success. That matters more than giving it more freedom.

### 3. Comparable experiment budget

Every run gets the same 5-minute training budget. This creates fair comparison across:

- model size
- optimizer choices
- architecture changes
- throughput tradeoffs

The harness optimizes under a fixed wall-clock budget, not under a fixed step count. This is a practical choice because autonomous research is constrained by elapsed time, not by theoretical purity.

### 4. Hard keep/discard boundary

The loop is simple:

1. change code
2. commit
3. run
4. parse metrics
5. keep only if metric improves
6. otherwise revert

This is the core anti-drift mechanism. The branch only advances on evidence.

### 5. Unattended autonomy

`program.md` explicitly forbids stopping for human confirmation once the loop begins.

This matters because unattended work needs:

- branch isolation
- structured logs
- recoverable crashes
- explicit timeout rules
- explicit revert rules

Autonomy here is not personality. It is an operational contract.

## Agent legibility is a first-class design goal

The article makes this explicit:

- if the agent cannot access something in-context, it effectively does not exist
- knowledge trapped in chat, docs outside the repo, or people's heads does not compound
- repository-local and versioned artifacts are the system of record

For the current repository, this means any rule, metric definition, architectural decision, product constraint, or debugging playbook needed by auto-research should live in-repo.

## `AGENTS.md` should be a map, not a manual

The article rejects the "one giant `AGENTS.md`" pattern because it:

- wastes context
- makes all guidance feel equally important
- rots quickly
- is hard to verify mechanically

The better pattern:

- keep `AGENTS.md` short
- use it as an index
- move durable knowledge into a structured docs tree
- enforce freshness and cross-linking with tooling

This is directly relevant for the current repository. The auto-research harness should likely be split across:

- entry instructions
- design principles
- execution plans
- evaluator definitions
- operational runbooks
- quality and debt ledgers

## `program.md` as the real product

The most important file in `autoresearch` is `program.md`, not `train.py`.

It contains the harness policy in executable prose:

- branch naming and isolation
- baseline-first rule
- allowed vs forbidden change surface
- how to launch runs
- how to extract metrics
- how to log results
- when to keep
- when to discard
- how to react to crashes
- when to stop: never, until interrupted by the human

This is the clearest evidence that harness engineering is mostly about encoding process invariants, not model code.

The article generalizes this idea. In a mature agent-first repo, the "product" is not only the application code. It is also:

- the prompts and plans
- the docs tree
- the lint rules
- the structural tests
- the review loops
- the observability surface
- the cleanup processes

## Stable invariants extracted from the repo

These invariants appear intentional and should be treated as first-class harness concepts:

- one north-star metric
- one bounded mutable surface
- one read-only evaluation path
- one fixed run budget
- one append-only experiment ledger
- one simple keep/discard rule
- one explicit rollback path
- one branch dedicated to the active search trajectory

From the article, add these broader invariants:

- one repository-local system of record
- one mechanically enforced architecture model
- one explicit place for plans and design history
- one path for feeding human judgment back into tooling or docs
- one recurring garbage-collection loop for agent drift

If too many of these become soft, autonomous iteration quality will likely collapse.

## Why this repo works as a harness specimen

It is small enough that the agent can load the full working context.

It is strict enough that the agent does not have to negotiate the rules every run.

It is measurable enough that success is machine-checkable.

It is reversible enough that local failures do not accumulate.

The article explains why this scales:

- agents move faster when boundaries are strict
- custom lint errors can teach remediation directly in agent context
- taste should be encoded as invariants, not repeated in reviews
- review and merge philosophy must adapt to agent throughput

## Architecture enforcement matters early

The article argues that strict boundaries are an early prerequisite in agent-first systems, not late-stage polish.

The pattern is:

- enforce boundaries centrally
- allow autonomy locally
- validate dependency directions mechanically
- statically enforce taste invariants where repeated review would be wasteful

For the current repository, this suggests the auto-research mechanism should not rely on free-form repo mutation. It should operate within a structural model the agent can understand and tools can check.

## Observability and UI must be legible too

The article extends harness scope beyond source code:

- app instances should be bootable per worktree
- UI should be inspectable and drivable by the agent
- logs, metrics, and traces should be queryable by the agent

This matters because many high-value research tasks are not purely static code edits. If the current repository wants autonomous work on TODOs and performance, the agent likely needs direct access to:

- benchmarks
- traces
- logs
- latency/error metrics
- reproducible local app surfaces

## Plans are first-class artifacts

The article emphasizes active plans, completed plans, and tech-debt ledgers as versioned repo artifacts.

This is a major addition to the earlier `autoresearch` reading. The harness should preserve not just experiment outcomes, but also:

- current execution intent
- progress state
- decisions made
- debt discovered
- cleanup opportunities

That is likely necessary for multi-run auto-research in a real product codebase.

## Throughput changes review and merge policy

The article argues that high agent throughput changes what is rational:

- short-lived PRs
- minimal blocking merge gates
- cheap follow-up fixes
- less waiting for perfect human review

This does not mean "no standards". It means standards move into:

- automated checks
- architectural enforcement
- agent review loops
- recurring cleanup tasks

## Garbage collection is part of the harness

The article's "AI slop cleanup" section is important.

Agent systems naturally replicate existing patterns, including bad ones. Therefore the harness needs scheduled anti-entropy work:

- quality grading
- stale-doc detection
- style and invariant cleanup
- targeted refactoring PRs

This is not optional maintenance around the harness. It is part of the harness.

## Important implementation details from code

### `prepare.py`

This file is the frozen environment layer.

- downloads and pins data shards
- trains tokenizer once and stores it in `~/.cache/autoresearch/`
- provides the runtime dataloader
- defines `evaluate_bpb`
- fixes `MAX_SEQ_LEN`, `TIME_BUDGET`, and `EVAL_TOKENS`

Design lesson: the harness should own dataset, evaluator, and budget. The agent should not.

### `train.py`

This file is the experiment layer.

- model definition
- optimizer implementation
- hyperparameters
- model-size controls
- training loop
- final summary output

Design lesson: the mutable surface should contain the levers that can plausibly improve the target metric, and as little else as possible.

### `results.tsv`

This file is intentionally untracked.

It functions as the local experiment ledger:

- commit
- metric
- memory
- status
- description

Design lesson: the harness needs a cheap, append-only operational memory outside the git history.

## What matters for the current repository design

The strongest takeaways are:

- define the harness in a policy document first
- separate mutable experiment code from fixed evaluator code
- make keep/discard machine-checkable
- make rollback the default response to non-improvement
- optimize for unattended operation, not interactive elegance
- keep logs and experiment memory outside the main code diff stream
- bias toward a narrow search surface before adding more agent freedom
- design for agent legibility across code, docs, UI, logs, and metrics
- keep durable knowledge in a structured repo-local knowledge base
- encode architecture and taste into tools, not repeated human review
- treat plans, debt, and cleanup loops as first-class repository artifacts
- optimize the system around scarce human attention

## Questions to answer before designing the current repository harness

- What is the single north-star metric for auto-research in this project?
- What files or modules are mutable by the agent?
- What evaluator must remain read-only?
- What is the fixed per-run budget?
- What is the branch and state model for long-running search?
- What is the keep/discard rule when multiple metrics move in different directions?
- What operational memory replaces `results.tsv`?
- What is the crash policy?
- What is the timeout policy?
- What is the rollback primitive?
- What docs tree becomes the system of record for agent-readable project knowledge?
- What observability surfaces must be exposed directly to the agent?
- What architecture invariants should be linted or structurally tested?
- What recurring garbage-collection jobs should keep the repo from drifting?
- What merge gates should be automated, and which judgments truly require a human?
