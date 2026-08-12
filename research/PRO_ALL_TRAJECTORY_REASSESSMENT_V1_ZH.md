# EnvSolve-Pro 全轨迹重新审视 v1

日期：2026-08-03

## 研究问题

在实现下一个 EnvSolve-Pro 机制之前，本轮只回答一个问题：已有轨迹中反复出现的
主要失败是什么，能够直接解决它的最小算法改动是什么？

已消耗 case 只用于机制分析，不用于估计泛化能力。任何准备晋级的算法都必须先冻结，
再使用仓库不重合的新开发集进行验证。

## 证据边界

本地 artifact 清单包含 620 份 manifest。本轮审视了与其关联、已经同步到本地的全部
执行轨迹：

- 278 条 EnvSolve episode；
- 86 条 Codex 容器命令轨迹；
- 97 条旧 Agent 轨迹，其中 24 条符合当前解析器；
- 7 条能够完整读取原生动作历史的 Repo2Run 轨迹。

278 条 EnvSolve episode 共包含 1,055 个完整程序候选和 944 次可执行验证。其中
EnvSolve-Pro 子集包含 132 条 episode、512 个候选和 475 次验证。最终清点时 Spark
暂时无法连接，因此本文不声称检查了尚未同步到本地的远端独有 artifact。

## 核心结论

当前主要矛盾不是“跨候选约束规则不够多”，而是修复循环放错了位置，而且粒度太粗。

现在的 EnvSolve-Pro 会让一个独立模型 session 生成完整累计 bootstrap 程序，在新环境
里重放，汇总结果，然后重新启动另一个模型 session。强 coding Agent 的有效工作方式
却是：在同一段对话和同一个构建环境中，连续进行许多小步观察和状态变换。EnvSolve-Pro
保存了候选之间的报告，却在真正发生部署推理的地方切断了推理连续性。

通俗地说：系统一直在重写整份部署方案，而它真正应该做的是验证并修复下一个不确定步骤。

## 定量证据

### 候选不同，不等于取得进展

在 132 条 EnvSolve-Pro episode 中，512 个脚本有 502 个完全不同，只有 10 次精确重复。
因此，“禁止重复完全相同的脚本”不可能解决主要问题。

但在完整的可执行目标快照中，9 条 episode 出现了 18 次前后 finding 集合完全不变。
所有被观测到的语义停滞都发生在 EnvSolve-Pro 方法里。脚本变了，但经过验证的缺失导入
集合没有变化。

execution-feedback-v3 的对照结果最直接：7 个有效 pair 中，treatment 为 0 胜、6 平、
1 负；Official Pass 为 treatment 3、较简单的 goal-frontier control 4。treatment 的
完整 frontier 停滞为 6 次，control 为 4 次。增加失败分类制造了更多候选差异，却没有
制造更多经验证的进展。

### 失败主要发生在操作过程

132 条 EnvSolve-Pro episode 中记录了：

| 事件 | 数量 |
| --- | ---: |
| 可执行 verifier 反例 | 390 |
| 命令退出失败 | 274 |
| 候选校验拒绝 | 27 |
| 候选预算耗尽 | 23 |
| 可执行 verifier Unknown | 16 |

这并不意味着需要一个封闭的命令词表。operation-relevance contract 能描述正确修复，
但不能证明操作可行，也没有产生 treatment-only pass。精确 finding ID 还带来了投影截断
和 grounding 摩擦。因此操作空间应继续保持开放。

### 结构化机制尚未提高 Official Pass

本轮审视的已裁决配对实验中，没有一个可靠地出现 treatment-only Official Pass：

| 机制 | 有效 Official 结果 | 解释 |
| --- | --- | --- |
| candidate retention | 1/3 对 1/3 | 提高终局可达性，不提高成功率 |
| 显式约束对 raw goal state | 完整有效 pair 均打平 | 只有可能的压缩信号 |
| persistent 对 fresh construction | 4/5 对 4/5 | 状态复用真实存在，但没有成功增益 |
| goal frontier | 唯一有效 pair 打平 | treatment 资源更多 |
| bootstrap frontier v2 | 1/2 对 2/2 | treatment 负收益 |
| execution feedback v3 | 3/7 对 4/7 | treatment 负收益 |
| structured stateful V2.2 | 4/5，对 strong/raw 5/5 | 硬语义 veto 导致丢失一个 pass |
| structured stateful V2.4 | 4/4，对 strong/raw 4/4 | 修复循环一次都没有触发 |

causal-frontier v2 的表面增益因模型实际看到的 frontier 被截断而作废。operation-
relevance 的大部分位置被基础设施问题 censor；有效 pair 仍然是平局。

### 命令状态不等于环境状态

Codex 轨迹包含 2,224 条容器命令、234 次非零结果和 17 次超时，其中 15 次超时发生在
会修改环境或下载依赖的命令上。River 与 LitGPT 都说明，超时安装可能留下可用环境；
LitGPT 同时说明，相同状态也可能已经安装了大量包，却缺少生成的可执行文件，因而既有
可复用部分，也有损坏部分。

所以以下两种策略都不可靠：

- 所有非零或超时命令都回滚；
- 所有部分完成的命令都保留。

是否保留，必须由操作后的可执行 postcondition 决定。

## 关键反例

### Lark

goal-frontier control 将完整 finding 集合从 7 降到 4，再降到 2，最后降到 0。它切换了
安装路径，并最终解决剩余的 QScintilla binding。

execution-feedback-v3 却一直围绕同样 4 个 PyQt finding 修改 `PYTHONPATH`、`.pth`、
Pyright 配置、系统包和构建路径，部分操作还触犯保护面。12 份不同的完整程序没有找回
control 的成功路径。

### duckdb_engine

两个条件都长期保留同一个 finding：`duckdb_engine/__init__.py` 中的
`sqlalchemy.base`。后续候选不断更换 SQLAlchemy 版本、stub、临时包和 Pyright 配置，
但没有先回答一个局部问题：哪一种安装布局、analyzer 路径和包版本真的能满足这个导入？
循环是在重新生成方案，而不是验证这个假设。

### River 与 LitGPT

原生 Codex 没有看到 EnvBench 公共目标，所以它们不是效果对比。但它们是有价值的操作
轨迹：Agent 保留部分构建出的环境，探测它，修复工具链或 Python 兼容性，并在不重放
全部历史命令的情况下迁移已验证状态。

## 与 Repo2Run 的关系

Repo2Run 已经拥有持久 shell、命令历史、单步 Docker checkpoint，以及非零修改命令后的
回滚。因此 checkpoint 本身既不新，也不足以解决问题。

它主要根据 shell return code 决定是否回滚。pipeline 可能掩盖内部失败，超时也可能留下
尚未语义判断的环境修改。它的原生成功目标是 `runtest` 或 `poetryruntest`，不是
EnvBench 公共 `reportMissingImports` 目标。7 条可读取的完整轨迹都没有通过 Official
EnvBench，但由于目标不一致，不能把失败简单归因于 checkpoint 策略。

Docker commit 使用磁盘上的 copy-on-write image layer；Repo2Run 的 `mem_limit='2g'`
是容器内存上限，不是每个快照占用 2 GB 内存。即便如此，无界的多分支 checkpoint 仍会
消耗大量磁盘和管理时间。EnvSolve-Pro 不应维护大量物理环境分支。

## 假设取舍

### 不作为下一个核心机制

- 更多跨候选失败分类；
- 权威性高于公共目标的硬语义或 provenance 约束；
- 把 exact-script no-good 当作主要 solver；
- 多分支物理 checkpoint frontier；
- 仅根据退出状态自动回滚或保留；
- 再做一个独立 session、完整程序粒度的候选循环。

### 保留为支撑能力

- 公共可执行目标与终局一次 Official evaluator 的边界；
- 仓库完整性与 effect audit；
- 完整不可变轨迹；
- best admissible script retention；
- 最终自包含 bootstrap 程序的新容器重放；
- 作为执行优化的有界可选 checkpoint。

## 修订算法：ActiveState v1

下一个 EnvSolve-Pro 仍然保留三层架构，但把三层放进强 Agent 的活跃 session。

### 观测层：环境发生了什么变化？

Harness 在有意义的状态变换后记录命令输出、公共目标输出、仓库 effect，以及紧凑的
postcondition probe。超时或非零退出只是 observation，不是环境结论。完整观测与部分
观测必须区分。

### 约束层：当前真正验证了什么？

维护最小的**已验证状态账本**，而不是不断扩大的规则库。每条记录包含有作用域的
predicate、`satisfied`/`violated`/`unknown` 状态、证据，以及最后改变它的操作。只有
公共可执行目标和共享完整性边界是硬约束。包、版本、平台和来源解释在得到可执行 probe
支持前都只是建议。

这就是之前 compatibility frontier 更通俗的含义：维护一份短清单，写清楚哪些已经证明
可用，哪些当前损坏，哪些还没有检查。

### 操作层：完成下一步修复

一个强 Agent 对话通过开放终端控制一个持久构建环境。它可以自由检查、安装、迁移或
修复。高风险操作后，Harness 将结果分类为：

- **useful**：目标 postcondition 成立，且没有让已验证 invariant 退化；
- **damaged**：此前成立的 invariant 被破坏；
- **unknown**：关键 probe 没有完成。

Agent 接收紧凑的状态差量，而不是被替换成一个新对话。它继续决定下一步操作。最终程序
如果在新环境重放失败，失败信息也回到同一个 session 继续修复。

### 认证

当活跃环境满足公共目标后，Agent 输出一个自包含 bootstrap 程序。Harness 在新的 checkout
里重放它，审计仓库 effect，并运行公共目标。只有干净重放成功的程序才能进入终局 Official
evaluator。

### Checkpoint 策略

物理 checkpoint 是可选能力，最多保留 base、当前已验证状态和一个高风险操作前状态。
只有 postcondition 证明环境受损时才回滚；Unknown 状态应先探测。Checkpoint 不作为论文
核心贡献。

## 实现扩张前的机制门

活跃 session 假设有较强间接证据，但尚未在相同公共目标下对 DeepSeek hard screen 做过
验证。下一步应先在少量已消耗 hard case 上运行冻结的强单 session goal-aware Codex，
例如 Lark、duckdb_engine、Meerkat、Pysnmp、River 或 LitGPT。这些运行只用于观察轨迹。

只有 hard failure 出现以下至少一个现象，才继续实现完整 ActiveState v1：

- Agent 发现了会被完整程序重放丢弃的有用部分状态；
- 局部 probe 在不更换对话的情况下改变下一步操作；
- postcondition 能识别 exit status 无法识别的损坏操作；
- fresh certification 失败后，同一个 session 能修复生成程序。

如果强 goal-aware Agent 已经能解决这些 case，EnvSolve-Pro 就必须证明相对该 baseline 的
增量价值，而不是重新包装它已有的循环。

## 机制门之后的实验设计

实现冻结后再选择仓库不重合的新 case。使用相同强模型与公共目标比较：

1. 强单 session goal-aware Agent；
2. 工具完全相同、没有结构化账本的 raw active-session Agent；
3. EnvSolve-Pro ActiveState v1；
4. 明确报告 native/aligned goal 的外部 Repo2Run 与 Codex baseline。

Official Pass 是主指标。次指标包括失败后恢复、fresh replay 认证、已验证状态退化次数、
损坏操作恢复、命令数、时间、token 和依赖流量。Token 与成本只作为结果报告，不作为
停止成功求解的硬阈值。

## 最终判断

EnvSolve-Pro 不应继续变成更大的跨候选规则集合。下一个可检验贡献应当是围绕强活跃 Agent
的一层小型状态控制：观察每次环境变化，只保留可执行事实，就地修复，最后在新 checkout
中认证一次。

这个判断保留了“观测层—约束层—操作层”的研究主线，同时删掉了那些反复未能提高
Official Pass 的复杂机制。

机器可读裁决记录位于
`experiments/validations/pro_all_trajectory_reassessment_v1_adjudication.json`。
