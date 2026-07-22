# Auto-EnvSolve Research Plan / Auto-EnvSolve 研究计划

Status / 状态：独立后续项目，当前不属于 EnvSolve 的论文 claim、方法或实验。

## 中文版

### 1. 核心问题

Auto-EnvSolve 研究：一个外层研究 Agent 能否根据大量运行中反复出现、且有可执行证据支持的失败，
自动发现内层 EnvSolve 的表示或机制缺口，提出通用修改，并通过冻结的反例、回归测试和未见 case
qualification 安全地改进部署引擎？

它不是让内层 harness 在评测期间偷偷改变规则，也不是把单个 case 的修复写成全局规则。核心对象是
**harness improvement proposal**，而不是 deployment candidate。

### 2. 两层系统边界

内层 EnvSolve：

- 在单个 case 内执行 observation、constraint、operation、verification loop；
- 使用某一冻结版本的 parser、schema、planner、guard 和 verifier；
- evaluation episode 内保持不可变。

外层 Auto-EnvSolve：

- 只读取已完成 episode 的审计 artifact；
- 聚类 unsupported observation、unresolved conflict、invalid action 和 verifier mismatch；
- 提出 parser、constraint type、operator 或 verifier 的通用修改；
- 生成合成反例与回归测试；
- 只有通过独立 qualification 才产生新的内层版本。

### 3. 可更新与不可更新部分

允许版本化更新：

- observation parser 和 evidence normalizer；
- constraint schema 与 admission rule；
- operation type、planner 和 guard；
- benchmark-independent verifier；
- 诊断和审计工具。

永远不可由外层修改：

- 历史 raw event；
- 已冻结实验结果；
- official evaluator；
- held-out split 和预算协议；
- evaluation episode 中正在运行的内层版本。

### 4. 改进事务

每个外层 proposal 必须形成一个可审计事务：

```text
failure cluster and supporting evidence
claimed mechanism gap
minimal generic code change
synthetic counterexamples
regression impact
fresh unseen-development qualification
accept/reject decision
new version manifest
```

单个仓库名称、模块名称或官方 evaluator 输出不能成为准入理由。无法产生通用反例的 proposal 默认
拒绝。

### 5. 暂定研究假设

1. Evidence-grounded outer-loop improvement 比自然语言经验累积更稳定、更可审计。
2. 合成反例加未见 case qualification 能抑制 case-specific overfitting。
3. 随着运行数量增加，parser/operator coverage 和部署成功率能够改善，而回归率保持受控。

### 6. 必要实验

- 按时间和 repository identity 构造严格的 continual stream；
- 比较冻结 EnvSolve、自然语言经验库、无 qualification 的自动修改和完整 Auto-EnvSolve；
- 报告 proposal acceptance rate、regression rate、coverage gain、unseen success gain 和研发成本；
- 对 parser、constraint、operator、verifier 四类修改分别消融；
- 使用 shadow evaluation，保证外层无法接触正式 held-out 结果；
- 对每次版本升级提供可重放的因果证据。

### 7. 启动门槛

正式研究需要多个稳定 EnvSolve 版本、足够大的失败语料、可信的回归测试库，以及真正独立的
qualification reserve。在此之前，只维护机器可读的失败分类和版本 provenance，不自动修改内层算法。

### 8. 统计驱动的外层闭环

外层不能因单个 case 失败就生成代码补丁。一次合法的改进周期必须先冻结一个跨仓库批次，将轨迹按
observation、constraint、operation 和 evaluator gap 聚合，只有某个机制缺口在预先定义的统计规则下
成为主要矛盾，才允许生成一个最小 harness proposal。proposal 随后依次经过：

```text
frozen trajectory census
-> dominant-gap decision
-> one minimal generic proposal
-> synthetic counterexamples and regression tests
-> repository-disjoint shadow qualification
-> promote, reject, or roll back a version
```

因此外层自身也是状态化约束求解器：观测是版本化的失败分布和回归证据；约束包括通用性、数据隔离、
接口兼容和置信门槛；操作是带测试和迁移说明的 harness patch。EnvSolve-Pro 当前生成的 typed event、
candidate lineage、constraint delta、effect audit 和 terminal evaluation 将作为这一闭环的初始数据契约。

## English Version

### 1. Core question

Auto-EnvSolve asks whether an outer research agent can identify recurring,
evidence-supported mechanism gaps in a frozen EnvSolve engine, propose generic
changes, and admit them only after synthetic counterexamples, regression tests, and
unseen-case qualification.

### 2. Two-level boundary

The inner EnvSolve runs a fixed observation-constraint-operation-verification loop
within each case. The outer system reads only completed audit artifacts, clusters
coverage gaps, proposes changes to parsers, constraint types, operators, or generic
verifiers, and produces a new inner version only after independent qualification.
It never mutates a running evaluation episode.

### 3. Improvement transaction

Every proposal must preserve the chain from supporting failure cluster to claimed
gap, minimal generic change, synthetic counterexamples, regression results,
unseen-development qualification, acceptance decision, and version manifest.
Repository names and official evaluator output are inadmissible justifications.

### 4. Evaluation and start criterion

Evaluation uses a repository-disjoint continual stream and compares frozen
EnvSolve, natural-language experience, unqualified self-modification, and the full
admission protocol. Formal work starts only when stable EnvSolve versions, a large
failure corpus, strong regression coverage, and an independent qualification
reserve exist.

### 5. Statistically triggered outer loop

The outer system may not patch the harness in response to one salient failure. A
valid improvement cycle first freezes a repository-diverse trajectory census,
aggregates failures by observation, constraint, operation, and evaluator gaps, and
admits one minimal generic proposal only when a preregistered rule identifies a
dominant mechanism gap. The proposal must then pass synthetic counterexamples,
regression tests, and repository-disjoint shadow qualification before a new inner
version is promoted. In this sense, the outer system is itself a stateful constraint
solver whose observations are versioned failure distributions, whose constraints
encode generality and leakage boundaries, and whose actions are tested harness
patches.
