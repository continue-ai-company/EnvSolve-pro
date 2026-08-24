# EnvSolve-Pro 研究计划

> **当前论文设计（2026-08-23）：** 失败统一按 Observation--Constraint--Operation 三层分类。
> EnvSolve-Pro 保留一个自由连续 Agent session，按固定节奏测量完整公开目标，并把首次可信 Pass 转成
> 可执行交接：整理当前解法并从目标初始状态重放。重放失败在同一 session 内成为 case-local 软约束。
> Package 规则、ledger、checkpoint、跨 case memory 和硬动作策略均被排除。所有方法共享的实验完整性
> 底座 E 不属于算法。第 12 节优先于下文保留的可审计研发历史。

## 1. 研究目标

EnvSolve-Pro 研究陌生仓库的自动环境部署。核心问题保持不变：部署不是自由命令试错，而是一个
**部分可观测的状态化约束求解过程**。系统仍采用三层闭环：

1. **观测层：发生了什么？** 保真记录仓库证据、执行结果、环境身份和不确定性。
2. **约束层：现在缺什么、冲突在哪里？** 同一活跃 session 根据目标状态反例维护 case-local 软约束。
3. **操作层：怎样改变环境来解除冲突？** 由强模型自由修改完整部署程序，并在目标初始状态重放。

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

强模型始终可以访问有界原始观测。软约束是带 provenance 的 advice，不是模型的唯一上下文；模型可以
推翻其解释，也可以提出 schema 未覆盖的操作。evaluator 隔离与结果通道保护等实验完整性由所有方法
共享的 E 底座保证，不属于 EnvSolve-Pro。会强制、拒绝或改写部署动作的硬兼容规则属于独立的 C_h
方法族，通过冻结的旧 EnvSolve baseline 评估。

### 2.3 Baseline-first

在提出新算法改动前，先真实运行 Repo2Run、Codex/native agent 和同 backbone raw ReAct。阅读代码只能
解释实现，不能替代对完整轨迹的观察。外部 baseline 的容器策略、反馈 loop、停止原因和失败恢复必须
进入统一轨迹分析。

### 2.4 防止开发集过拟合

诊断 case 与验证 case 分离。每个算法假设先由跨仓库失败模式和 repository-free 反例支持，再在新的
outcome-blind Dev batch 上验证。已经看过结果的 case 只能用于诊断，不能再次承担确认性证据。
Canary 和 Official Test 在算法、baseline 与分析规则冻结前保持 untouched。

### 2.5 主执行平台

新的 Dev census、构建容器、clean replay 和 Official evaluation 统一以 DGX Spark 为主执行端。
Mac 只保留本地 Agent session、实验控制、代码编辑和轻量回归测试，不再作为部署执行端。所有被比较
arm 必须使用相同的 Spark 平台、镜像 digest、网络策略和加速器暴露方式。GPU 不是主机带来的隐含优势，
而是显式实验设置：冻结的 CPU-compatible census 继续关闭 GPU，CUDA 支持在后续作为单独冻结的平台
treatment 评估。SSH transport 属于所有方法共享的实验基础设施，不属于 EnvSolve-Pro 算法。

Spark 是 Linux ARM64，也是 EnvBench 发布的容器平台之一，因此开发结果对声明的平台有效；但涉及
原生包的失败必须标记为架构敏感。正式提交榜单前，冻结后的全部方法和对照 arm 必须在真实提交平台
重跑；只有 ARM64 与 AMD64 结论一致时，才能提出跨架构结论，不能从任一平台直接外推。

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

2026-08-24 的 attempt 级重建恢复了全部 48 个 method--case row，其中 36 个完成 Official。原生
Codex 在完成评测的 episode 上为 6/15，causal-v3 为 3/10，复现 Repo2Run 为 1/11。由于三者使用的
模型、目标可见性和基础设施/adapter 路径不同，这些分母也不同，不能被当成性能排名。该矩阵用于轨迹
taxonomy，并证明目标可见性是反复出现的因果差异；同 backbone 效果必须由后续 matched experiment
估计。证据矩阵与重试裁决分别为
`experiments/validations/pro_cross_method_census_v1_evidence_matrix.json` 和
`experiments/validations/pro_cross_method_census_v1_attempt_adjudication.json`。

机械终止阶段现已与因果标签分离。临时单审阅标注已为 38 条非成功记录中的 17 条建立证据链接：观测
7 条、约束 3 条、操作 2 条、基础设施未知 3 条、协议截断 2 条。同一个 Conan Official 残余在 Codex
和 Repo2Run 中属于观测失败，在 causal-v3 中却属于操作失败：只有 causal-v3 表示了精确的条件导入
缺失，但其动作没有满足对应的版本化 API 要求。target-bootstrap 记录也进一步分成未观测目标状态和
包索引事故。标注底稿与自动汇总分别为
`experiments/validations/pro_cross_method_census_v1_causal_annotations.json` 和
`experiments/validations/pro_cross_method_census_v1_causal_annotation_summary.json`。剩余记录必须继续
审阅，并在任何分布性结论前完成独立第二标注。

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

### 4.11 后置条件控制的状态复用

一个仓库不相交的五 case 资格实验，在相同模型、目标、prompt family、终局 evaluator 边界和限制下，
比较了 persistent explicit state、fresh explicit state 与 persistent raw history。15 个 episode 全部通过
完整性检查并具有科学可用性。三个 condition 都通过相同四个仓库、都失败于 `openqasm/openqasm`，
因此各自 Official Pass 都是 `4/5`。预注册 gate 保留状态复用机制，因为复用真实发生且可审计，但该
实验没有提供 Official Pass 增益证据。

该机制不是只存在于代码中：persistent explicit state 记录了 6 次复用 construction verification，其中
2 条复用谱系最终产生 clean-replay Pass。与 persistent raw history 相比，显式状态使用 19 而非 27 个
候选、339,479 而非 483,988 tokens、4,361 而非 9,064 秒 generation time。与 fresh explicit 相比，
它使用 19 而非 21 个候选且 token 更少，但 easy case 的强制 clean replay 使总 wall-clock 更长。由于
只有五个仓库和一个随机 seed，这些只是诊断性资源差异，不构成效率结论。

`openqasm` 隔离出下一步算法矛盾：三个 condition 最终都保留 7 个官方 issue 并失败。persistent
explicit 用约一半于 persistent raw history 的 generation time 到达这一边界，之后却重复不可行的
ANTLR 生成路径，并多次尝试违反完整性的 import artifact 物化。所以下一版应改进操作层，而不是增加
更多状态类型。操作相关性合同 v1 已作为独立的 post-freeze method 实现：每个候选声明目标 executable
finding，引用模型确实看到的前提证据，预测 finding delta，并声明开放式 operation-family identity。
harness 会拒绝过期引用、已经确定失败的相同完整脚本，以及没有新增引用证据的同 family 重试；下一次
完整目标快照会生成 progress certificate。v1 不宣称能够证明任意 Shell 语义或外部 provider 可用性。

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

Pass@1 需要区分“方法未提交成功答案”和“外部删失”。方法触发冻结的候选、context 或 generation
上限时，虽然未解决任务状态仍是 Unknown，但它没有在协议内产生通过答案，因此属于 primary
non-pass。Provider、网络、evaluator 和测量失败属于外部删失，只有在冻结的 identical-episode
amendment 下才能重试。

依赖缓存是方法无关的实验基础设施，不是算法记忆。所有被比较方法必须获得同一初始缓存快照和 client
image，并在 batch 前审计其身份。缓存模式与网络字节只作为资源设置和结果报告。冻结重试不能在看到
源结果后临时采用新缓存。

## 7. 当前下一步

操作相关性合同 v1 继续保持冻结。在 DeepSeek-direct 复现中，第一个有效配对在 Django 上是
Pass/Pass，第二个有效配对在 Trax 上是 Nonpass/Nonpass。Treatment 在 Trax 上使用更少候选，但仍重复
同一类宽泛且不可行的重安装，因此这不能证明 Pass@1 增益。UER-py 配对及后续位置都受到外部删失：
VPN 退化先后引发包网络、provider transport 和仓库获取失败。

位置 1-4 保持不可变；位置 5-10 已生成新 run ID、保持原顺序的 network retry schedule，算法、模型、
provider、prompt、seed、config、protocol、平台和预算全部不变。本轮新建的依赖缓存明确不用于该重试，
因为加入缓存会改变冻结实验设置。只有 provider、Hugging Face、PyPI、Ubuntu 和 VPN 剩余额度
preflight 全部通过后才恢复执行。

Closure 后首先分析 Official Pass@1。若操作合同仍未提升跨仓库成功率，就将其封存为可审计的结构化
baseline。当前已消费轨迹只提出一个更简单的后续假设：操作需要证明 package/platform 可行性与有界
执行进展，而不是只引用宽泛 goal finding。在冻结比较关闭前不得用 qualification outcome 重设计，
也不得针对 `openqasm` 或任何单独 case 调参。

### 7.1 依赖缓存工程资格验证

方法无关缓存已经在 EnvBench Python 的精确基础镜像上通过严格功能 canary。每个条件都使用 fresh
container 安装一个 PyPI 包和一个 Ubuntu 包：直连网络耗时 151.63 秒，空缓存冷启动耗时 191.98 秒，
两个缓存服务被强制设为离线后的热复放耗时 12.28 秒。离线热复放相对直连快 12.35 倍；冷缓存则增加
26.61% 开销。

该结果只证明缓存可以作为共享实验基础设施，不是 EnvSolve-Pro 的算法效果。完整记录绑定了镜像身份、
配置哈希、缓存内容、进程级离线参数和 apt 输入/输出证据。整机网卡计数包含无关流量，只能作为描述性
观测。估计批量实验的流量下降前仍需运行一个有代表性的 EnvBench 依赖轨迹；已经冻结的
DeepSeek-direct 重试继续禁用缓存。

代表性轨迹已经在已消费开发 case UER-py 上完成。它声明的 6 个顶层 requirement 最终解析为 35 个
wheel 和 2.896 GB 缓存快照。直连与空缓存生命周期分别耗时 2584.94 和 2605.31 秒；两者都出现了
验证成功标记，但在 `docker run --rm` 返回前保守地超过冻结 wrapper 超时。第三个 fresh client 在
DevPI 进程级离线时复放相同闭包，只用 93.74 秒并正常退出。相对直连，这是描述性的 27.58 倍加速和
96.37% wall-clock 降低；复放后缓存快照保持不变。

该结果改变了批量实验设计。全局 mutable cache 会产生方法顺序效应；frozen-offline cache 则会拒绝
新包，从而关闭强模型的操作空间。新的、尚未冻结的对比实验应给每个 episode 提供同一份、方法无关且
经过审计的 seed snapshot 的独立可写副本，同时允许 online miss。Seed 只能由 benchmark-visible
manifest 构建，不能使用结果。缓存变更只在单个 episode 内持久化，用于消除候选间重复下载，不在方法
之间传递状态。Seed 构建成本、hit/miss、上游字节、缓存大小、wall-clock 和服务内存单独报告；现有
DeepSeek-direct 重试继续禁用缓存。

## 8. 外部轨迹裁决与下一版算法

Lark 与 micropy-cli 的事后研究已经观察了 Repo2Run 和 goal-aware Codex 在已消费开发 case 上的
行为。它只提供机制证据，不是性能比较。Repo2Run 在 Lark 原生测试通过后停止，但公开官方目标仍有
13 个问题；在 micropy-cli 上，它通过修改受版本控制的依赖声明让原生测试通过，无法输出合法的纯
环境重放程序。goal-aware Codex 则通过交互式包诊断找到了合法的 Lark 解法，但在 micropy-cli 上，
即使提前看到开放候选契约，仍提交了合成 import stub；可执行验证正确拒绝了该候选。

结合 execution-feedback-v3 的负结果，当前核心假设发生变化。下一版不会继续增加语义约束分类，也
不会收窄 Bash 动作空间，而是把强交互 Agent 与三层状态结合：

- **观测层：** 保留完整公开目标 finding、命令结果、仓库 effect、候选策略裁决和 clean replay
  结果；
- **约束层：** 只维护带来源的未解决目标义务、合法性 violation 和已验证候选事实；
- **操作层：** 让强 Agent 使用开放终端进行检查与操作，再提交累计部署程序。候选被拒或 clean
  replay 失败时，把精确结果作为下一次 fresh repair round 的反馈，而不是终止整例。

这个最小假设冻结命名为 `stateful-agent-v1`。受控比较固定同一个强模型和同一个公开目标，依次比较：
单次原生 goal-aware session、多 session 加原始历史反馈，以及多 session 加结构化当前状态和相关
原始证据。主指标仍是 Official Pass@1；首次失败后的恢复率直接检验新机制。Token、请求、命令、
环境数量和 wall-clock 继续作为资源结果报告，不覆盖成功结果。

在打开未见开发 case 前，`stateful-agent-v1` 必须通过三个已消费机制检查：保留合法 Lark 程序；
在 micropy-cli 上把精确策略拒绝转成新观测；所有成功都必须产生身份可审计的 clean replay。已消费
case 只能验证 plumbing 与机制，任何规则都不得编码其包名或具体解法。

### 8.1 Stateful-Agent V1 裁决

四个已消费位置都在第一个候选上通过官方指标，但这不能证明机制合格。两份 Lark 程序是合法的纯环境
部署；两份 micropy-cli 程序则通过 `PYTHONPATH`，用旧版同名 distribution 中的 `micropy.cli`
覆盖当前 checkout 的 `micropy` namespace。它们是可重放的混合来源环境，不是来源一致的仓库复现。
raw 与 structured 都选择同一捷径，说明漏洞在共享验证契约，而不是某一种状态表示。

由于每个 episode 都在第一轮结束，没有拒绝或目标失败进入后续 session，结构化修复状态从未被真正
使用。V1 作为强 Agent 诊断 baseline 冻结，不做效果或资源结论。V2 只增加共享的操作前目标观测、
通用项目 namespace 来源检查，以及可信 verifier shell 不变量恢复。它必须先在已消费数据上展示真实
的“失败后修复”转移，才允许打开新的 Dev 仓库。

### 8.2 Stateful-Agent V2.1 裁决

V2.1 修正了初始观测的角色边界，并完成 micropy-cli 已消费机制实验。第一次模型操作之前，公开可执行
目标产生 70 条 active finding；约束层完整保留并压缩为 24 个 obligation group。候选 1 直接生成
Python stub，被操作层精确拒绝到具体违规行。候选 2 在新的 session 中拿到完整程序和拒绝原因，改变
方案后通过 fresh 内部验证，并以 0 个计分 issue 获得 Official Pass。这是第一次真实观测到的状态化
“拒绝到修复”转移，但仍然只是已消费机制证据。

事后审计发现一个剩余的定义缺口：候选 2 通过 setuptools 元数据，把已有的 `micropy.app` 源码赋予
仓库中不存在的 `micropy.cli` 身份。它符合冻结的 V2.1 源码内容规则，也符合 EnvBench 官方
`reportMissingImports` 目标，但不保持模块身份。V2.2 只增加这一个不变量。ARM64 Docker canary
已经证明：正常同身份安装保持合法，未声明的源码重命名会被拒绝。下一步是在独立版本 runner 中接入
V2.2，在打开仓库不相交 Dev case 前冻结，并分别报告 Official Pass 与 integrity-qualified Pass。

### 8.3 Stateful-Agent V2.2 Dev-5 结论

冻结的 repository-disjoint Dev-5 诊断已经完成。强单 session goal-aware baseline 与
raw-feedback loop 都得到 `5/5` Official Pass，structured V2.2 得到 `4/5`。相对 raw feedback，
V2.2 少用 16.2% 命令和 19.4% input token，但总 wall time 基本相同，并新增了一次错误 hard
reject。因此 V2.2 没有效果证据，只作为冻结的结构化 baseline 保留。

错误分析改变了当前机制。操作前的完整目标探测在强 Agent 使用仓库证据之前就产生额外成本和注意力
偏置。derived root group 没有真正减少状态增长，因为完整 finding 仍进入模型投影，而且每个 surface
finding 都产生两条状态事件。最重要的是，project-provenance 启发式在 `moat-mqtt` 上错误拒绝了合法
Python namespace composition。除非属于共享实验合法性契约，否则从部署语义推断出的约束不能覆盖官方
目标。

完整数字和逐例证据冻结在 `PRO_STATEFUL_AGENT_V2_2_RESULTS_ZH.md`。这些 case 已消费，不能用于
资格验证下一版。

### 8.4 Stateful-Agent V2.3 假设

V2.3 不再加规则，而是做减法：

1. 第一轮操作只获得仓库访问，不再强制先运行完整目标；
2. 候选失败后，完整 goal finding 进入审计档案，只有 root obligation 进入 solver state 和有界模型
   视图；
3. hard authority 只属于公开可执行目标与共享 candidate/effect 规则；推断的 provenance 或 runtime
   语义只能作为 advice；
4. 操作层继续使用不受限的强 Agent。

这恢复了部分可观测闭环的本意：模型先在不确定状态下行动，可执行失败揭示新状态，后续独立 session
再依据紧凑约束 frontier 修复。Raw-feedback V2.3 使用相同的 failure-triggered schedule 和 verifier
边界，但不做 root compaction，从而构成同模型消融。

实现与所有历史 freeze 文件隔离。Mac 回归结果为
`655 passed, 3 skipped, 2 项因 Python 3.9 deselect`；Spark ARM/Linux 回归为
`670 passed, 3 skipped`，另有两个无关宿主测试因为登录 shell 没有 `python` alias 而失败。下一步在
全新 repository-disjoint batch 上比较强单 session、raw V2.3 与 structured V2.3。主结果是 Official
Pass@1；真正首个候选失败后的恢复率是机制指标；资源数据保持为次指标。

### 8.5 Stateful-Agent V2.3 Pilot 结论与 V2.4

repository-disjoint Pilot-3 中三个条件都得到 `2/3` Official Pass。Structured V2.3 消耗了最多的
时间、命令和模型 token，因此既没有效果证据，也没有效率证据。由于运行开始时 worktree 不干净，
这些轨迹不具备科学统计资格，只能用于机制诊断。完整描述性结果记录在
`PRO_STATEFUL_AGENT_V2_3_PILOT3_RESULTS_ZH.md`。

StopStalk 把下一处矛盾定位到操作层接口：可执行目标可能已经满足，但 repository effect 或 caller
可见的 shell 后置条件仍不合法。V2.3 把两个维度压成一个候选失败，丢失精确修复信息；同时，过宽的
文本验证器会因为合法配置程序读取了真实源码，就错误拒绝它。

V2.4 只做最小通用修正：

1. 独立保留目标状态与操作契约状态；
2. 目标 Pass 后仍向下一轮投影精确操作 violation；
3. 结构化分析 embedded-Python 真正的写入目标；
4. 强制恢复 caller 工作目录。

算法中不加入任何仓库名、包名或具体解法。V2.4 必须先提交为干净版本，再通过 salted sampling
选择新 case。V2.3 的 case 只能作为回归测试。只有在新 case 上提高 Official Pass，或稳定修复这种
因子化失败且不损害简单首轮成功，V2.4 才能晋升。

### 8.6 Stateful-Agent V2.4 Pilot 结论

干净的四仓库 Pilot-4 对比已经完成。12 个 artifact 全部完整有效并具备科学统计资格。强单 session
baseline、raw repair V2.4 与 structured V2.4 都得到 `4/4` Official Pass。Structured V2.4
相对 raw repair 多使用 66.7% input token 和 3.4% 端到端时间，但没有成功率增益。

更重要的是，所有 raw 与 structured episode 都在一个候选、一个模型轮次内通过。跨候选状态转移
从未因果地到达操作层。因此 V2.4 没有检验所提出的 failure-conditioned repair 机制；资源差异
也不能归因于未被触发的状态机制。V2.4 冻结为可审计 structured baseline，不予晋升。精确结果与
完整披露的干净重跑 amendment 记录在
`PRO_STATEFUL_AGENT_V2_4_PILOT4_RESULTS_ZH.md`。

最难的 `flavio` 轨迹把下一处问题定位到活跃 operation session 内部：包能否安装、旧版本语义是否
兼容、平台是否可行、静态分析是否可见、运行时 ABI 是否一致，是不同事实。Structured condition
虽然观测到其中多个事实，却没有维护单调演化的 compatibility frontier；它反复进入相互冲突的状态，
最终利用了静态 evaluator 与运行时一致性之间的缺口。

下一版不增加仓库特定包规则，也不扩张语义 taxonomy。资格假设是：

1. 把命令结果规范化为紧凑的 session 内 compatibility frontier；
2. 只接纳有因果根据的事实，并保留对应观测证据；
3. 对高影响环境事务进行可行性与后置条件检查，同时保持终端动作空间开放；
4. 只抑制相关前提已经被证伪的操作；
5. 分别报告 Official Pass 与 runtime-coherence certification。

Pilot-4 四个仓库已经消费。新的资格 case 必须从 repository-disjoint identity 中 outcome-blind
选择。打开新 case 前，机制要先在已消费或 synthetic 轨迹上证明：一次被证伪的操作能够改变下一次
操作，同时不会阻断简单、合法的首轮解。

## 9. 历史 Minimal B 冻结

前文的 ActiveState 与 verified-frontier 提案不再是当前算法，只作为历史假设和后续可能的
treatment 保留。冻结的下一版只包含四个运行时要素：

1. 一个连续强 Agent session；
2. 一个带开放终端的持久构建环境；
3. 一个可调用的 `submit_and_replay` 工具，它创建独立干净环境，并把候选校验、执行、公开目标与
   effect-audit 证据返回同一个 session；
4. 只接受精确通过 clean replay 的程序。

紧接着的受控配对只改变第 3 项：control 在 session 结束后得到一次不会返回结果的终局重放；
Minimal B 可以在线使用重放反馈并在同一个 session 中继续。Official evaluator 输出仍然只在终局
可见。选择新的效果 batch 前，必须先完成源码实现、测试和机器可读 implementation freeze。

Minimal B v1.0.2 现已通过实现机制门。在一次预注册的已消费 case smoke 中，同一个连续 session 在
安装超时后保留了有用的部分状态，生成正常依赖安装程序，在独立干净环境中完成认证，随后通过终局
Official evaluator。唯一一次 replay 直接通过，因此它只证明在线机制与合法性边界可运行，尚未证明
replay 失败后的修复能力或效果增益。下一步直接冻结 repository-disjoint A/B 配对，不能根据这个已
消费结果修改方法。

## 10. 冻结配对 Dev-5 裁决

Repository-disjoint 开发配对已经完成。Minimal B 的 Official Pass@1 为 `5/5`，其他条件匹配的
强 Agent control 为 `4/5`。四对双方通过，`datactive/bigbang` 仅 Minimal B 通过。只有一个
discordant pair，精确双侧 McNemar 检验为 `p = 1.0`。这是正向信号，不是统计可靠的效果，更不是
held-out 结论。

5 个 Minimal B episode 都只调用了一次 clean replay，而且第一次直接通过。因此本批次没有真正
触发“replay 失败后继续修复”。`bigbang` 差异可能来自面向认证的提前构建，也可能来自运行方差，
目前不能归因于迭代修复。Minimal B 冻结为一个新 baseline，但不能宣布它已经是收敛的 EnvSolve-Pro
算法。

资源结果也不支持单方面包装。全部 5 次尝试中，Minimal B 多使用 `4.8%` model tokens，少执行
`12.1%` 容器命令；在 4 对 coordinator timing 可比的 pair 中慢 `36.1%`。峰值内存、磁盘增长和
网络字节没有被持久化，必须报告为缺失。`bigbang` 时间 pair 被删失，因为 control 在 Agent 前网络
故障后按照 amendment 使用了 exact-revision 本地源码缓存。

### 10.1 测量发现

下一批前必须修复两个共享 harness 问题：

1. 命令与 Git timeout 只终止父进程，transport 或 installer 子进程可能继续存活并与后续命令重叠；
2. 源码获取与资源 telemetry 尚不足以支持干净的效率比较。

基础设施资格验证将终止完整 process group，对所有条件统一使用 immutable exact-revision cache，
内存、磁盘和网络只在三臂能够对称测量时报告。这些改动对所有方法完全相同，只属于测量修复，不属于
算法贡献，也不阻塞 Official Pass 实验。

事后审计还发现，两个方法在 `castagnait/plugin.video.netflix` 上都把 `setup` 解析到无关的 Pylint
模块，而该模块并不提供代码实际导入的 `get_addon_data`。Official Pass@1 继续作为榜单主指标；同时
必须加入方法无关的独立诊断，区分“模块可解析”和“所需接口兼容”，避免论文的复现主张超过公开目标
实际验证的范围。

### 10.2 下一因果门

下一批 outcome-blind 开发实验使用三个条件，保持模型、终端、构建环境、公开目标和 evaluator 边界
相同：

1. 只做终局 post-hoc clean replay；
2. 只能调用一次 clean certification，失败后不能再取得第二张证书；
3. 可以反复 clean replay，并在失败后继续修复。

条件 1 对 2 测量 certification-aware construction；条件 2 对 3 才隔离 replay-conditioned repair
的算法价值。先报告机制是否激活，再报告总成功率：first replay 失败数、失败后产生第二份方案的数量、
以及同 session 恢复数量。在这一分解验证循环或暴露重复失败模式之前，不增加结构化状态、checkpoint、
假设搜索或最小化。

### 10.3 认证—修复消融 v1 冻结

三臂接口已经实现并冻结。B 继承 Minimal B 的目标 verifier、完整性边界、证书绑定和干净环境
provider，但最多执行一次 replay；第二次提交会被记录并在创建环境前拒绝。共享 qualified
infrastructure 冻结时全量回归通过 `699` 个测试；加入 B 后完整代码树通过 `702` 个测试、`7` 个
skip 和 `75` 个 subtest。Spark Linux ARM 资格测试通过 `25` 个 focused test 和 `7` 个真实 Docker
test。

执行前用冻结 salt 对 untouched pool 的仓库 identity 做哈希，选出 8 个仓库并生成 24 条轮换
episode。机制判据已经固定：只有 C 臂第一次 replay 为 Fail/Unknown、随后不同程序 replay 通过且
最终 Official Pass，才能支持 feedback-conditioned repair。双语协议冻结在
`PRO_CERTIFICATION_REPAIR_ABLATION_V1_PROTOCOL_ZH.md`。

有效 episode 裁决、可复算分析与双语结果分别冻结在
`experiments/validations/pro_minimal_b_v1_paired_dev5_effective_episodes.json`、
`experiments/validations/pro_minimal_b_v1_paired_dev5_results.json` 和
`research/PRO_MINIMAL_B_V1_PAIRED_DEV5_RESULTS_ZH.md`。

### 10.4 Boundary-v2 有效性裁决

第一个完整三臂 block 不能估计算法效果。A 组用 tracked 模板生成合法运行时配置并达到构建环境公开
目标，却被共享完整性规则误拒；B 组创建无关空导入模块，被正确拒绝；C 组利用多次 replay 反馈，最终
通过重定义 Pyright 调用时的 shell 行为让公开指标通过。批次随即停止，三条轨迹都只作为已消费诊断。

Boundary v2 只做对三组共享的测量修复：

1. 可信 goal 执行不继承候选定义的 shell function 和启动 hook；
2. 公开 goal 显式调用所选 Python 命令，而不调用同名 shell function；
3. 只有与指定 revision 中同目录、同 stem 的 tracked 模板字节完全一致，ignored 运行时配置才被接纳；
4. 使用版本化 runner 与入口，防止后续 schedule 静默落回旧边界。

旧 C 组的精确程序现在能够执行完成，但会在修正边界下被真实 Pyright 判定失败；旧 A 组的精确 workspace
通过 provenance audit。Focused test 与真实 Docker 红队已在 macOS 和 Spark Linux ARM 通过，两个
平台的源码快照逐文件一致。这只是基础设施资格，不是效果结果。下一步冻结 v2 源码与分析契约，通过
原 outcome-blind 规则替换已消费 identity，然后在不再修改方法的前提下运行尚未打开的三臂 case。

### 10.5 Boundary-v2 Dev-8 预注册

下一批效果实验已在打开任何新仓库前冻结。实验沿用 6 个已证明“未执行、未检查”的 identity，再用原始
盐化仓库排序中顺延的两个合格 identity 填补已消费位置。只读取 manifest 是否存在的审计表明，替代
候选都没有既往轨迹；选择过程没有读取仓库内容、失败类型或分数。

冻结 schedule 包含 8 个仓库 block、24 条顺序 episode。三臂使用明确的 boundary-v2 runner、同一
强模型、同一 Mac 主机和相同宽松运行上限。Spark 继续承担可移植性和基础设施验证；只把部分因果实验
放到 Spark 会引入 host-by-treatment 混杂。在 24 条结果全部记录完，或触发预注册的结构有效性早停
之前，不允许修改算法或边界。

### 10.6 Boundary-v3 与 Untouched Dev-5

第三个仓库 block 触发了结构有效性早停。三臂都找到项目原生的包同步操作，但 boundary v2 把锁文件
派生的 Python 输出判成违规；可重试组还在临时创建并删除构建配置后获得了假证书。因此整个
`trader` block 排除在 A/B/C 效果估计之外。

Boundary v3 保持三个推理接口不变，只修共享测量：在干净环境中资格验证最终提交程序；即使最终文件
被删除，也记录受保护配置的违规写入；只有仓库声明、revision 锁内容和包管理器校验三者同时成立，
才接纳生成依赖。标准 `virtualenv` hook 还必须匹配候选执行前记录的模板哈希和版本。构建容器残留
继续保留为轨迹证据，不再冒充提交 artifact。

A 的精确程序现已在 Spark Linux ARM 上同时通过公开目标和全部 provenance 检查；隐藏临时操作的
C 程序在执行前被拒。B 的字节相同程序在紧邻的前一版 v3 中完整通过，最终哈希下的重复执行则都被
外部包传输故障删失。完整回归为 735 passed、8 skipped，另有 76 个 subtest passed。这些结果只
证明测量边界合格，不证明算法有效。

Untouched Dev-5 的第一个仓库在 B 臂开始前再次触发 validity stop。C 和 A 都通过 Official evaluator，
但 boundary v3 会因为等价原生构建位于 `/tmp` 还是仓库内部而给出不同判定；原 v3 审计还拒绝了 A 的
标准 build 命令产生的 106 个提交源码精确副本。该 case 与两个提交程序都只作为已消费测量诊断，不报告
方法效果。

### 10.7 Boundary-v5 冻结与恢复规则

Boundary v4 被预注册为最小原生产物修正。它正确接纳了 A 的 tracked-source 原生扩展，但 106 个精确
build-tree 源码副本仍被拒，因此校准失败；该版本作为失败测量版本保留。

Boundary v5 用一个统一的 committed-source provenance 原则替代位置和后缀例外。Python 构建副本只有
在字节与提交源码完全一致、且输出路径保留源码路径后缀时才被接纳；原生扩展只有在提交原生源码声明同名
初始化符号、artifact 具有合法原生格式和初始化符号时才被接纳。被修改、改名、直接生成或没有源码来源
的 import artifact 仍被拒。候选操作语言、Agent session、公开目标和 Official evaluator 均未改变。

预注册的已消费校准在不调用模型和 Official evaluator 的情况下，重放 A/C 两份精确程序。A 以 106 个
提交源码副本和 1 个原生 artifact 通过；C 以外部 import root 中的对应原生 artifact 通过。两者 missing
imports 和剩余 violation 都为 0。Mac 全量回归通过 759 个测试；Spark Linux ARM 在源码 hash 完全一致
时通过全部 24 个 v4/v5 focused test。该校准只证明测量一致性。

实现冻结在
`experiments/protocols/envsolve_pro_certification_repair_boundary_v5_implementation_freeze.json`。
效果实验只能在 boundary-v3 schedule 的 case positions 2-5 共 4 个尚未打开仓库上恢复，对应 episode
positions 4-15 的 12 条运行，并使用明确版本化的 boundary-v5 A/B/C runner。打开任何仓库前，必须
冻结 host、模型、prompt、公开目标、Official evaluator 和分析规则。

## 11. 当前 V2 论文方案

第 4-10 节保留研发历史，不代表当前论文算法。论文严格区分三个科学对象：

| 对象 | 取值 | 作用 |
|---|---|---|
| 失败分类 | 观测层、约束层、操作层 | 解释最早产生决定性影响的失败原因。 |
| 部署机制 | F、定时 O、增量 C、R | 规定搜索、测量、状态与重放。 |
| 公共底座 | E | 保证实验公平可审计，永远不算算法 treatment。 |

EnvSolve-Pro 在一个持续存在的构建环境中保留同一个强 Agent session。Agent 具有自由 shell 操作能力 F；
harness 按冻结节奏执行与环境身份绑定的完整公开目标观测 O；将完整 finding 集合转成已解决和新引入的
义务，同时维护非支配证据前沿 C；完整部署程序只通过独立干净环境重放 R 获得认证。证据可以单调积累，
环境状态和 Agent 的操作空间都不要求单调。E 隔离 Official evaluator，并审计环境身份和仓库完整性。

### 11.1 失败研究

EnvBench FreeAgent、Repo2Run、原生 Codex、旧 EnvSolve 和 EnvSolve-Pro 的全部科研有效已消费轨迹
进入回顾性 taxonomy discovery。每个失败 episode 按最早决定性原因标一个带 artifact 证据的观测层、
约束层或操作层主标签；基础设施事故单独删失。按系统与主类别分层确定性抽取 20% 样本独立复标，报告
原始一致性、Cohen's kappa 和 adjudication。该不均衡语料只支撑 taxonomy 与跨系统分布，不支撑
成功率 claim 或因果归因。

### 11.2 可选 Ledger Pilot 的结论

冻结的已消费 case pilot 比较 B-FSR（F+R）与 D-LEDGER。D 额外向 Agent 提供一个可选的环境身份绑定
compatibility 工具和增量 ledger。两个仓库、两个 arm、每个 arm 两次重复；按预注册规则替换基础设施删失
位置后，共得到八个有效 episode。所有 episode 均通过 provider、image、goal、仓库完整性和审计检查。

D 形成并通过 Official 的候选为 3/4，B 为 2/4；D 有一个独占成功，且没有独占失败。关键 Paz 轨迹先
观测到 16 个义务，随后降到 0，修复了一次干净重放依赖冲突，并在第 84 次请求通过 Official；其配对 B
用完 120 次请求仍未进入重放。但是另一个成功的 D episode 一次都没有调用 ledger，因此 treatment 没有
满足预注册的机制激活标准。在双方均成功的可比配对上，D/B 的中位数比值分别为：请求数 1.30、交互步骤
1.28、token 1.46、获得证书时间 1.11。

机器判定为 `negative-mechanism-not-qualified`。这否定的是“可选工具”实现，不是否定观测假设。完整且
绑定环境身份的观测能够揭露虚假进展，也可能促使 Agent 从修当前环境转向修可重放程序；但如果由 Agent
自行决定何时观测，treatment 剂量就不稳定，而且往往代价较高。

### 11.3 确定性观测 V2

下一个候选算法只改变观测调度：

1. 第一次模型请求前执行一次完整、绑定环境身份的观测；
2. 每完成 16 次 shell 操作，再自动执行一次；
3. 干净重放前，若环境在上次观测后发生过变化，则补一次观测；
4. 把既有增量 ledger 反馈注入同一个连续 session；
5. 永不阻断 shell 操作或重放，不替 Agent 选择包，不恢复容器，不使用跨 case 记忆。

节奏来自已消费 14 条轨迹的自然全局检查间隔：898 次 shell 操作对应 50 次全局检查，平均 17.96，预先
一次性取整为 16，而不是按最新 pilot 结果调参。移除可选 `check_compatibility` 工具，使每个 treatment
episode 接受相同机制剂量。ledger 表示、Agent、干净重放、模型/provider、安全上限和公共 E 均保持不变。

预注册一个 16-episode 已消费 qualification：四个此前已消费仓库、两个 arm、两次重复，并平衡运行顺序。
当前两个压力 case 可继续作为设计 case；另外两个 identity 在实现前从不同的历史观测失败层中冻结。机制
合格要求：每个 treatment episode 都遵守调度，至少 75% 的观测完整，不增加任何操作约束，也不创建
checkpoint。晋级还要求 Official Pass 数不下降、最多一个 treatment 独占失败，并且至少出现一个
treatment 独占成功或一个预注册的成功条件效率信号。token、时间、网络、磁盘和内存只作为结果测量，
不作为优化停止阈值。

### 11.4 确认性实验与主张

V2 通过已消费 qualification 前，不再打开冻结 Dev identity。通过后，在 Canary 前冻结算法、prompt、
tool schema、taxonomy、model/provider binding 和分析代码。主指标是 Official Pass@1；机制指标包括观测
调度符合率、状态增量、候选就绪到首次重放时延、首次重放修复和配对失败层迁移。资源既报告无条件结果，
也报告成功条件下结果；基础设施删失始终单独保留。

最终系统比较包括 Repo2Run、EnvBench FreeAgent、旧硬约束 EnvSolve，以及能保持原生语义时的同 backbone
自由搜索 control；原生 Codex 是独立 frontier reference。第一篇只主张固定三层算法和受控证据。
harness 自动搜索属于 Auto-EnvSolve，学习型部署策略属于 EnvSolve-RL。

## 12. 验证器触发的目标状态重放候选

确定性观测资格实验在 ceiling case 上打平，因此没有晋级。随后六 case bad-profile 研究发现了更基础的
实现问题：旧 replay 环境继承构建 package cache，导致两份重放通过的程序在冷 Official 中失败。因此
当前主要矛盾是对交付程序的观测不真实，而不是约束库规则不足。

### 12.1 最小算法

当前候选只保留：

1. 一个连续的自由搜索 Agent session；
2. 按固定节奏在构建状态中可信测量完整公开目标；
3. 首次完整 Pass 后立即触发程序化的可执行状态转换；
4. 不复用构建缓存，从目标初始状态执行完整程序；
5. 把第一个可执行反例作为 advisory evidence 返回同一 session；
6. 重复执行，直到完整程序通过或宽松安全上限耗尽。

观测层提供绑定环境身份的执行证据；约束层保存当前程序与目标状态之间的 case-local 矛盾；操作层仍由
Agent 自由决定，controller 只负责定时测量和执行 Pass 到 replay 的转换。方法不包含 package 规则、
ledger、checkpoint、跨 case memory 或新增硬动作策略。

### 12.2 已消费机制检查

在 Spark 上使用 DeepInfra 的 DeepSeek V4 Flash，预注册的 basxconnect、Graphium 和 cvxportfolio 检查
已经完成。三个 case 的最终重放都与 Official 一致，且全部 Official 通过。basxconnect 和 Graphium 都
经历了失败重放、同 session 修改程序、后续重放通过和 Official 通过。Graphium 的五次重放依次暴露无效
torchvision 版本、缺失 Git ownership、遗漏测试依赖、一次网络失败，最后通过，直接取代旧版构建缓存
导致的假通过。

三条轨迹共使用 139 次模型请求、137 次 shell 操作和 3,133,930 tokens。Graphium 单例使用 82 次请求、
约一小时生成时间和 1.2 GiB 构建缓存。因此机制在这些经过选择的 case 上能够工作且符合目标状态，但尚未
证明成功率或效率增益。

### 12.3 Outcome-Independent 资格实验

四对 case 在下载源码和执行模型前，从已有随机 Dev16 顺序的第 9--12 位固定。同模型自由搜索 Official
通过 2/4，目标状态重放通过 3/4；配对表为 2 对都通过、1 对只有 B 通过、0 对只有 A 通过、1 对都失败，
精确 McNemar 为 `p=1.0`。原 cellrank B 受到一次已披露的研究者中断。主分析使用在替代执行前写明的
replacement；排除整个 cellrank pair 的敏感性结果为 2/3 对 3/3。

因果证据比成功数差异更窄。probatus 只有 B 通过，但首次 replay 就通过，随机搜索路径仍是合理解释。
`importlib_metadata` 的两次失败重放依次揭露完整程序缺陷，第三份修改后的程序通过 replay 和 Official。
cellrank B 在形成候选前耗尽 120 次请求，因此 replay 从未激活；B 的总时间和 Token 也更高。

预注册晋级条件只在开发决策意义上满足：保持最小机制不变，扩大到下一组固定 Dev case。当前证据不能支持
效果、效率、held-out 或 SOTA 主张。

### 12.4 开发扩展与下一步证据

Dev16 第 13--16 位的同一 A/B 比较已经完成，结果为 4/4 对 4/4 ceiling tie。最终 replay 与 Official
全部一致；三条 B 程序首次 replay 通过，`pygeo` 修复一次网络获取 timeout 后通过。B 的资源总量更低，
但请求和生成时间的配对中位数没有改善，总量由 `pygeo` 主导。与 qualification 合并后，A 为 6/8、B
为 7/8，只有一对 discordance，精确 McNemar 为 `p=1.0`。

这个结果关闭随机 Dev 扩展，不批准算法补丁。保持最小方法不变，从既有 census 的强 baseline Official
failure 中构造下一组，并在查看 treatment 结果前冻结抽样规则和 baseline 证据。不添加 `pygeo` 网络规则、
package 规则、checkpoint 或其他正交 treatment。只有 bad-case 效果实验确认 matched control 有提升空间时
replay 能提高成功率，才进入外部 baseline 与强弱 backbone 比较。

### 12.5 Bad-6 失败富集压力测试

预先固定的强 baseline Official-failure Bad-6 已完成 12 条科研有效 episode。端到端结果是自由 Agent
`2/6`、目标状态重放 `4/6`；配对表为 2 对都通过、2 对只有 B 通过、0 对只有 A 通过、2 对都失败，
精确 McNemar `p=0.5`。B 的 4 个候选执行 7 次重放，其中 3 个为 Fail→Pass；最终重放和 Official 在
4/4 上一致。HARK 是最干净的因果救援：内部 fresh replay 暴露与 A 的 Official 完全相同的 Git ownership
错误，同一 session 增加 safe-directory 操作后通过 replay 和 Official。

该批没有证明显著性、泛化、效率或 SOTA。B 比 A 多用 5.8% Token 和 10.4% 端到端时间。更关键的是，
quacc B 在候选前搜索膨胀；ajenti 两组都已经达到 0 missing imports，却继续追求更广的 runtime completeness
而没有提交。micropy-cli A 也多次达到公开目标但未交付。下一主要矛盾因此是**成功候选保留与停止决策**，
不是 package 规则不足。

下一版只讨论一个简单的成功优先假设：首次得到可执行 Official-equivalent 候选时先保存并进入目标重放，
后续完整性或成本探索不能抹掉已有候选。Official success、部署完整性和路径成本保持独立评价轴。该假设
不能在已消费 Bad-6 上调 package 规则，必须在新的固定 development batch 上验证。

### 12.6 Certified-Incumbent 证伪与验证器触发交接

该假设已经在不改变调度 episode 的条件下完成检验。用历史 registry 修正 selection claim 后，主分析
包含 6 对 prospective case。B-FSR 为 `6/6`，C-GCI 为 `5/6`，qibolab 是 B-only；C 没有一次
fallback 激活。C 在全部样本和 5 对共同成功样本上都消耗更多资源。因此 certified-incumbent retention
退出核心方法，只作为未来正交安全 ablation 保留。

决定性的 qibolab 轨迹达到可信完整目标 Pass，却始终没有形成候选。这说明此前混淆了两个状态：
**环境已经充分**与**可重放的累计程序已经交付**。Prompt 不能稳定触发状态转换，而 replay 后才开始的
retention 又太晚，无法补救。

下一最小方法只给控制器增加一个职责：可信完整目标 Pass 后，在同一活跃 session 中切换到程序化和 clean
replay。自由搜索与 replay 修复仍开放；package、解释器和完整性仍由 Agent 决定。方法不增加 package
规则、跨 case memory、物理 checkpoint、候选图或自修改。

预注册的已消费 qibolab 资格实验完成了整条状态转换。两组都通过 Official。Scheduled control 在
request 72 首次 Pass，之后又花 11 次请求和 10 次 shell 操作才形成候选；treatment 在 request 64
Pass，只触发一次 handoff，request 65 提交，clean replay 暴露依赖冲突，同一 session 修复后在
request 66 通过 replay 和 Official。这证明机制可执行，不证明效果；更低的请求、Token 和时间只是一对
已消费样本的描述性结果。

Runner 0.6.0 还暴露了一个因果设计混杂：treatment prompt 在触发前提前说明了 handoff。Runner 0.6.1
删除该说明，使两组在触发前的工具和初始 prompt 完全相同；controller 指令只在可信 Pass 后出现。下一步
是在固定 prospective bad-case 上与 B-FSR 比较，本次资格实验不允许导出 qibolab 专用规则或其他 treatment。
