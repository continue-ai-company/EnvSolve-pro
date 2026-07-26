# EnvSolve-Pro 研究计划

## 1. 研究目标

EnvSolve-Pro 研究陌生仓库的自动环境部署。核心问题保持不变：部署不是自由命令试错，而是一个
**部分可观测的状态化约束求解过程**。系统仍采用三层闭环：

1. **观测层：发生了什么？** 保真记录仓库证据、执行结果、环境身份和不确定性。
2. **约束层：现在缺什么、冲突在哪里？** 维护带证据来源的事实、假设、冲突和未解决义务。
3. **操作层：怎样改变环境来解除冲突？** 由强模型提出完整部署方案，系统验证执行边界和状态转移。

EnvSolve-Pro 从冻结的 EnvSolve v1 代码和历史继续开发。旧仓库
`hongleo-Lee/EnvSolve` 已在提交 `07a208f` 以标签
`envsolve-v1-baseline-freeze-2026-07-21` 封存，作为可运行 baseline；所有新改动只进入
`hongleo-Lee/EnvSolve-pro`。

## 2. 研究原则

### 2.1 成功优先

主目标是 Official Pass@1 和可重放部署成功率。Token、模型调用、容器、命令和 wall-clock 是效率
指标，不是问题定义。系统仅保留防止无限循环和失控执行的宽松安全上限。确认性实验另外报告
success-resource curves，不以美元价格作为核心变量。

### 2.2 结构增强而非替代模型推理

强模型始终可以访问有界原始观测。约束层是带 provenance 的外部状态，不是唯一上下文。确定性 hard
guard 只保护任务边界、安全边界和被执行证据直接反驳的精确行为；其余约束作为可质疑的 belief 或
advice。模型可以提出 schema 未覆盖的操作，系统执行后再决定是否扩展状态。

### 2.3 Baseline-first

在提出新算法改动前，先真实运行 Repo2Run、Codex/native agent 和同 backbone raw ReAct。阅读代码只能
解释实现，不能替代对完整轨迹的观察。外部 baseline 的容器策略、反馈 loop、停止原因和失败恢复必须
进入统一轨迹分析。

### 2.4 防止开发集过拟合

诊断 case 与验证 case 分离。每个算法假设先由跨仓库失败模式和 repository-free 反例支持，再在新的
outcome-blind Dev batch 上验证。已经看过结果的 case 只能用于诊断，不能再次承担确认性证据。
Canary 和 Official Test 在算法、baseline 与分析规则冻结前保持 untouched。

### 2.5 开发阶段平台并行

Mac 和 DGX Spark 都可执行 Dev case，以提高实验吞吐。平台、架构、镜像 digest、网络状态和 provider
必须记录在轨迹中。开发阶段不把 host OS 当作算法变量；同一 paired comparison 尽量在相同执行镜像和
平台上完成。跨平台一致性在机制稳定后单独验证。

## 3. v1 资产审计

原样继承的基础设施：

- benchmark-independent runner、EnvBench adapter 与 Official evaluator 隔离；
- fresh environment provider、artifact manifest、审计与 schedule coordinator；
- append-only event log、hash-chained state、evidence provenance；
- Repo2Run runner、raw agent runner、结果汇总和失败分析；
- 已有单元测试、集成测试与冻结协议。

保留但必须重新验证的算法组件：

- `EvidenceNormalizer` 的 schema 覆盖率和错误硬化率；
- 固定 confidence threshold 是否有统计或语义依据；
- `domain -> operation kind` 映射是否遗漏强模型可发现的方案；
- typed replay validator 是否误拒绝合法部署程序；
- operation guard 是否带来终局收益，而不仅是可审计性；
- transcript 压缩是否保留解决当前冲突所需的原始证据。

## 4. 实验路线

| 阶段 | 目标 | 主要产物 | 进入下一阶段的条件 |
|---|---|---|---|
| P0 | 亲自观察外部 baseline | Repo2Run、Codex/native、raw ReAct 的统一轨迹与错误分类 | 至少 5 个新 Dev case，每种方法均有可审计 run |
| P1（完成） | 建立公平比较接口 | 开放程序、fresh execution、effect audit、adapter precondition | 6 条已消费轨迹均无表示层拒绝 |
| P2（完成） | 找出主要矛盾 | 跨方法 failure decomposition | 一个高频、可干预且非 harness 假象的瓶颈 |
| P3（完成） | 验证候选保留机制 | certified/admissible 状态及已消费配对重放 | terminal reach 为 `2/3` 对 `1/3`，Official Pass 无增益 |
| P4（完成） | 量化剩余主要矛盾 | Spark 上两组独立的 8-case Dev 普查 | 单层复现失败，接口级信号已冻结 |
| P5（完成） | 验证因果约束前沿 | V2 测量否决与 V3 完整性修复 | 保留为诊断 baseline，不做效果 claim |
| P6（完成） | 观测各方法与官方目标的关系 | 16 个已消费仓库上的 causal-v3、Codex 与 Repo2Run | 一个跨方法、仓库无关的主要矛盾 |
| P7（进行中） | 验证可执行目标驱动的状态 | 冻结 `goal-contract-evidence-anchor-v1` 后进行 repository-disjoint qualification | 目标保真、多轮修复且无 evaluator 泄漏 |
| P8 | 受控效果实验与冻结 | goal-aware 配对、untouched Dev、Canary 与 Official Test | 代码、prompt、目标、baseline 与分析全部冻结 |

P0 期间不得根据 EnvSolve v1 的既有 case 添加仓库特定规则。新的 parser、constraint 或 guard 必须来自
多个独立轨迹，或者来自任务定义本身的确定性不变量。

### 4.1 P0 审计结论

五个 case 的 P0 batch 已完成。20 个计划方法位置没有出现 official pass，但这不是 effectiveness 估计：
Codex 有 4 个位置因 executable drift 变成 Unknown，wrapper 也独立删失了原生轨迹。Repo2Run 与 raw
ReAct 各自在原生环境解决 2 个 case，冻结 EnvSolve 在 fresh container 中内部接受 2 个方案。其中 3 个
原生成功没有进入等价的官方执行，原因是 replay 丢失成功操作或其 ambient runtime；EnvSolve 的两次内部
接受也都暴露了 internal-versus-terminal contract mismatch。

因此 P0 的主要矛盾首先是方法学问题：强 native solver 可以构造工作环境，但封闭的 post-hoc command
parser 或不等价的 verification workspace 会抹掉成功。在 P2 把剩余失败归因给部署算法前，P1 必须先修复
这个接口。

P1 遵循一个最小原则：把模型的完整 candidate program 视为开放程序，在隔离的 fresh environment 中执行，
再根据可审计 effect 与 executable postcondition 判断安全性和正确性。command schema 仍可用于状态摘要与
causal replay，但 schema 未覆盖本身不能证明 candidate 无效。benchmark adapter 必须声明 workspace
precondition，使内部执行和 terminal execution 从等价的非 outcome 状态开始。

### 4.2 P1 审计结论

P1 已完成。6 条冻结 Raw ReAct/Repo2Run 轨迹全部可编译，没有 unsupported operation；5 次最终官方重放
全部到达 terminal evaluation，没有 representation rejection，但也没有 Official Pass。这个负向效果结果
是有信息量的：公平接口暴露出真实残余 Pyright 失败、原生测试与榜单目标不一致，以及 `build_output/`
引发的 package-discovery 冲突，而不是用 Unknown 把它们遮住。

冻结 EnvSolve 的 `importlib_metadata` 候选在 materialize adapter 声明的 `build_output/` 后，也在内部验证
中失败。因此 P1 按冻结预测解决了 P0 的测量矛盾，没有加入仓库特定 solver rule。详细证据单独保存在
`PRO_P1_FAIR_INTERFACE_RESULTS_V1_ZH.md`；这些已消费 case 不能再支撑下一阶段效果声明。

### 4.3 P2 冻结诊断设计

P2 从剩余 118 个 untouched Dev 中仅按元数据抽取 6 个 case，执行 24 个 salted position：Codex native、
Repo2Run、raw ReAct 和 P1 EnvSolve-Pro scaffold。主分析单位是最早决定性修复机会，归因到 Observation、
Constraint、Operation 或 unresolved。只有同一可干预矛盾出现在至少 3 个仓库和 2 种方法中，才允许提出
新机制；抽样后整批 immutable，禁止修改 solver 或 wrapper。

### 4.4 P2 审计结论

24 个位置已全部完成。由于多数 Codex、Repo2Run 位置以及两个 raw ReAct 位置受到 baseline adapter 或
完整性审计删失，本批不能作为效果对比。EnvSolve-Pro 与 raw ReAct 分别在不同仓库获得一次 Official
Pass，把它们写成可比较的 1/6 会违反实验有效性。

三个仓库出现了同一个确定性主矛盾：完整性有效的候选以零退出码完成内部执行，但任何残余内部约束
都会让 EnvSolve 丢弃候选，不进入终局评测。部分内部证据被当成了精确 terminal oracle。因此 P3 只
引入一个最小区分：`certified` 候选满足内部目标；`admissible` 候选完成安全重放，但仍有未解决内部
约束。系统保留最佳 admissible 候选，并可用 `uncertified` 状态输出；内部目标仍为 blocked，Official
evaluator 仍然 terminal-only。

第二个跨仓库模式是 runtime、dependency lock 与 platform compatibility。它被冻结为次级假设；在更小的
候选保留机制得到资格验证前，P3 不实现这套更大的结构。

### 4.5 P3 资格实验结论

候选保留通过了已消费 case 上的资格门：处理组 `2/3` 进入官方终态，无保留对照为 `1/3`；两组
Official Pass 都是 `1/3`。唯一一次 retained-candidate release 明确标记为 uncertified，内部 goal 仍为
blocked，并因 22 个残余 issues 未通过官方评测。因此它只被验证为 terminal censoring 修复，不能写成
效果提升。

在实现 runtime closure 或其他机制前，P4 从未见 Dev 池盲选 8 个 case，将完整轨迹归类为操作不可行、
观测缺口、闭包缺口、evaluator gap 或成功。聚合结果冻结前禁止修改算法。

### 4.6 P4 普查结论

第一组由 closure gap 领先（`4/8`），独立复现组则由 operation nonviability 领先（`4/8`），因此预注册的
单类别复现标准没有通过。稳定结论位于更高一层：operation 与 closure 合计分别占 `6/8` 和 `5/8`，
合并为 `11/16`。机制审计把这些标签归结为三个反复出现的原因：runtime/platform 前沿缺失；表面义务
缺少 scope 与因果父节点；effect/evaluator 信任边界既过硬又可被绕过。12 个 case 达到 5-candidate
上限，证明它是会删失搜索的诊断限制，不适合作为主协议。

P5 先修复测量信任边界，不把它写成算法增益；随后只验证一个最小的因果约束前沿机制：原始证据始终
可见，只提升有执行依据的根条件，把有 scope 的表面症状连接到根因，同时保持强模型动作空间开放。

### 4.7 P5 因果约束前沿

P5 不增加封闭 planner 或 case-specific rule。它把约束层从平铺义务改成一个只读 derived view：

```text
带 provenance 的原始观测
-> 按观测通道更新的当前 scope
-> 有可执行证据的根条件与 surface-to-root 边
-> 强模型自由生成下一份完整部署程序
```

不同观测通道不能被同一个全局时间戳粗暴清空。若新候选在模块探针前失败，上一轮模块根因仍处于
部分可观测状态；若新的模块探针证明根因消失，旧根因退出当前前沿。前沿不修改 hard constraint，不
丢弃历史 raw event，也不限制操作空间。

在两组已消费 P4 轨迹上的离线资格分析中，`94` 个表面模块义务中 `93` 个可归入 `37` 个可执行根因；
最大症状放大为 `25:1`。另外两个不同仓库的原始 artifact 中出现 `7` 次精确 PyO3/Python 兼容性边界，
但旧的有界状态没有稳定保留它。该结果只证明表示问题跨仓库存在，不证明成功率提升。

V1 实现 `8e79eab` 暴露的是三类测量问题，而不是可用的效果估计：根因会因后续沉默被错误移除，shell
控制流可绕过后置验证，宿主 effect audit 会跟随只在容器内有效的解释器链接。V1 artifact 只保留为诊断，
不与后续结果合并。V2 在 `d250549dd29745887fe7fd1db4026b4d37aca384` 冻结最小通用修复，并按照
`pro_p5_causal_frontier_paired_v2_preregistration.json` 重跑相同已消费配对。模型、verifier 目标、开放
程序接口、候选保留和 evaluator 边界不变；仍然只比较 flat 与 causal state。只有完整性与机制门槛都
通过后，才抽取新的 outcome-blind Dev batch。

V2 的基础设施重试完成后，冻结分析仍未通过测量门。三个 causal episode 共记录 16 个模型决策；其中
LangGraph candidate 2 持久化的是整个 frontier 的截断包装，而不是含 `causal_roots` 的结构化对象。
事后审计精确定位到这 1 次失效，并将 `measurement_integrity_ok` 与 `effect_analysis_admissible` 都判为
false。因此 causal `1/3` 与 flat `0/3` 的表面 Official Pass 差异只能用于诊断，不能作为算法收益。

最小 V3 修复把完整内部 frontier 与模型投影视为两个版本化对象。模型投影在固定字符预算内先保留
causal root，再用剩余空间保留环境事实，并显式报告 omitted count；不再截断整个 JSON。另一个通用
修复让 verifier 正确解释 `sys.version_info` tuple guard，避免在新 Python 上把不活跃的 compatibility
import 硬化为义务。V3 先只在相同三个已消费 case 上运行完整性 canary；Official Pass 不进入 canary
gate。只有每次决策的模型可见投影都通过 hash、schema、结构和 root-completeness 审计，才冻结后续
multi-block flat/causal 配对。

### 4.8 跨方法轨迹普查

下一版算法必须来自配对轨迹统计，而不是另一个孤立 case。两组已消费 P4 census 的完整并集提供 16 个
仓库，不打开 untouched 数据。当前 EnvSolve-Pro causal-v3、Codex CLI 和 Repo2Run 在相同 case identity
与未修改 terminal evaluator 下运行。官方目标严格等于 bootstrap 退出码为 0 且
`reportMissingImports` 为 0；其他 Pyright error 不参与机制选择。

每个 case 识别最早决定性分歧属于观测层、约束层、操作层、终局化还是基础设施。只有某一类别唯一最大、
覆盖至少四个仓库，并能写成 repository-independent counterexample，才允许进入下一版。Mac 运行
Codex，Spark 运行 EnvSolve-Pro 和两条互不重叠的 Repo2Run 队列。本批仅用于诊断，不能支持 held-out
或榜单结论。

对前两组已消费 census 的目标对齐审计显示，9 个可比较最终候选覆盖了 `40/41` 个官方缺失模块，但
70 个内部模块义务中有 30 个不对应官方 missing import，其中 25 个集中在同一仓库。这只是 precision
假设，还不是主要机制；只有它在冻结的跨方法普查中跨仓库反复成为最早决定性分歧，才允许据此改算法。

### 4.9 P6 跨方法结论

完整普查得到一个比继续增加依赖规则更简单的主要矛盾：**可执行任务目标没有成为持续可见、具有权威性
的状态变量**。原生 Agent 经常在没有执行计分目标时优化仓库测试或文档等代理目标。causal-v3 虽然运行
丰富的内部 verifier，但语义推断可能移除真实目标义务，也可能保留不计分义务。c14 的 Codex
state-parity 复核进一步表明，一个表面成功的生成仍可能留下 37 个官方缺失导入，而轨迹中从未运行
Pyright。

因此，因果前沿不再是论文中心。它作为冻结的结构化 baseline 和可选消融保留。下一版本首先必须用公开
可执行成功标准锚定状态；语义压缩可以注释该状态，但不能覆盖它。

### 4.10 P7 可执行目标契约

`EnvSolve-Pro goal-contract-v1` 引入一个通用接口。版本化可执行目标包含公开描述、可信程序、报告
schema 和内容摘要。对每个候选，verifier 在同一个 fresh shell 中依次执行完整部署程序和目标。有效
报告产生 Pass 或带类型的 Fail finding；格式错误、能力缺失和基础设施事故产生 Unknown。目标 finding
作为权威 active obligation 进入约束层，直到后续执行证明它已满足。每份报告同时声明 finding set 是
complete 还是 partial；只有同一 scope 的完整快照才能通过“旧 finding 未再出现”解除它，部分证据
不能。强模型仍然生成不受封闭动作集合限制的完整 Bash 程序。

EnvBench adapter 将公开标准实例化为 bootstrap 成功且 `reportMissingImports` 为零；Pyright 代码不进入
通用 runtime。Official evaluator 仍然只在终局运行，永远不进入 loop。为了区分目标可见性和结构化
状态，`codex-cli-goal-aware` 获得相同公开目标，但没有 typed constraint loop。

第一个已消费资格 case `jaraco/irc` 获得 Official Pass 且计分 issue 为零，它只证明端到端兼容。第二个
已消费 case `censys/censys-python` 的冻结 causal-v3 曾丢失唯一的 `sphinx_rtd_theme` 义务，因此用于
检验第一轮可执行目标失败能否进入第二轮定向操作。

显式状态组与同模型 goal-aware raw-history 组都在 c10 的第二个候选完成修复并 Official Pass；该单次配对
中 raw baseline 使用更少 token 和时间。因此 c10 支持可执行目标反馈，但不支持结构化状态的额外增益。
审计还发现并修复了 stale-state bug：目标 Pass 后，同一版本化 evidence scope 产生的旧约束现在会被
明确 supersede。c15 的第一组诊断又暴露了对应的 Fail 转移缺口：穷举报告已经解决四个 finding 中的
三个，旧 requirement 却仍保持 active。报告契约现已区分完整 finding 快照与部分证据；修复前配对
禁止用于比较。

随后通过完整性检查的 c15 运行暴露了两个部分可观测状态问题：goal finding 没有包含解决动态 test
package 所需的仓库局部构建语义；新候选还会遗忘早期候选已经满足的依赖。
`goal-contract-evidence-anchor-v1` 用有界的 finding 定向源码证据和一个完整执行、通过准入的保留候选
锚点解决这两个问题，同时保持开放 Bash 操作空间。新的 c15 机制运行在 11 个候选后通过 Official
evaluation，计分 issue 为零。

在已消费 c16 上，具有相同源码证据和锚点的显式状态组与同模型 raw-history 组都在 3 个执行候选内
Official Pass。显式组使用 3 次模型请求和 40,438 tokens；raw-history 使用 4 次请求和 90,748 tokens，
其中一次输出因违反 schema 在执行前被拒绝。这个单次配对既不支持成功率优势，也不支持候选数优势；
它只提出一个待预注册验证的假设：在多 finding case 上，显式状态可能降低模型侧上下文与重试负担。
上述 case 都不是 held-out 效果证据；详细证据记录在
`PRO_GOAL_CONTRACT_CASEBOOK_V1_ZH.md`。

## 5. 核心消融

为了检验结构化约束是否限制强模型，固定 backbone 后依次比较：

1. 原生 raw-history ReAct；
2. ReAct + 结构化 Observation；
3. ReAct + Observation + advisory Constraint state；
4. 上述系统 + grounded hard guards；
5. EnvSolve v1 frozen baseline。

同时跨至少两个能力层级的模型复现实验。若模型越强，hard planner 的增益消失或转负，则收缩 hard
mechanism，把贡献定位在可验证状态、执行闭环与恢复能力，而不是限制模型的动作空间。

## 6. 指标与统计

主指标：Official Pass@1。关键次指标：terminal reach、首次失败后的修复成功率、clean replay、重复失败
率和基础设施删失率。资源指标包括输入/输出 token、请求次数、候选环境、执行命令与 wall-clock。
逻辑模型调用与 provider transport attempt 分开报告。

报告 paired effect、置信区间和 failure-stratified analysis。基础设施 Unknown 不计作算法失败，但必须报告
比例。Internal verifier 仅用于在线反馈；Official evaluator 始终 terminal-only。

## 7. 当前下一步

冻结的 5-case qualification 已完成。ILAMB 与 Flask-Security 是仅有的两个双方都达到
integrity-valid Official Pass 的配对；显式状态使用的候选和 token 略少，但不足以支持成功率或效率
结论。Starsim 暴露 import-alias 完整性旁路，禁止进入效果分析；River 与 LitGPT 暴露全前缀重复重放、
上下文增长和终局删失。完整结果冻结在
`PRO_GOAL_CONTRACT_QUALIFICATION_V1_RESULTS_ZH.md`。

资格实验后的 integrity v2 已在执行前和两条 verifier 的活动解释器中拒绝观测到的 symlink alias。
资源 ledger v1.1 已记录每次 provider attempt、关闭 SDK 隐藏重试、让一次逻辑调用共享同一 deadline，
并回归验证删失标签。

同一已消费 River revision 上的原生 Codex 事后观测进入 Official evaluation，但留下 16 个 missing-
import finding。该 evaluator 输出已冻结，不能驱动新的 River candidate。其轨迹独立显示：命令超时后
状态仍可能有效；编译器兼容约束可能未声明；环境位置会改变 verifier 作用域；同时它通过变换已验证
环境而不是重放历史完成修复。

因此，在真实 provider canary 后只检验一个操作层假设：保留通过后置条件验证的状态，对 suffix repair
执行最小状态变换，并在终局使用全新环境完整重放认证。显式状态与 raw-history 对照必须共享同一机制。
冻结新的 repository-disjoint qualification 前，还需补齐同一已消费 case 的 Repo2Run 轨迹。
