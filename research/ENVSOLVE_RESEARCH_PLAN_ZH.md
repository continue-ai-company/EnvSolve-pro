# EnvSolve：研究与实验计划

> 英文版：[`ENVSOLVE_RESEARCH_PLAN.md`](ENVSOLVE_RESEARCH_PLAN.md)。研究计划发生
> 变化时必须同步更新中英文两版；机器可读的冻结协议与实验产物仍是实际执行记录的
> 最终依据。
> 持续更新的 ICLR 论文稿单独维护在
> [`ENVSOLVE_ICLR_RESEARCH_PLAN.md`](ENVSOLVE_ICLR_RESEARCH_PLAN.md) 和
> [`ENVSOLVE_ICLR_RESEARCH_PLAN_ZH.md`](ENVSOLVE_ICLR_RESEARCH_PLAN_ZH.md)。

## 1. 研究目标

第一篇论文正式命名为 **EnvSolve**。它将仓库环境部署研究为部分可观测的状态化约束求解，
而不是 LLM 自由命令试错。

给定仓库 `R` 和内部可执行反馈接口 `U`，Agent 在第 `t` 轮提出
可重放部署程序 `P_t`。EnvSolve 在全新环境 `E_t` 中执行该候选，把命令与项目反馈
转化为带 provenance 的状态 `S_{t+1}`，再根据已接纳约束合成下一候选。在线 episode
结束后，只把一个最终候选提交一次给未修改的 benchmark evaluator `Q`。

核心因果主张是：

> 在模型、原始执行反馈、全新环境机会和总资源预算完全相同的条件下，带 provenance
> 的显式约束，相比非结构化轨迹历史和自然语言反思，能够提高最终环境部署成功率。

第一篇的产品目标是在 EnvBench 排行榜取得有竞争力的结果；科学目标是证明提升来自
结构化执行状态，而不是更多 evaluator 权限或更多重试。EnvBench 是最终评测基准；
Repo2Run、EnvBench agents、Codex 和相同 backbone 的反馈对照是 baseline。

资源上限属于评测协议，而不是任务定义。对比方法在模型调用与 token、candidate environment、
命令和 wall-clock time 等原始资源上使用匹配上限。美元成本只是按带日期的 provider 价格快照得到的
附属换算。

## 2. 研究范围与完整性规则

第一阶段研究对象是 EnvBench 中的 329 个 Python 仓库。不考虑 EnConda-Bench。

EnvSolve v1 只在单个 case 内进行 inference-time 适应。跨 case 自动进化、policy
training 和 Agent RL 明确不属于第一篇论文。第一篇会记录可复用环境和 transition
trajectory，但在 held-out evaluation 期间不会用它们更新 policy。
后续跨 case policy-learning 研究统一保留给单独立项的 **EnvSolve-RL**，本计划不展开。
EnvSolve v1 也不在线检索其他 case 的自然语言总结、修复经验或历史轨迹；共享但不可变的
revision cache、base-image 元数据和 benchmark 配置属于实验基础设施，不属于跨 case memory。

环境解决方案可以安装软件包、选择运行时、安装系统库、配置包管理器，以及添加仅
作用于环境的配置，但不得：

- 修改应用源代码来掩盖环境错误；
- 创建空模块或伪模块，只为通过静态 import 检查；
- 使用从 held-out evaluation 中得到的仓库专属硬编码修复；
- 向求解 Agent 暴露官方 evaluator 的实现细节或结果；
- 使用官方评测结果选择、修复、排序或重试同一 case 的候选；
- 在不同方法的对比中暗中改变模型、预算、镜像、超时或验证器配置。

所有运行都必须记录仓库 revision、方法 revision、evaluator revision 及其 dirty
状态、模型标识、预算、容器镜像、脚本、轨迹、日志和解析后的指标。

每个 method、case 和 seed 的在线 episode 结束后，官方 evaluator 只调用一次，结果
只作为 post-episode evaluation 保存。内部反馈只能来自普通容器执行、依赖工具和预注册
的 benchmark-independent 项目检查，并且所有 feedback-loop 对照拥有相同访问权限。

## 3. 方法

### 3.1 候选部署程序

外层 loop 提出的单位是完整、可重放的环境程序，而不是孤立 shell patch。候选
`P_t` 包含类型化 runtime、系统包、包管理器、仓库安装和环境配置 effect。只用于
检查的命令保留在 trajectory 中，但不进入最终部署程序。

### 3.2 执行证据与状态

每个候选都在具有唯一 identity 的全新环境中执行。原始命令、工作目录、stdout、
stderr、exit code、耗时和项目原生检查结果构成不可变证据。EnvSolve 从这些证据中
派生显式 runtime、package、capability、module、platform 与 unresolved-goal 状态。
每个派生事实都保留支持或反驳它的 provenance。

### 3.3 约束接纳

反馈在影响下一候选前必须分类：

- 可复现的确定性矛盾进入 hard constraint；
- 有证据但含义模糊的观测只作为 hypothesis 参与排序，不能排除候选；
- 带明确网络或基础设施签名的 timeout 保持 Unknown，不转化为环境约束；没有此类签名的固定预算
  execution timeout 保留为 candidate-cost evidence；
- 格式错误、过期、复用环境或无依据反馈全部 fail closed。

失败证据必须先持久化，才能影响下一次 proposal。已接纳的 hard conflict 或高置信度 unresolved
requirement 可以生成强制操作义务；仅有 hypothesis 的失败可以继续搜索，但只能提供软排序信号，
不能排除候选。
方法不加入 repository-name 分支、held-out package map 或源码修改修复路径。

### 3.4 反例驱动的候选更新

在第 `t` 轮，相同 agent backbone 接收仓库上下文和当前已接纳状态，提出 `P_t`。
执行证据更新 `S_t`。若预注册内部检查通过，EnvSolve 可以停止；否则在剩余全局预算
内，根据累计约束生成 `P_{t+1}`。所有候选轮共享同一个模型请求、token、wall-clock、
命令和 fresh-environment 账本。

Fresh replay 属于算法，因为它检查部署程序是否依赖前一候选留下的隐藏状态；但它不是
EnvBench 官方评测。

对于每个受支持的 hard conflict 或 unresolved hard requirement，确定性 planner 生成带 provenance 的 `OperationPlan`，
把 runtime、package、capability 和 module 冲突映射为允许的运行时配置、Python 包安装或
系统包安装等操作类型。模型仍负责选择具体参数并重新提出完整程序；在创建容器前，
`constraint-operation-guard-v2` 检查候选相对最近一次真实执行候选，是否为每项义务引入了
至少一个允许的新 mutation。被拒候选只消耗候选与模型预算，不消耗环境或命令预算。

### 3.5 评测隔离

未修改的 EnvBench evaluator 是终局裁判，不是在线 verifier。它只在最终候选上运行
一次，输出不会反馈到同一 episode。已经冻结的 EnvBench Finding Collector 仅用于
post-episode 测量和错误分析。

### 3.6 可复用轨迹协议

第一篇保存不可变 raw event 与版本化 derived view。每个 transition 记录 `case_id`、
`episode_id`、`candidate_id`、`parent_candidate_id`、`environment_id`、`step_id`、
动作前状态、动作、原始 observation、动作后状态、资源成本和终态。最终官方结果标记为
`post_episode_evaluation`，不属于在线状态。部署 recipe、base-image digest、已安装版本
manifest 和选定 terminal snapshot 使环境可重建。该数据协议保留未来研究价值，但跨 case
学习不构成 EnvSolve 的论文贡献。

每次受约束的 transition 还记录 source conflict、source constraint、operation requirement、
guard decision、候选 mutation 与 verifier outcome。它们形成可监督的“约束状态 -> 操作 ->
结果”数据，可供 EnvSolve-RL 学习策略，也可供未来 Auto-EnvSolve 统计未覆盖的
parser/operator 类别；第一篇不读取这些跨 case 派生数据来改变在线策略。

## 4. 研究问题

| ID | 研究问题 |
| --- | --- |
| RQ1 | 在总预算匹配时，EnvSolve 能否相对 native agent 和相同 backbone feedback-loop 对照提高最终 Official Pass@1？ |
| RQ2 | 带 provenance 的约束状态能否超过原始轨迹历史和自然语言反思？ |
| RQ3 | 显式约束、证据接纳和 fresh replay 分别贡献了哪些提升？ |
| RQ4 | EnvSolve 能否减少重复失败与部署成本，同时提高 clean-replay 可靠性？ |
| RQ5 | 效果能否跨 agent backbone、仓库类型和失败类型泛化？ |

## 5. 数据集协议

EnvBench 官方提供 229/100 的 train/test 划分。已发布 train JSONL 实际包含一条
拼接记录，因此训练集由 329-case 源数据减去未修改的官方 100-case test set
重建。源 revision 和文件哈希冻结在 `experiments/cases/split_manifest.json`。

| Split | 数量 | 使用策略 |
| --- | ---: | --- |
| Dev-5 | 5 | 按预先声明的环境类别从官方 train 中选择；允许重复运行 |
| Dev-Extension-3 | 3 | 首次执行前冻结的 outcome-blind 哈希采样；允许重复运行 |
| Canary-20 | 20 | 从剩余官方 train 中进行 outcome-blind 哈希采样；每个 milestone 只运行一次 |
| Train-Pool Snapshot | 201 | Dev-Extension-3 分配后的不可变分配源；不再表示当前 untouched 数量 |
| P0 Harness Dev | 3 | 仅用于 harness 验证且已消费；不得用于 solver 确认性结论 |
| V0 Discovery Round 1 | 5 | outcome-blind 的 FreeAgent/v0 配对 transport 与机制发现批次 |
| V0 Discovery Round 2 | 5 | Round 1 transport 修复后重新冻结的新 outcome-blind 配对批次 |
| Remaining Train Reserve | 188 | 上述分配后仍 outcome-unseen；后续分配必须预注册 |
| Official-Test | 100 | 方法和协议冻结前完全 held out |
| Leaderboard | 329 | 最终用于排行榜比较的完整 EnvBench |

Dev-5 覆盖常规 metadata、包管理器或版本约束、系统或原生依赖、开发或测试依赖，
以及平台相关的可选依赖。在预算允许时，replication experiment 使用官方 held-out
100 cases 进行三 seed 分析。

Dev-Extension-3 在检查其中任何仓库、轨迹或结果之前，使用预注册 salt 按 SHA256
排序，从冻结的 Train-Rest-204 分配池中选择。它用于扩展稳健性诊断，不消耗
Canary-20 或 Official-Test-100。

`train_untouched201.jsonl` 继续作为不可变的分配源快照。3 个 outcome-blind case 已被
P0 post-freeze harness 验证消费，并从 solver 确认性分析中排除。随后使用新的冻结
SHA256 salt，从其余 198 个 case 中选出 EnvSolve v0 Discovery Round 1。一次 transport
缺陷使 v0 graph 尚未调用模型就终止；原始批次保持不可变，并使用已消费的同一 case
完成通用 state-schema 修复资格验证。随后使用不同冻结 salt，从剩余 reserve 中选出 5 个
新 case 形成 Round 2。两轮都在相同 identity 上配对比较 FreeAgent 与 v0，禁止批次中途
修改方法；只有当同一错误族至少出现在 2 条有效 v0 trajectory 中，且构成可归因失败的
plurality 时，才允许引入新机制。任何 development-informed 机制仍必须先在另一批单独
冻结的未见 case 上带来提升，之后才能运行 Canary-20。

## 6. Baselines

- EnvBench deterministic baseline
- EnvBench Python ReAct agent
- EnvBench procedural agent
- Installamatic
- 固定 revision 的 Repo2Run
- 使用冻结 native execution policy 的 Codex
- 使用原生 ReAct loop 的相同 backbone FreeAgent
- raw-history retry：使用相同 agent、fresh-environment 机会和原始历史执行反馈，但
  不使用结构化状态
- reflection retry：使用相同反馈的 LLM 自然语言反思，但不使用类型化约束
- EnvSolve v0：使用相同 agent 与全局预算，但不持久化 counterexample constraint

Native system 用于建立排行榜上下文。主要因果对比是相同 backbone、case、官方评测
次数、内部反馈、候选轮数上限和全局资源账本下的 raw-history retry、reflection retry 与
EnvSolve。方法可以提前停止，但任何条件都不能在新一轮获得新的独立预算。

## 7. 实验设计

| ID | 实验 | 对应研究问题 |
| --- | --- | --- |
| E1 | 与固定 native baselines 的完整 EnvBench 排行榜对比 | RQ1 |
| E2 | 预算匹配的 native、raw-history、reflection、v0 与 EnvSolve 对比 | RQ1-RQ2 |
| E3 | 分别移除结构化状态、hard-constraint admission 或 fresh replay | RQ2-RQ3 |
| E4 | 候选轮修复率与 failure-transition 分析 | RQ3-RQ4 |
| E5 | 重复失败、命令、token、时间、成本和 fresh-container 数量 | RQ4 |
| E6 | 跨 agent/backbone 复现实验 | RQ5 |
| E7 | 按失败类型和仓库特征进行分层分析 | RQ5 |
| E8 | 对最终成功部署程序进行独立 clean replay | RQ4-RQ5 |
| E9 | 成功、回归和 blocked outcome 的机制案例研究 | RQ1-RQ5 |

核心消融保持最小：非结构化 raw history、自然语言 reflection、没有 constraint gate 的
结构化 evidence、没有 fresh replay 的结构化 constraint，以及完整 EnvSolve。只有当同一
未解决需求出现在多个无关 development repository 中，并在另一批冻结数据上验证后，才
允许增加新的 parser、repair operator 或 state type。

## 8. 指标与统计方法

主指标是最终 Official Pass@1：一个最终候选、一次未修改官方评测，且不允许基于
evaluator 结果选择候选。次要效果指标包括 round-to-round repair rate、clean replay
rate、bootstrap success、project-native internal-check success 和 repository integrity。
效率指标包括总动作、失败动作、精确重复动作、重复失败族、模型请求与 token、
wall-clock time、命令和消耗的全新环境数量。可以用带日期的 provider 价格快照换算附属美元估计，
但它不是科学比较的匹配指标。

机制指标包括接纳约束的 precision 与 coverage、保持 Unknown 的失败比例、真正改变下一
候选的冲突，以及由历史证据直接支持的成功修复。基础设施 outcome 单独报告，绝不计为
已解决的环境错误。

二元配对结果使用 McNemar 检验和 paired bootstrap 95% 置信区间；连续配对结果
使用 Wilcoxon signed-rank 检验并报告 effect size；多重比较进行校正。非确定性 Agent
在预注册代表性子集上使用多个 seed；完整冻结评测使用预先声明的 seed，并在预算允许时
进一步复现。所有 headline comparison 同时报告 effect size 与资源使用量。

## 9. 论文结构

1. 引言
2. 交互成功与部署重放之间的缺口
3. Repository Environment Synthesis 问题定义
4. Evidence-Grounded Constraint State
5. EnvSolve 反例驱动部署算法
6. 实验协议与公平性
7. 主要结果
8. 机制分析与消融
9. 泛化、效率与失败分析
10. 相关工作
11. 有效性威胁
12. 结论

## 10. 里程碑

| 阶段 | 目标 | 退出条件 |
| --- | --- | --- |
| P0-P1 | 冻结 harness、数据划分和 baselines | 历史基础设施和对比 artifact 保持可审计 |
| P2-P3 | 显式状态与约束 | 可从不可变事件重建状态，且每条约束都有 evidence provenance |
| P4-P5 | Repair 与内部验证资格验证 | 通用修复和 clean replay 在不查看 held-out outcome 时完成资格验证 |
| P6 | 内部反馈 multi-round runner | raw-history、reflection、v0 和 EnvSolve 共用全局账本；官方输出不能进入在线状态 |
| P7 | 未见 development 准入 | 完整 EnvSolve 超过 v0 和两个 feedback control，且无完整性违规或 case-specific rule |
| P8 | 算法与协议冻结 | 代码、prompt、预算、内部检查、split、停止与最终候选选择完成内容冻结 |
| P9 | Canary 与 Official-Test 评测 | 冻结后只使用一次 Canary-20；Official-Test-100 artifact 完整且未修改方法 |
| P10 | 完整排行榜与复现 | 完整 EnvBench、跨 agent 复现和 clean-replay artifact 完成 |
| P11 | 分析与投稿 | RQ1-RQ5、附录、代码、轨迹 schema 和复现包完整 |

P7 是算法 go/no-go gate。它要求单独冻结的未见 development batch、有效配对 audit、
最终官方成功数严格超过 EnvSolve v0 与两个相同 backbone feedback control、无 repository
integrity 回归，并通过机制分析证明接纳约束确实改变后续候选。具体最小 effect 和复现次数
必须在执行该 batch 前，根据 baseline variance 和统计功效预注册。

P8 之后，在 Canary 和 Official-Test 前不得修改 parser、repair operator、prompt、state
transition、internal check、预算或 candidate-selection rule。任何必要修改都创建新版本并
消耗新的预注册 development batch，绝不能在同一 held-out outcome 上调参。

## 11. 当前进度

- 已在 macOS 和 Docker 上本地复现 EnvBench 与 Repo2Run。
- `markqvist/reticulum@6ded42e` 已完成 EnvBench 评估。
- 常规 editable install 会产生 18 个 missing-import 问题。
- 空模块 stub 可以把官方 issue 数降为零，说明 benchmark 存在 fidelity 风险；本协议
  明确禁止此类做法。
- P0 harness 已完成：官方协议已机器可读；运行产物以原子方式写入，并包含生命周期
  状态和完整 provenance；evaluator failure 得以保留；每次运行都能独立审计。P0
  源码、数据集、预算、协议、scoring/diagnostic channels、registries、外部 revision
  和 evaluator image 已由机器可验证的 Harness Freeze Manifest 进行内容寻址。
- P1 正在进行：Dev-5、Canary-20、Train-Rest 和 Official-Test 已冻结；deterministic
  与 DeepSeek V4 Pro FreeAgent 的 Dev-5 baseline 已完成；Repo2Run 和 EnvBench
  ReAct adapter 可生成具备凭据保护、输入完整性检查且可重放的脚本。Repo2Run Dev-5
  和其余 EnvBench agent-family baselines 仍待执行。
- P2 已完成：类型化、hash-chained 状态内核已接入真实 `StatefulSolverLoop`；每个动作
  结果都成为证据；action 和 goal budget 均有显式终态；snapshot 原子化生成并可独立
  审计；一条包含 25 个命令的记录轨迹可以从 103 个事件确定性重建。
- P3 已完成：benchmark-independent 类型化约束可规范化 runtime、package、
  capability、module 和 platform 证据；高置信度冲突包含以证据为依据的解释；policy
  wrapper 会在动作进入 P2 executor 前检查其声明的 effects。17 个合成测试和两个已
  消耗 Dev 结果的离线回放全部通过，未调用模型，也未执行新 benchmark case。任意
  PEP 440 范围交集的空集求解与实时原始诊断捕获被明确留到 P4 扩展。
- P4A 类型化修复内核已完成，但 P4 整体仍在进行。repair plan 现在会声明类型化
  effect、待替换事实、风险、provenance 和独立 probe。transition-aware preflight
  允许修复替换冲突事实，但绝不允许替换 requirement；只有 probe 观测到 proposed
  fact 后，旧事实才会变为 `superseded`。13 个合成测试全部通过。对两个已消耗 P3
  冲突的只读回放均命中了通用算子族，但由于尚未观测 runtime manager、可用版本、
  package manager 和 capability-package context，可执行 plan 数为零。下一步是构建
  能产生证据的 context acquisition。
- P4B 证据化 context acquisition 已完成，但端到端 P4 仍未结束。现在已有可恢复的
  只读 probe policy 和严格 context builder，用于记录工具存在性、runtime inventory、
  system manager 和 provider-backed package candidate。11 个合成测试全部通过。
  在不挂载仓库且关闭网络的条件下，冻结 evaluator image 的 case-free 运行完成了
  7 个 probes，观测到 `pyenv`、从 `3.8.18` 到 `3.13.1` 的 6 个 Python 版本以及
  `apt-get`；其 39-event 状态轨迹无 failure 且独立审计通过。这些证据在完成
  provenance transfer 后可以支持 runtime 修复；capability-package 与
  module-distribution discovery 仍是下一步。
- P4C 镜像 provenance context transfer 与一个开发集 runtime transition 已完成并
  冻结，但 P4 整体仍未结束。context transfer 现在必须同时通过精确 image ID、
  repository digest、源状态哈希、case manifest、audit 和原始结果哈希检查。6 个
  合成测试覆盖匹配迁移、幂等性、mismatch 拒绝、证据筛选和 runtime execution
  contract。在已消耗的 `automl/neps` 冲突上，保留的第一条诊断轨迹表明，仅执行
  `pyenv local 3.11.7` 无法覆盖镜像中 Conda 优先的 `PATH`。随后，通用且由证据
  推导的 pyenv-shim execution contract 使未修改的冻结 repair 与独立
  `python --version` probe 成功验证 3.11.7，仅 supersede 被反驳的 3.13.2 fact，
  并使类型化状态变为 satisfiable。两条轨迹均关闭网络、不挂载仓库、可独立审计，
  且明确不能计为 EnvBench 成功。要达到 P4 退出条件，仍需完成 capability/module
  discovery 与多 case repair 闭环。
- P4D capability discovery 已完成并冻结三轮开发实验，但 P4 整体仍未结束。Round 1
  表明 per-case 全量刷新 `apt-file` Contents 在工程上不可接受：provider bootstrap
  成功，但索引刷新在 600 秒超时，尚未进入 repair。Round 2 改为带 response hash 的
  Ubuntu 官方 Contents 定向查询，并使用本地 apt-cache 二次验证，找到两个精确且
  PATH-reachable 的候选。冻结 P4A 的 V1 presence probe 随后接受了
  `postgresql-common`，暴露出 verifier 假成功：`pg_config` 路径虽然存在，但
  `pg_config --version` 明确表示仍缺真正的开发包。Round 3 引入干净容器候选资格
  验证和 V2 semantic commit gate。在单独区分一次瞬时 apt timeout 后，只有
  `libpq-dev` 通过语义接口探针；第三个全新容器完成 V2-gated repair，仅 supersede
  一个 absent fact，并得到可满足且可审计的状态。这些结果说明后续需要 image/source
  级 provider cache 和类型化 capability-interface verifier。后续 P4E 补齐仓库安装
  replay、metadata 驱动的 module 修复与终态控制。
- P4E 仓库回放已完成，P4 已冻结。Dev-5 审计首先确认 EnvBench 的 `issues_count` 仅
  统计 `reportMissingImports`，而不是 Pyright 总错误数。唯一仍然 bootstrap 失败的
  `jaraco/inflect` 暴露出 verifier 自有 `build_output` 触发 setuptools flat-layout
  冲突。基于 provenance 的 relocation operator 只临时搬移并恢复该外部产物，使
  bootstrap 从 exit 1 变为 exit 0，并进一步暴露 3 个测试文件 module obligation。
  随后由项目 `pyproject.toml` 与 `tox.ini` 共同选择声明的 `test` extra，全程不假设
  import 名与 distribution 名相等。第一次回放因 Python wheel 下载 read timeout 被
  正确标记为 infrastructure-blocked；预注册的相同脚本重试后达到 `exit_code=0`、
  `issues_count=0`，并通过独立审计。Dev-5 最终达到 5/5 可审计环境终态，其中 2/5
  Official Pass，3/5 为 bootstrap 已满足但仍有 verifier obligation。整个过程没有
  模型调用、源码修改、import stub、held-out 检查或 repository-specific repair rule。
  P5 下一步必须分类可选/平台导入和 verifier 扫描范围产物；这 3/5 open case 不计为
  榜单成功。
- P5 已推进九个预注册开发 round。import 审计现在对运行时函数参数 fail closed：修正
  一条不可靠的默认值规则后，active obligation 从 17 增至 20，同时没有改变 finding
  identity 或官方 outcome。benchmark-independent 的 metadata 驱动 V3 合约已加入隔离
  import、entry-point 与 CLI probe、空工作目录、Docker 强制断网和三值判定。迭代暴露
  并修正三类通用问题：函数默认值不是已观测调用、legacy editable 使用
  `egg-link`/`PKG-INFO`，以及 build metadata 依赖 `.git` 时源码 tree 相同仍不充分。
  预注册 detached-checkout replay 在 24 个断网 probe 上达到 5/5 bootstrap Pass 与
  5/5 V3 Pass，全程没有源码修改、name guessing、case-specific map 或官方 verifier
  调用。严格三值的 V1 metadata-resolver 合约已通过 9 个定向合成测试，但尚无真实
  仓库 claim。P5 尚未冻结；真实 V1、V4、V6 仍未完成。
- 在继续调更多 case 前，Round 10 已完成一次全代码设计审计。已修复互斥范围被误判
  SAT、superseded 旧事实复活、context 缺少时间语义、V3 部分收集假阳性、CLI 惯例
  probe、ambient V1 假失败、pyenv 布局猜测、core 反向依赖 harness、macOS 专属临时
  路径，以及 workspace relocation 非事务化等问题。全套测试目前 181 tests passed。
  预注册的新合约 Dev-5 回放得到 3/5 bootstrap Pass 与 3/5 V3 Pass；实际执行的 21 个
  probe 全部通过，collection error 为 0。两个 unknown 分别保留为 Inflect 缺失外部
  `build_output` 实验夹具，以及 Poetry 包下载站连续超时。runner 已用通用、预注册的
  pre-bootstrap 目录合约修复夹具遗漏，没有加入 repository 逻辑。用户按要求确认切换
  网络后，Round 11 保持原有三个 pass，并恢复 Inflect 与 Poetry，最终在 24 个断网
  probe 上达到 5/5 bootstrap Pass 和 5/5 V3 Pass，probe failure 与 collection error
  均为 0。verifier policy、bootstrap、源码和官方 outcome 均未改变。P5 继续保持开放，
  下一步补齐真实 V1、V4、V6。事件重放已改为增量，但每事件完整写 snapshot 仍是
  Train-Rest 批跑前需要继续优化的扩展性问题。
- Round 12 的真实 V1 准备已让 V1 与 V3 共享项目 provenance 和网络隔离，不再复制
  collector。它对 installed 项目 requirement 做内容寻址，记录完整 installed state 与
  容器 marker environment，要求 extras 显式绑定到冻结 bootstrap 哈希，并只在断网后
  执行直接 resolver 证据。V1 policy 会先判定可归因的项目闭包冲突，再把其他无法归因
  的 ambient resolver 非零记为 Unknown。预注册回放在 23 个 active requirement 上得到
  4/5 V1 Pass，四次断网 resolver 均 exit 0，且无 collection error。Poetry 因包下载站
  超时在采集前停止并保持 Unknown；没有用真实 outcome 调整合约。Round 13 已消耗一次
  用户确认的基础设施重试，并精确复现四个 V1 决策及其 metadata/resolver 哈希；Poetry
  又因 `cmake` 下载不完整保持采集前 Unknown。本地重试到此关闭，后续服务器批跑需要
  独立预注册 dependency artifact/cache 可靠性协议。全套测试目前 188 tests passed。
- Round 14 的 V4 准备在观察 outcome 前冻结两种模式的 project-native verifier：内容寻址
  的显式 pytest 配置选择断网直接 collection，否则标准 Python build metadata 选择
  无 dependency、无 build isolation、输出到临时目录的 wheel build。planner 不执行项目
  任意 command，也不使用 repository identity。没有收集到测试为 Unknown，非零/timeout
  为 Fail，build exit 0 但没有 wheel artifact 也为 Fail。全套测试现为 195 passed。
  预注册回放达到 5/5 V4 Pass：两个断网、内容寻址的 wheel build，以及三个显式 pytest
  collection，分别覆盖 284、207、1668 个 selected test。所有 planner 证据均与冻结预期
  一致。这只是 collection/build 证据，不是 V5 test execution。
- Round 15 的 V6 准备把可复现性定义为两个独立 fresh container 的规范化状态完全等价，
  而不是 bootstrap 再次 exit 0。fingerprint 包含完整 installed distribution state、项目
  metadata/provenance、Python runtime 与 marker environment，并绑定同一冻结 plan identity。
  两次 replay 不共享可写 volume，且仅在断网后采集。缺证据为 Unknown，component delta
  为 Fail。pair runner 独立检查 snapshot hash、source identity、cleanliness、网络隔离与
  不同 container ID。全套测试为 204 passed；尚未宣称真实 paired execution。
  冻结的 Round 15 随后因 direct-file entry point 初始化 package path 过晚，在 Docker
  启动前失败。该零执行失败已保留；没有观察 V6 outcome，也没有修改 policy。新增直接
  CLI 覆盖后全套测试为 205 passed，真实 paired execution 必须使用新哈希的 Round 16。
- Harness hardening 已解决 batch cancellation blocker：SIGINT/SIGTERM 会终止 case
  进程组、清理该 case 所属容器、取消排队任务、写入 interruption evidence，并保留
  可审计终态。
- Typed Replay IR v4 已使用 benchmark-independent 合成安全语料冻结。Official 与
  非计分 Diagnostic channel 已分离；P0 freeze verifier 可在不检查 Canary-20 和
  Official-Test-100 的情况下通过。
- 一次预注册的 P0 post-freeze Dev-3 运行完成，并审计了三个 first-attempt 产物。它
  揭示了在线依赖获取的非确定性，以及一个不影响计分的 failure-stage summary bug；
  后者已修复并在 Harness Freeze v2 中披露，没有改变 Official scoring 或原始结果。
- Round 16 按未改动的 prospective V6 合约执行并写出全部 10 个 required fresh-replay
  artifact。四个项目分别形成两个完整且全状态精确相同的 snapshot，得到 4/5 V6 Pass、
  0/5 V6 Fail、1/5 V6 Unknown。Gpkit replay A 在 snapshot 前下载 `plotly` 超时，而 replay B
  完成，因此这是基础设施阻塞而不是状态漂移。独立审计重算了冻结实现、raw result 与
  snapshot 哈希，并复核 source cleanliness、断网与 container identity 独立性；全部通过。
  frozen round 不允许本地重试。结果保留 V1 Poetry 与 V6 gpkit 证据缺口，进入显式
  freeze-readiness 审查。
- P5 已在不重跑、不重分类两个 infrastructure Unknown 的前提下，通过只读 evidence-matrix
  audit 冻结。最终 Dev-5 curve 为 V0 5/5，V1 4/5 加一个 Unknown，V2 2/5，V3 5/5，
  V4 5/5，V5 not measured，V6 4/5 加一个 Unknown；Official Pass 与 Robust Pass 均为
  2/5。四个 clean replay 覆盖三个 PEP 610 项目和一个 legacy egg-link 项目；Reticulum
  通过所有已测非 benchmark Robust level，但 V2 仍为 false，形成具体的榜单指标与环境
  质量差异案例。机器可验证 freeze 保持 Unknown fail closed，不含 case-specific verifier
  rule，也未检查 held-out case。服务器 dependency cache 现在属于 P6/P7 批跑可靠性任务，
  而不是 P5 调参义务。
- EnvSolve v0 研发已切换为 error-first、受复杂度约束的循环。通用分析器从已经消费的
  same-backbone FreeAgent Dev-5 trajectory 重建了全部 83 个决策：12 个命令失败，6 次
  失败后的精确重试全部集中在 Poetry，具有 6 个不同 output 哈希，并最终产生 1 次恢复。
  这否定了简单的失败命令禁重规则，但没有据此选择 retry 机制或任何其他 EnvSolve
  组件。最小 v0 agent 现已可通过通用 harness 执行：它保留相同的 ReAct bash surface，
  只增加固定的 `python -m pip check` 完成门。该 gate 必须是最后一个 action-state
  boundary，且不会进入 replay script。runner 注册、identity 传递、预算账本、仓库完整性、
  fail-closed finalization 和无凭据 CLI preflight 已通过 224 tests，并能生成可审计
  artifact。冻结的批后分析器会把不完整或损坏 trajectory 保留为带哈希的 analysis error，
  只分配可观察阶段标签，绝不根据 exit code 推断基础设施失败。配对 V0 Discovery Round 1 已在
  执行前冻结，包含 5 个 outcome-blind case、两个
  same-backbone condition、一个 seed、零自动重试和跨 case 的机制准入规则。当前仍未选择
  任何额外算法机制。
- Discovery Round 1 已完成 10 个冻结 first attempt，但不能用于 v0 机制推断：空的初始
  graph state 使 LangGraph 在第一次模型请求前终止。最小且与 benchmark 无关的 state
  schema 修复，以及使用已消费同一 case 的资格验证，得到 7/7 模型响应、一次通过的
  completion verifier 调用，且 transport 异常没有再次出现。剩余失败只来自 replay，
  因此 Round 1 没有准入算法机制。
- Discovery Round 2 完成 10 个新的 outcome-blind first attempt，全部 audit 有效且 provider
  error 为 0。EnvSolve v0 使用 67 次模型请求和 665,867 tokens；FreeAgent 使用 123 次
  请求和 1,702,574 tokens。两种方法都没有进入官方评测。5 条 v0 trajectory 中有 4 条
  通过固定 completion verifier，随后都被常规 `eval "$(pyenv init -)"` 的 replay 表示
  错配拒绝；第 5 条因在仓库内创建 virtualenv 而触发 repository integrity。该重复错误族
  达到预注册机制门槛，但被归类为基础设施表示债务，而不是 EnvSolve 算法贡献。
- Typed Replay IR v5 因此只增加一条语义规范化：精确的 pyenv 初始化转为显式 shim-path
  runtime action，其他 `eval` 与命令替换仍然 fail closed。策略、负对照和审计后的 v0
  recorded redistillation 已冻结到 Harness v3；全套 228 tests 通过。只读重蒸馏恰好解锁
  2/4 条触发轨迹，并保持另外两条拒绝。沙箱外官方评测随后得到 0/2 pass：
  pyfirebirdsql 的 bootstrap 成功，但有 11 个公开 issue 和 701 个 Pyright error；Islandora
  在 bootstrap 下载依赖时发生 read timeout，属于网络删失。这些是 development-informed
  诊断结果，不是 held-out 证据。
- 证据已经把第一个候选算法机制约束得很小：候选动作必须在干净环境中通过可插拔的
  executable verifier contract 回放，规范化 verifier counterexample 必须先写回显式
  solver state，之后才允许下一次 repair。设计应复用已冻结的 P5 verifier interface，
  不加入 repository map，并保持为一个统一循环，而不是 case-triggered heuristic 集合。
  只有在另一批单独冻结的未见 development batch 上同时优于 v0 和 same-backbone
  FreeAgent 后，该机制才正式准入。
- Counterexample Loop core 已在抽取任何新真实 case 前完成设计预注册和内容冻结。
  它只在现有 state/constraint kernel 外增加一个 benchmark-independent 元循环：提出
  完整部署候选，在具有唯一 identity 的 fresh environment 中执行 verifier；若得到被
  合约接受的 Pass 则终止，否则必须先持久化类型化 verifier evidence 及其 normalized
  constraint，才能进入下一次 proposal。Unknown、格式错误、无法规范化、环境复用、
  矛盾 Pass 和未验证自报成功均 fail closed；自由格式 action output 不会被隐式接纳为
  counterexample evidence。随后，真实 case 前的合成审计用 v2 取代 v1，只增加一道门：
  failure feedback 必须留下显式 constraint conflict，而不能只是可解析的 constraint。
  Structured Finding Adapter 随后审计到 v3：collector disposition 不能覆盖 verifier-owned
  goal decision，requirement/observation evidence 在不改变 normalized constraint 语义的
  前提下保留 finding provenance。EnvBench Finding Collector v1 已单独冻结：它保持精确
  官方目标，把 missing-import diagnostic 绑定到 revision-owned source，将全部可归因官方
  finding 保持为 goal-active，并把 P5 semantic disposition 单独保存用于 risk 与 Robust-Pass
  分析。在一个已消费 case 上的只读资格验证重建了 11/11 goal-active finding，其中 5 条
  semantic active obligation、6 条 guarded optional、0 Unknown，并排除了 690 条非环境
  Pyright error。9 个 core、10 个 adapter、7 个 collector 测试与全套 254 tests 均通过，
  没有新 benchmark execution 或模型请求。未见 batch 仍是准入前提，因此当前属于 recorded
  qualification，尚不构成算法准入。
- 新增算法协议时发现 Harness Freeze v3 存在 source ownership 缺陷：过宽的
  `experiments/protocols/*.json` glob 会把未来无关实验预注册误算为 harness source，
  却遗漏真实执行所依赖的 `envsolve/v0` 与 state runtime。Harness Freeze v4 现在只冻结
  harness 代码及其真实 runtime dependency；配置、官方协议、Typed Replay IR 和数据集
  继续使用原有独立哈希字段。该修订不改变 scoring、runner、replay policy 或历史结果，
  机器验证已通过。
- 在实现或运行真实 multi-round policy 前，第一篇论文范围已进一步收敛。EnvSolve 在线
  只能使用历史容器执行和预注册内部项目反馈；EnvBench 官方 evaluator 在 episode 结束后
  只调用一次。已冻结的 EnvBench Finding Collector 继续作为 post-episode 分析 adapter，
  不能驱动 candidate repair。下一项工作因此改为预注册新的 internal-feedback runner，并
  配置预算匹配的 raw-history 与 reflection control。跨 case 自进化和 Agent RL 延后到
  EnvSolve 之后；第一篇只保留不可变 transition 与 environment artifact，使后续研究能够
  复用这些数据。
- P6 已形成可执行且与 benchmark 解耦的 runtime。结构化模型 policy 只能读取有界的只读
  仓库画像和历史内部执行状态，并输出一个累积式完整部署程序。Typed Replay validator 为
  脚本统一加入 fail-fast 合约，并拒绝 observation、source edit 与不支持的 mutation。每个
  通过验证的候选都在独立 Git checkout 和独立 Docker container 中重放，随后执行固定的
  `python-deployment-v1` 内部检查：`pip check`、字节码编译，以及项目存在 tests 时的测试
  收集。在线路径完全不包含 EnvBench 官方输出，官方评测仍受 episode 结束后的原子
  evaluation claim 保护。模型请求、candidate、environment、command 与 wall clock 共用
  同一个可恢复 ledger。
- Dev-extension split 上的两次 Civet first attempt 均作为开发诊断失败保留，不计入算法效果。
  R1 完成了一次可审计模型调用，但 candidate validator 在执行前拒绝了普通 virtualenv 创建。
  candidate language 现在只增加精确且有界的 venv 形式，并把被拒 proposal 同样写入 candidate
  lineage 和预算。R2 随后在 fresh container 中执行一个候选并通过全部 V1 内部检查，但 episode
  结束后的官方 evaluator 报告 16 个 missing-import issue，涉及 5 个 module name，同时有
  1,589 个 Pyright error。这揭示的是 verifier recall 问题：对没有有效测试收集的仓库，V1
  过弱。R2 还存在独立的实验有效性缺陷：旧的 execution-ledger 实例覆盖了模型请求和 token
  用量。原始 artifact 保持不变，独立 audit 现在会明确拒绝该 run。
- Harness Freeze v6 取代而不重写 v5。每次模型或执行侧预算变更前都会重新读取最新持久化
  ledger；所有模型驱动的 EnvSolve run 还必须具有可审计的请求、响应与 token 用量。Harness
  Freeze v7 随后加入与 benchmark 无关的 `python-deployment-v2` verifier：对 runtime/test/build
  import 做有界 AST inventory，在候选环境中解析 module，并输出类型化 module counterexample。
  它复用已有源码语义以区分 active import、inactive platform branch 和 optional import；同时把
  `except ImportError` 中的兼容 import 建模为替代分支：主分支可解析时为 inactive，两边都失败
  时为 Unknown，绝不任意挑一个升级成硬依赖。documentation、fixture、vendored source、项目
  本地 module 与官方 evaluator 输出不属于该检查范围。
- 全套 213 个 EnvSolve 测试和 62 个 harness 测试通过，其中一个真实 Docker 测试默认跳过；
  语法编译通过，显式 V2 Docker 边界测试单独通过，Freeze v7 已对 live evaluator image 验证。
  在已消费 Civet 源码上的只读反事实检查把 12 个 Python 2 fallback occurrence 全部判为 inactive，
  同时保留直接 Redis obligation；这只是 coverage qualification，不是重跑或分数。P6 仍未准入。
  R2 的官方反馈不得进入未来在线 solver state；下一次真实执行仅作为预注册、development-informed
  的同 case loop 时序与可审计性资格验证。
- 预注册的 Civet R3 资格验证完成 1 次模型请求（2,549 tokens），持久化 1 个被拒候选，未启动
  container，也未调用官方 evaluator。它通过独立 audit，但没有通过资格验证，因为模型输出了
  validator 正确拒绝的 shell control flow。这暴露的是通用接口缺陷而不是环境失败：validator
  持有的 candidate DSL 对 policy 不可见。Harness Freeze v8 将同一份精确 DSL 契约注入模型
  system prompt，但不放宽可执行 shell 语言；同时，所有已经持久化 budget 证据的失败 run 都会
  被审计，而账本创建前的缺凭据和 hard-timeout 失败仍可合法记录。R4 已在 v8 下单独预注册，
  仍然只是同 case、development-informed 的资格验证。
- R4 的 artifact 通过独立 audit，并真实形成两轮内部 loop，但没有通过资格验证。candidate 1
  因可归因的依赖下载超时结束，旧 V2 错误地允许该基础设施 observation 驱动 candidate 2，
  违反预注册 retry 规则。candidate 2 完成 bootstrap，V2 也在 candidate 3 前持久化了全部类型化
  evidence，但 source inventory 把 `RecipeReader` 和 `settings` 两个精确仓库内 legacy module
  误判为外部 obligation，诱导模型提出被禁止的 `PYTHONPATH=$PWD` workaround。该 run 共用
  3 次请求、28,274 tokens、3 个 candidate slot、2 个独立 environment，且未调用官方评测。
- Harness Freeze v9 在不使用 repository identity 或 module map 的前提下修复这两类错误。只有
  在仓库根或 import 文件的 project-owned 祖先链上存在精确 module path 时，才排除项目本地
  module；可归因网络 signature 现在产生 infrastructure Unknown 并终止 episode；危险 export
  名称也显式写入 validator-owned prompt contract。只读回放只移除两个本地假阳性，并保留
  `distutils` 与 `redis.exceptions` active obligation。全套 213 个 EnvSolve 与 63 个 harness
  测试通过，V2 Docker 边界通过，Freeze v9 验证有效。
- R5 通过独立 audit，并满足 V2 精度与事件顺序资格检查，但没有解出该 case。它使用 5 次模型
  请求、41,014 tokens、5 个独立 candidate environment，成本约 `$0.0233`，没有调用官方评测。
  前三个候选分别消耗在 package artifact hash mismatch、不支持的 pip option 和空 package-index
  response。candidate 4 完成 bootstrap；V2 恰好产生 3 个 active occurrence，对应两个语义 module：
  项目源码中的 2 个 `distutils` import 和 1 个 `redis.exceptions` import。R4 的两个本地假阳性
  没有复现。candidate 5 随后用 `pip install distutils` 暴露剩余推理缺陷，并耗尽冻结候选预算。
- Harness Freeze v10 只改进证据传递，不增加 package map 或 repair operator。模型 state 现在包含
  最近两次 structured verification 和完整 runtime facts；有界日志同时保留开头与 terminal error；
  system contract 明确禁止把 module name 等同于 distribution name。dependency artifact hash
  mismatch 现在以 infrastructure Unknown 终止。全套 213 个 EnvSolve 与 65 个 harness 测试通过，
  真实 V2 Docker 边界通过，Freeze v10 验证有效。R6 必须等用户明确确认本地网络已切换或检查后执行。
- 预注册 Civet R6 通过独立 audit，但未通过资格验证。它完成 3 次模型请求、24,100 tokens、2 个
  candidate、2 个 fresh environment，成本约 `$0.0133`，且没有调用官方 evaluator。candidate 1
  再次得到 active `distutils` 与 `redis.exceptions` obligation；candidate 2 仍把 unresolved module
  name 当作 package-index distribution，并在 `pip install distutils` 处失败。随后一次模型响应违反
  exact-JSON 合约，v10 将其作为 fatal policy exception，导致尚余 3 个 candidate slot 时提前结束。
  这是同 case 开发诊断，不是算法效果证据。
- Harness Freeze v11 将 proposal-level failure 纳入状态化求解过程，不增加 repository map 或 case
  rule。格式错误的模型输出现在会被哈希、截断、持久化并反馈给下一轮，连续错误上限为 3；candidate
  DSL 拒绝会消耗 candidate budget，但可在不创建 container 的情况下由下一轮修复。模型投影显式列出
  active module obligation，并包含最近 policy failure。全套 215 个 EnvSolve 与 66 个 harness 测试
  通过，显式真实 Docker 边界 1 项通过，隔离 bytecode cache 后语法编译通过，Freeze v11 验证有效。
  后续任何同 case 重跑仍不得解释为 held-out evidence。
- R7 通过独立 audit，并在 4 次模型请求、28,379 tokens、4 个 fresh environment、约 `$0.0173`
  和 2,126.8 秒在线 wall time 后得到内部 V2 Pass。官方 evaluator 严格在 episode 结束后只 claim
  一次，但未通过：`issues_count=15`，对应 4 个不同 missing module name：`ConfigParser`、`Queue`、
  `requests.packages.urllib3.exceptions`、`urlparse`；1,594 个 Pyright error 中有 1,579 个不是
  missing-import diagnostic。该分数只属于开发诊断。R7 资格无效，因为 candidate 1、2 都触发
  900 秒 harness timeout，而 v11 错把 exit 124 当作 candidate counterexample，让删失日志驱动了
  后续 proposal。R7 没有出现 malformed model 或 DSL output，因此没有直接触发 v11 新恢复分支。
- Harness Freeze v12 只做一项因果修正：harness 强制执行 timeout 一律为 infrastructure Unknown，
  不产生 counterexample，并立即终止 episode。全套 215 个 EnvSolve 与 67 个 harness 测试通过，
  语法编译通过，Freeze v12 验证有效。下一项算法矛盾已明确：semantic runtime import closure 可以
  Pass，但 EnvBench 的 static missing-import 目标仍会失败。任何 static-closure 扩展必须采用通用定义，
  先在合成 case 与新冻结 development case 上验证；Civet 的 4 个具体 module name 不得进入 repair rule
  或 package map。
- Harness Freeze v13 实现了预注册、与 benchmark 解耦的两层 import-obligation 契约。对于有界扫描
  得到的每个 runtime/test/build 源码 import，`python-deployment-v3` 将 runtime-semantic 执行与
  无副作用 static-source 解析保留为两层独立证据，再合成为一个类型化 module finding，并显式记录
  required、active 和 unknown layer provenance。Guarded import 与兼容 fallback 在 runtime 层仍为
  optional，但在 static source closure 中是必需项；`TYPE_CHECKING` import 只属于 static 层；对目标
  平台可证明不活跃的分支豁免两层。Static resolver 支持 Python/package/namespace/extension 路径、
  `.pyi`、`name-stubs`、标准库名称以及 editable import hook 映射且名称一致的物理 origin；名称与
  origin 不一致的动态 alias 不能冒充 static closure，无法支持的 importer 保持 Unknown。实现中不
  调用 EnvBench、Pyright 或 package index，也不包含 case name 或 module mapping。
- 冻结的 S1-S10 合成矩阵与真实执行 probe fixture 覆盖 active absence、物理解析、optional 和
  fallback import、动态 alias、stub-only `TYPE_CHECKING`、平台不活跃、runtime execution error 与
  unsupported-layout Unknown。全量回归 294 项通过、1 项 opt-in 测试跳过；该真实 fresh-container
  Docker 边界测试单独运行通过；语法编译通过。Freeze v13 校验有效，manifest SHA256 为
  `60079e6bfd12d9aead2172a47d334b7394eaac46965458c55b08fc3beefd4ba6`。
  尚未运行任何新真实 case，因此这只是机制验证，不是算法效果结果。下一项合规工作是单独预注册
  unseen development qualification batch，在匹配预算下比较 runtime-only admission
  ablation 与完整 V3。
- 下一项资格实验已按 outcome-blind 原则准备完毕，并由 Harness Freeze v15 冻结。5 个 case 在
  查看仓库前，按照预注册 salted-hash 规则从 SHA256 冻结的 Train-Untouched-201 中选出，永久划为
  development-only；剩余 untouched training pool 为 196 个。受控比较不再使用历史 V2 代码：
  两组共享完全相同的 V3 inventory、probe、模型、预算与 fresh-container 实现。
  `envsolve-runtime-only` 只消融 static-source evidence 的接纳，
  `envsolve-full` 同时接纳两层。冻结的交错 schedule 包含 10 个独立 episode，各自使用唯一 run ID，
  不共享 ledger 或 trajectory。全量回归 298 项通过、1 项 opt-in 跳过；语法编译与真实 Docker 边界
  均通过。Freeze v15 校验有效，SHA256 为
  `a3e837a92d090017b3d5a88b9ec887a10464f34f05b9accf5e9f36e2cd455c66`。
  Freeze 时尚未查看任何选中仓库，也未发出模型请求。
- Schedule position 1 随后产生了一条 audit-valid、但 qualification-invalid 的 harness 诊断。
  runtime-only episode 使用 1 次模型请求、5,740 tokens、1 个 candidate、1 个 fresh environment，
  成本约 `$0.00314`，官方 evaluator claim 为 0。一次普通 fixed-check failure 已标记
  `deterministic_counterexample=false`，却仍被错误放进 hard counterexample channel。Normalizer
  正确地把推断出的 Python version evidence 保持为 provisional，但 loop 错误要求每个
  counterexample failure 都必须形成 hard conflict，因而在 candidate 1 后 blocked。
- Harness Freeze v16 进行最小 evidence-admission 修正：含义不确定的 fixed-check 日志保留为
  grounded hypothesis，可以用于排序下一完整 candidate；只有类型化、有依据的 finding 才进入 hard
  counterexample channel。修复未使用 case rule、package map 或 evaluator feedback。Position 1
  不覆盖、不补跑，因此本批最多形成 4 个完整 pair 加 1 个仅 full-method 的 development observation。
  全量 298 项测试、语法编译与真实 Docker 边界均通过。Freeze v16 验证有效，SHA256 为
  `99b93549ae60f2f01314b59ce08b8f92d99910912cbe08300a8a5e07884871c3`。
- Position 2 的首次启动没有产生模型、candidate、environment 或 evaluator claim，在仓库获取阶段
  因 Hugging Face HEAD 请求超过 10 秒 read timeout 而失败。失败 artifact audit-valid 并完整保留；
  因为没有获得任何 method information，可以使用新 run ID 做 infrastructure retry。Harness Freeze
  v17 将不可变 repository revision 提升为共享 source cache，同时继续隔离 clean checkout、ledger、
  trajectory、script 与 container；pre-episode acquisition failure 也会被显式标注，不再与 EnvSolve
  episode failure 混淆。全量 299 项测试、1 项 opt-in skip、语法编译与真实 Docker 边界均通过；
  v17 验证有效，SHA256 为
  `45279af4a4c201d0aa49cd8dd250921cd8a983e4ad9f994225f56ffeddddbe77`。
  Position 2 的 revision 已进入共享 cache，当前等待按约定恢复本地网络后执行 retry1。
- 获准执行的 position-2 retry 通过独立 audit，但资格无效，且官方 evaluator claim 为 0。
  Candidate 1 暴露了 typed replay 表示不一致：允许激活项目根虚拟环境，却拒绝直接执行
  `.venv/bin/pip` 变更。Candidates 2、3 随后遭遇 Ubuntu mirror 502/connection failure；最后
  一次 900 秒删失执行被正确终止为 infrastructure Unknown。该不可变诊断使用 3 次模型请求、
  21,194 tokens、2 个 fresh environment，成本约 `$0.01175`。它不再补跑，因此从 schedule
  position 3 开始，本批最多仍能形成 4 个完整 pair。
- Harness Freeze v18 做了两项与 benchmark 无关的一致性修正。Typed Replay IR v6 仅接纳
  项目根 `.venv/venv` 中的 `pip` 与 `python` 可执行文件，并用绝对路径、嵌套路径作为负对照；
  网络分类器将明确的 upstream HTTP 5xx 与 apt connection failure 识别为 infrastructure
  Unknown。32-case IR 语料、32 项聚焦测试、300 项全量通过加 1 项 opt-in skip、语法编译和
  真实 Docker 集成都通过。V18 验证有效，SHA256 为
  `a9e03ee3e594e8cef8912e72d2877fcffe0caf78d68cb1e6e34afc1ed53c8fe2`。
  未引入 case-specific mapping 或 evaluator-derived rule；下一项合规动作是已冻结 schedule 的
  position-3 runtime-only episode。
- Position 3 形成第一条干净的 calibration observation。Runtime-only 在 2 个 candidate、2 次
  模型请求、8,234 tokens、2 个 fresh environment 和约 `$0.00459` 后达到 internal Pass。首次
  终局评测在 Pyright 运行前因包下载 read timeout 被删失。Freeze v19 独立地把“bootstrap 非零、
  Pyright 未运行且命中网络签名”的结果分类为 evaluator infrastructure Unknown，并只允许一次新
  run、原脚本完全一致、零模型调用的重试。V19 验证有效，SHA256 为
  `152e2ff0d89f396323fdd44baf48e628b09cf609d78af7dc7ffa189219fe35a9`。通过 audit 的重试完整
  执行：bootstrap 成功，官方静态目标报告的两个 module 恰好是 runtime-only 未解析但判为 inactive
  的两项。因此 runtime-only 是 `issues_count=2` 的正式 Fail，而非基础设施结果。
- Position 4 使用完全独立的 full-method 状态。Candidate 2 将上述两个 static obligation 与一个
  build-source obligation 接纳为 hard constraint，但下一项 system-package candidate 达到 900 秒
  command timeout。该 run audit-valid，分类为 infrastructure Unknown；使用 3 次请求、17,992
  tokens、3 个 fresh environment、约 `$0.01019`，evaluator claim 为 0。它不再补跑，因此 pair 2
  不完整，只能支持 calibration 分析，不能给出 paired effectiveness estimate。
- Position 4 audit 还发现终止 wall-time 记账过期：command timeout 已执行，但持久化 ledger 停留
  在 candidate 启动时，低估了 episode 时间。Harness Freeze v20 在每次写 SolverResult 前 finalize
  并关闭共享 ledger；runner v0.2 audit 强制要求 `finalized_at`，封存后的写入关闭式失败。全量
  306 项测试通过、1 项 opt-in skip，语法编译与真实 Docker 集成通过。V20 验证有效，SHA256 为
  `b178c71cd98578273c484442afb193ba2017a61c687091ae6ef90ebd79912e95`。
- 资源上限选择现在属于显式开放的评测协议，而不属于任务定义。进入 held-out 前，
  `P6_BUDGET_CALIBRATION_PROTOCOL_V1` 将 EnvSolve 视为 anytime solver，通过因果轨迹前缀报告
  `K={1,3,5}` candidate/environment 前沿；`K=5` 是预注册排行榜配置，不宣称为天然最优值。
  模型调用上限由控制流推导为 `3K`。对比匹配模型、token、environment、command 和时间等原始
  资源上限；带日期的美元估计只作为 ledger 附属字段和非绑定运营断路器。
- 主 runner 现在具有最小类型化操作边界。Hard conflict 被投影为带 provenance 的
  `OperationPlan` requirement；`constraint-operation-guard-v1` 要求 fresh execution 前出现
  类型允许的新 mutation。被 guard 拒绝的候选消耗 candidate/model 预算，但不会伪装成真实执行
  历史。Event contract 为 EnvSolve-RL 保留 constraint-action-outcome 监督数据，为
  Auto-EnvSolve 保留 coverage 诊断，同时 EnvSolve v1 不进行跨 case 检索或更新。聚焦测试、
  全量回归（`308 passed, 1 skipped`）、语法编译和真实 Docker integration 均通过。
- Operation qualification Q1 已永久关闭并仅作为 harness diagnostic。第一组 pair 暴露出共享
  表示不一致：candidate validator 接受受限的项目虚拟环境创建，operation guard 却拒绝同一动作。
  Typed Replay IR v6 现在让两者共享唯一表示；全部五个 Q1 case 均保持 development-consumed。
- Q2 在第一组 audit-valid 负向 pair 后永久关闭。Full EnvSolve 在不创建 container 的情况下拒绝了
  一次精确重复候选，但后续 hypothesis-only failure 错误清除了仍未解决的 hard conflict。通用状态
  修正把 fresh verification 视为部分观测：只有后续新 fact 与旧 fact 具有相同 domain、subject、
  predicate 时，旧 fact 才会 supersede。合成 transition 测试同时证明“未观测则保留”和“同变量
  新观测则替换”；Q2 没有 official evaluator claim。
- Q3 从剩余 186-case pool 中预注册并 outcome-blind 选样，随后按冻结 adaptation rule 在第一组
  pair 后关闭。两种方法都 audit-valid、official evaluator claim 为 0，但都触发共享的 64K feedback
  contract。只读重建显示，旧 fallback 后 free-form 仍有 108,802 chars，full 有 109,760 chars。
  根因与 case 无关：逐字符串截断不能限制 constraint、verification、candidate、hypothesis 和
  operation-plan collection 的 aggregate size。全部五个 Q3 case 均保持 development-consumed；
  allocation pool 还剩 181 个 case。
- 新 context projection 只暴露紧凑的未解决 conflict、最近两份累积式候选、verifier 摘要、有界
  hypothesis，以及仅 full EnvSolve 可见的按 domain 与允许 action kind 分组的 operation
  requirement。每个字段都有确定性的 aggregate JSON budget。对 Q3 触发状态的只读回放中，
  free-form 为 40,114 chars，full 为 27,526 chars，均不需要字段 wrapper；高基数合成测试也满足
  最小 4K contract。61 项聚焦测试、全量 `324 passed, 1 skipped`、语法编译和真实 Docker
  integration 均通过。继续真实 case 前，必须建立新的 mechanism freeze 和 outcome-blind Q4 batch。
- Q4 完成了全部五组 pair，十条轨迹全部 audit-valid。在四组非删失 pair 中，full EnvSolve
  得到一组 full-only official pass、一组共同 pass 和两组共同 fail，没有 ablation-only pass；
  另一组因 full condition read timeout 被删失。四条 full episode 触发 typed operation requirement。
  full-only pass 修复了两个显式 module obligation；在共同 pass pair 中，full 于 candidate 2 解决
  9 个 obligation，free-form 则到 candidate 5。这足以让 operation mechanism 继续开发资格，但不支持
  paper-level effectiveness claim。
- Q4 同时发现共享 candidate-language 缺口：`.venv` 可以承载所有安装，却不成为 verifier
  runtime。Candidate policy v3 现在要求每个被创建的 `.venv` 或 `venv` 都必须随后在匹配路径上激活。
  合成顺序与路径测试、全量回归（`330 passed, 1 skipped`）、语法编译和真实 Docker integration 均通过。
  Q5 已在 metadata-only 选样前预注册，从剩余 176-case pool 中冻结 5 个新 case，仍有 171 个未触碰。
- 随后的全仓库 hardening review 把 evidence preservation 与 scientific admissibility 分开。原审计
  保留为 artifact-integrity check；新的 eligibility 层拒绝未提交源码、原始预算超限、不完整 heartbeat、
  host suspension 嫌疑和 schedule identity 错配。Q4 仍是 10/10 artifact-valid，但由于早于 Git
  baseline，0/10 具备 scientific eligibility。Q5 同样被排除，其中四个 episode 还在主机休眠后超过
  冻结 generation wall-clock。两批都不能估计 treatment effect，也不能在机制改变后重跑。
- 一个通用 schedule coordinator 取代了五份复制的 qualification driver。它执行进程组硬截止、原子
  记录不可变 position 转移、续跑时保留旧结果、删失 orphaned position，并拒绝变化后的 schedule、
  config 或 protocol hash。确定性 summarizer 执行双层审计、校验 schedule identity、哈希全部核心
  evidence artifact，并把描述性观察与科学估计分开报告。
- Complete Candidate v4 与 Typed Replay IR v7 关闭两个执行语言缺口。项目根虚拟环境按有效路径而不是
  `.venv` basename 匹配；受限的 `pdm install/sync` mutation 被允许，而 PDM script 和发布仍被拒绝。
  对 Q5 Giskard 的只读回放表明，V6 拒绝的两个 proposal 现在都能进入语言；这只验证语言覆盖。
  全量回归为 `343 passed, 1 skipped`，真实 Docker boundary 通过。
- Q6 是修正 scientific contract 后第一批 10 个 run 全部 artifact-valid 且 scientifically eligible
  的 operation batch，但 official pass 为 0。四组 pair 因 generation 未进入 official evaluation
  而被删失；唯一进入 official 的 `rebench` pair 为双方都失败。Full 将 `issues_count` 从 28 降到 1，
  但内部 verifier 漏掉了最后一个 documentation import。其余三个非 timeout case 的两种 condition
  都耗尽 5 个 candidate；`datasets` 还暴露出普通 command timeout 被误标为 infrastructure failure。
  因而 Q6 否定了“当前被动式 operation plan 已经足够”的假设。
- 两项通用修正在 Q6 后完成，均不含 case 或 package rule。Documentation 与 runtime/test/build source
  一起进入有界两层 import inventory；command timeout 只有在 partial log 含明确 infrastructure
  signature 时才删失，否则作为 candidate feedback，并可通过 hypothesis 驱动下一 fresh candidate。
  全量回归为 `347 passed, 1 skipped`，显式真实 Docker boundary 通过。Q6 保持 consumed、永不重跑。
  Q7 前必须定义保守的初始 observation-to-constraint admission，并把带补丁的 EnvBench evaluator
  固化为干净、可分享的 revision。
- Fresh verification 的状态合约现在具有显式正观测通道。一份完整报告可以同时说明一个变量已经满足、
  另一个变量仍被违反；只有 domain、subject、predicate 相同的新 fact 才会替换旧环境 fact。Unknown
  或不完整报告不接纳任何正事实。跨 candidate 合成测试、全量回归（`351 passed, 1 skipped`）和
  opt-in Docker fresh-environment integration 均通过。这只是 pre-action admission 的前置条件，
  不是效果结果；本轮没有运行任何新 development case。
- 保守的 pre-action admission 已覆盖标准声明式 package requirement。有界、无执行的 observer 只接纳
  无 marker 的 PEP 621 dependency、`setup.cfg` `install_requires` 和顶层 `requirements*.txt` 中的
  PEP 508 条目；environment marker、directive、格式错误声明、runtime requirement 和源码 import
  猜测都不接纳。每条 evidence 都携带源路径与内容哈希。Constraint-driven EnvSolve 在 proposal 1
  前接纳这些 requirement；free-form condition 运行同一 observer，但不获得类型化初始约束。
- Python deployment verifier v4 使用固定 `importlib.metadata` package observation 闭合状态循环，
  区分 distribution 缺失、版本不兼容以及 presence/version 已满足，并用正事实只替换同变量的旧
  package fact。全量回归为 `358 passed, 1 skipped`，语法编译与 opt-in 真实 Docker boundary 均通过。
  本轮没有运行新 development case 或官方 evaluator；Q7 仍需先固化干净、可分享的 EnvBench
  evaluator revision，再建立新的 mechanism freeze。
