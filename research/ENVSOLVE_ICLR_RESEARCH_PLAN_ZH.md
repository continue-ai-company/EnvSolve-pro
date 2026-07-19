# EnvSolve：部分可观测的仓库部署状态化约束求解

> 持续更新的 ICLR 论文稿。英文版：
> [`ENVSOLVE_ICLR_RESEARCH_PLAN.md`](ENVSOLVE_ICLR_RESEARCH_PLAN.md)。
> 只有得到冻结实验支持后，本文档中的 claim 才会升级。

## 摘要

仓库部署既没有完整规格，也没有廉价 oracle。兼容的 runtime、ABI、语言与系统依赖、构建工具和
平台条件共同构成一个隐藏的真实环境状态。Agent 只能通过执行候选间接观察它：同一个 import 或
build failure 可能对应多种原因，网络故障和 timeout 还会让观测完全删失。因此仓库部署本质上是
部分可观测的状态化约束求解，而不只是 shell 命令生成。

现有语言模型 Agent 通常在失败后把终端输出追加到对话，再继续尝试。它们拥有 loop，却没有原则性
回答两个核心问题：本次执行究竟证明了什么？证据是否足以约束下一次尝试？因此真实项目约束、
含义不明确的失败和基础设施噪声很容易被混为一谈。

我们提出 **EnvSolve**，将仓库部署形式化为部分可观测的状态化约束求解
问题。每一轮中，EnvSolve 提出完整部署程序，在全新环境中执行，并把有依据的观测转化为显式
事实、假设和约束。确定性矛盾可以指导下一候选；含义不明确的证据保留为假设；带明确基础设施
签名的 timeout 保持 Unknown，没有此类签名的固定预算 timeout 则成为 candidate-cost evidence。
官方 benchmark evaluator 仅在在线 episode 结束后调用一次，绝不
提供修复反馈。

我们在 EnvBench 上，将 EnvSolve 与原始资源上限匹配、使用相同 backbone 的 raw-history 和自然语言
reflection 对照比较，测量最终部署成功率、修复效率、重复失败和 clean-replay 可靠性。开发分析
暴露了 runtime import 检查和 static missing-import 评测之间的校准缺口，由此产生了一个预注册的
两层 import-obligation verifier，将 runtime 语义与 static source 解析保留为独立证据。Held-out
结果尚未产生，因此本文当前不作性能提升 claim。

## 1. 引言

运行一个陌生仓库，是一个看似简单、实际复杂的推理问题。一次 import 失败可能意味着缺少包、
Python 版本错误、平台分支不匹配、可选功能未启用，或者项目本地模块没有被正确安装。一次安装
失败也可能来自 package mirror、构建工具不兼容或临时超时。这些观测并不支持同一种修复。

困难来自真实环境与 Agent 观测之间的关系。仓库具有一组未知的兼容性和依赖要求，但不存在一条命令
可以直接读出完整要求。执行只能给出投影：missing module 能指出某项要求未满足，却未必指出正确的
distribution；runtime import 成功不能证明 static source closure；timeout 几乎不提供候选本身的
信息。不同隐藏原因可能产生同一日志，同一隐藏原因也可能因基础设施变化产生不同日志。这就是部署
任务的**部分可观测性**。

观测同时具有真实成本。一条有用反例可能需要 clean checkout、新容器、package-index 流量、编译、
测试发现和下一次模型 proposal。这不定义任务本身，但要求受控评测：允许无限重试会把计算量伪装成智能，
也让方法比较失去意义。因此我们在模型调用与 token、candidate environment、命令和 wall-clock time
等原始资源上设置匹配上限。

它的意义也超出 benchmark 分数。大规模仓库的可靠部署是测试、代码理解、迁移与漏洞分析的入口。
一个不能区分环境证据与基础设施事故的引擎，无法以足够可靠的方式
复现项目并支撑这些下游系统。

多数 LLM 部署 Agent 使用对话式 loop：执行命令、观察输出，再让模型决定下一步。Loop 本身有用，
但状态是隐式的。Agent 容易重复失败命令，对网络错误反应过度，忘记哪些假设已被推翻，或者生成
一份只有依赖前一轮容器残留状态才能工作的脚本。

EnvSolve 从一个简单观点出发：**执行反馈只有先被解释为证据，才能约束下一次部署。** 因而方法
把通常混在一起的四个操作分开：

1. 提出完整部署候选；
2. 在独立环境中执行候选；
3. 判断本次执行究竟证明了什么；
4. 根据得到的约束状态生成下一候选。

这种分离不仅希望提高部署成功率，也让科学分析成为可能：在模型、反馈、评测权限和原始资源上限固定
时，我们可以直接比较结构化状态与 raw history。

本文形成三项贡献：

1. **问题定义。** 我们将仓库部署建模为部分可观测的状态化约束求解；执行结果只有进入显式、
   带 provenance 的状态后，才成为可用证据。
2. **方法。** 我们提出 EnvSolve：它生成完整部署程序，在 fresh environment 中验证，并对有依据的
   Fail、未决 hypothesis 和基础设施 Unknown 采用不同的 evidence-admission 规则。
3. **实证评测。** 我们在信息和原始资源上限匹配的条件下，将 EnvSolve 与相同 backbone 的 raw-history、
   reflection loop 做受控 EnvBench 对比，测量最终成功、修复行为、资源使用与 clean-replay 可靠性。

EnvBench 是主要试验场，而不是方法定义。Harness 隔离、artifact 日志和 fresh container 是有效
实验的必要条件，但不作为独立算法创新。

## 2. 问题定义

设 `R` 为固定 revision 的仓库，其潜在部署状态 `Z_R` 包含有效环境所需的 runtime、ABI、package、
build 与平台条件；`Z_R` 不能被直接观察。部署程序 `P` 是一串可重放环境动作，例如选择运行时、安装系统包、安装
语言依赖和设置安全环境变量。

在第 `t` 轮，Agent 提出 `P_t`。程序在 fresh environment `E_t` 中执行，内部 verifier `V`
返回观测 `O_t = V(P_t, E_t; Z_R, xi_t)`，其中 `xi_t` 表示网络可用性、package-index 状态等
干扰条件。该观测不能唯一确定隐藏状态：多个潜在状态可能解释同一失败，删失也可能不揭示任何候选
属性。因此 EnvSolve 不把 `O_t` 当作事实，而是更新显式约束状态：

`S_t = (F_t, C_t, H_t, X_t)`，

其中 `F_t` 是有依据的事实，`C_t` 是已接纳约束，`H_t` 是未决假设，`X_t` 是不可变执行证据。
下一候选来自 `G(R, S_t)`。实验记录每次 proposal 和 execution 消耗的原始资源，并在对比方法共享的
预注册资源上限到达时停止。

未修改的官方 evaluator `Q` 只对最终程序评分。每个 method、case、seed 至多调用一次，并且必须
发生在在线 episode 终止后；其输出不能进入 `S_t`。研究目标是在匹配实验条件下提高最终官方成功率，
而不是最大化尝试次数。

有效方案只能修改环境，不得修改应用源码掩盖失败、创建伪模块、削弱 evaluator，或使用从 held-out
结果中得到的 case-specific rule。

## 3. EnvSolve

### 3.1 完整部署候选

每个 proposal 都是一份必须从 clean checkout 独立工作的完整程序，而不是叠加在上一轮之上的
补丁。这样每个候选都能直接 replay，也避免成功依赖隐藏的容器历史。

Typed replay validator 接受环境 mutation，拒绝源码修改、纯观察命令、不安全路径注入和不支持的
shell 控制流。被拒程序会作为证据保留并消耗 candidate budget，但不消耗 environment 或 command
budget。

### 3.2 Fresh execution

每个被接受的候选都获得新的 checkout 与 container identity。EnvSolve 记录完整命令、stdout、
stderr、exit code、耗时、image digest、仓库 revision 和 environment identity。候选环境之间不
共享可写状态。

Fresh execution 属于算法，因为它检查候选程序是否自包含；但它与终局 benchmark evaluation 不同。

### 3.3 可执行验证

内部 verifier 检查不依赖官方 evaluator 反馈的普通项目属性，包括安装成功、package consistency、
项目编译、runtime facts，以及从项目源码和 metadata 中得到的依赖 obligation。

对于 Python import，EnvSolve 区分两层 obligation。**Runtime-semantic** 层判断当前候选平台和源码
控制流下 import 是否必须执行；**static-source** 层判断源码中可见的名称是否存在可发现的 module、
package、extension、namespace package 或 type stub。Guarded optional 与兼容 fallback 可以在
runtime 层不活跃，但仍属于 static obligation；`TYPE_CHECKING` import 只属于 static 层；对目标
平台可证明不活跃的分支豁免两层。无副作用 resolver 只检查候选解释器与物理源码路径，不调用官方
evaluator，不运行 Pyright，不查询 package index，也不使用仓库特定 module mapping。

Verifier 输出三种结果之一：

- **Pass：** 预注册内部 obligation 均满足；
- **Fail：** 可复现证据与当前部署假设矛盾；
- **Unknown：** 观测被删失，或无法归因于候选。

带明确网络或基础设施签名的 timeout 是 Unknown，而不是“需要换包或换命令”的证据。没有此类
签名的固定预算 timeout 只证明该 candidate 超出执行上限，可指导更低成本的下一候选，但不能断言
具体 package 原因。

### 3.4 证据接纳与状态更新

证据按强度接纳。确定性缺失 capability 可以进入 hard constraint；无法确定具体原因的 build
failure 保留为 hypothesis；格式错误、过期证据、复用环境和 forbidden feedback 一律 fail closed。

首次动作前，一个有界、无执行的 observer 只接纳标准项目 metadata 中无条件的 package requirement；
另一个断网、只读 probe 在精确 base-image digest 中观测 Python。标准 runtime requirement 只有能与
该 fresh fact 比较时才接纳。带 marker、格式错误、动态生成或 tool directive 的声明保持未接纳。
随后 fresh verifier 观测已安装 distribution 的 presence、version 与 runtime fact，使初始 requirement
只在 candidate-scoped evidence 满足或反驳它之前保持 unresolved。

Package manager 明确报告的 deterministic runtime incompatibility 会形成 hard requirement-fact
矛盾；含义不唯一的 action failure 仍保持 hypothesis 或 provisional state。这样，仓库声明与执行
反馈使用同一个带 provenance 的 runtime 表示。

每个 admitted fact 都记录来源 candidate、environment、verifier 和 raw evidence。后续观测可以
supersede 环境范围内的事实，但 fresh execution 只提供部分观测：后续 verifier 没有报告某变量，
不等于该变量已经满足。只有相同 `(domain, subject, predicate)` 获得新 fact 时，旧 fact 才退休；
hypothesis-only 或无关观测必须保留未解决 obligation。底层 event 始终不可变。
一份完整 verifier report 可以同时包含已修复变量的正观测和仍被违反变量的反例；不完整或 Unknown
报告中的观测不进入 hard state。

### 3.5 反例驱动修复

候选失败后，下一次模型调用接收仓库上下文、未解决 conflict、近期候选结果、verifier 摘要和有界
terminal evidence，并必须重新提出完整程序。该投影是受 aggregate budget 约束的充分统计量：raw
finding 与完整 constraint record 继续保留供审计，但不会在模型上下文中重复展开。当内部 Pass、
预算耗尽、policy 明确 blocked，或 Unknown 使修复失去依据时，loop 终止。

模型格式错误在固定次数内可恢复：系统对原始输出做哈希、记录并作为协议错误反馈，不创建容器。
这样可以避免偶然格式问题终止部署搜索，同时保留其真实成本。

当状态包含受支持的 hard conflict、高置信 unresolved requirement，或依赖上一候选环境才成立的
satisfaction 时，确定性 planner 将其投影为带 provenance 的 `OperationPlan`。最后一种情况很关键：
下一候选从 fresh environment 开始，因此让上一环境满足约束的操作必须保留在完整程序中。模型选择
具体修复参数，guard 检查当前候选是否覆盖每项操作义务，并阻止候选原样经过一个已经观测到会失败、
且任何新修改尚未生效的执行前缀。该机制把“缺什么或冲突在哪里”与“允许怎样改变环境”连接起来，
同时不依赖仓库专属 package map。拒绝只消耗候选与模型预算。

### 3.6 为什么它不只是另一个 Loop

Raw-history、reflection 和 EnvSolve 都可以执行多轮候选。区别在于反馈的表示与接纳方式：raw-history
保留日志，reflection 让模型总结日志，EnvSolve 使用类型化状态，并且只有有依据的证据才能约束
后续动作。主实验将在共享总预算下隔离这一差异。

## 4. 评测

评测检验三个假设：EnvSolve 在总预算匹配时提高最终部署成功率；提升来自结构化约束状态与 evidence
admission，而不是更多尝试；最终部署程序在 clean environment 中具有更高 replay 可靠性。

### 4.1 Benchmark 与数据划分

主要 benchmark 是 EnvBench 的 329 个 Python 仓库。开发仅限官方 train partition 中已声明的 case。
每次新机制决策必须在单独冻结的 development batch 上资格验证。算法冻结后 Canary-20 只运行一次；
方法与分析决策冻结前，Official-Test-100 保持 untouched。

EnConda-Bench 不属于本文。评测期间，EnvSolve 不进行跨 case 更新，也不检索其他 case 的
自然语言经验、总结或轨迹。

### 4.2 Baseline 与对照

我们比较固定 native baselines、Repo2Run 和 same-backbone controls。核心因果对比包括：

- 原生部署 Agent；
- 使用 fresh candidate 的 raw-history loop；
- 自然语言 reflection loop；
- 不持久化 constraint 的 EnvSolve v0；
- 完整 EnvSolve。

所有 feedback-loop 方法获得相同模型、case、seed、image、raw online information、官方 evaluator
调用次数和全局资源预算。方法可以提前停止，但不会为每个候选重新获得预算。

### 4.3 指标

主指标是 EnvBench Official Pass@1。次指标包括固定资源上限内成功率、失败后修复概率、重复失败率、clean-
replay 成功率、token、模型请求、命令、环境和 wall time。美元成本如果报告，只是按带日期的 provider 价格快照
得到的附属换算，不是匹配变量或主指标。确认性比较报告 paired effect size 与 confidence interval。

### 4.4 消融

我们分别移除 typed constraint state、evidence admission、provenance 和 fresh replay；同时用自然
语言摘要替换显式状态，并改变 candidate 与 token 上限以测量 success-resource curve。

## 5. 结果

### 5.1 协议有效性

实验基础设施现在把 artifact integrity 与 scientific eligibility 分开。完整性审计检查 identity、
hash、ledger、trajectory 和 official claim；科学有效性还要求已提交且干净的源码 revision、冻结的
原始资源预算、完整且没有 host suspension 嫌疑的 runtime heartbeat，以及与 schedule 一致的执行。
唯一的可恢复 coordinator 负责进程组硬截止时间，确定性 summarizer 从 hash-chained run evidence
生成全部表格项。这些性质保证实验有效，但不能证明 EnvSolve 有效。

### 5.2 开发诊断

已消费的 development trajectory 暴露出四类通用 calibration failure。第一，runtime import
成功并不足以代理 static deployment objective，因此需要两层 obligation verifier。第二，把每次
fresh-verifier 输出当作完整快照会错误清除未解决冲突；当前状态转移会保留旧 fact，直到同一变量
被再次观测。第三，对日志叶子逐项截断不能保证结构化 prompt 有界；EnvSolve 现在把事件历史投影为
紧凑 conflict、候选结果、verifier 摘要和分组 operation obligation，并统一受 aggregate context
budget 约束。第四，创建虚拟环境却不将其绑定到后续验证，会让已安装依赖看起来仍然缺失；
完整候选现在必须在验证前激活它创建的每个环境。

首个 artifact-valid 的五组 operation qualification 在描述性结果中产生一组 full-only pass、一组
both-pass、两组 both-fail 和一组 infrastructure-censored pair。在 both-pass pair 中，full 使用
2 个 candidate，free-form control 使用 5 个。后续 provenance review 发现这些 run 早于首个 Git
baseline，因此五组 pair 全部不具备 scientific eligibility，只能用于错误分析。下一批五组 pair
同样被排除：host suspension 造成多次 wall-clock 超限，通用 DSL 缺口还错误拒绝了有效 PDM 安装。
PDM install/sync 和项目 venv 语义绑定现在已有合成测试覆盖，两批 consumed case 都不会重跑。

后续一批满足干净 contract 的开发实验产生 10 个 scientifically eligible run，但 official pass 为 0。
五组 pair 中四组没有进入 official evaluation；唯一 official pair 中，完整 EnvSolve 将 missing-import
issues 从 28 降到 1，但仍然失败。错误分析发现，当前 operation plan 在首次执行前为空，因此尚未把
仓库观测转成初始约束；实验还发现一个 documentation source coverage 缺口和过度保守的 timeout
classifier。两个通用机制 bug 已为未来 unseen development case 修正，失败 batch 仍保持 consumed。
这个负结果收窄了方法 claim：只有类型化的被动修复还不够，下一方法版本必须定义保守的 pre-action
constraint admission。

该版本现在只在首次 proposal 前接纳无条件的标准 package declaration，并通过 fresh installed-
metadata observation 闭合这些约束。机制与干净、已提交的 EnvBench evaluator 已在下一批
outcome-blind 实验前冻结。随后按照预注册、仅使用 metadata 的哈希规则选择 5 个新 development
identity。该 batch 按照预注册 shared-defect rule 在执行 3 个 pair 后关闭；6 个 run 均 scientifically
eligible，但没有任何 run 进入 official evaluation。两个 pair 触发 pre-action package admission，
然而一个确定性的 Python version mismatch 始终没有成为 hard runtime constraint，后续 candidate
因此可以删除兼容 runtime 并退回已知无效的基础解释器。这个负结果说明仅接纳 package state 还不够：
runtime compatibility 与 action feasibility 必须进入同一个持续约束状态。

对应的 runtime-state revision 在检查新的 development repository 前已经实现并冻结。它把
fresh base-runtime fact 绑定到候选镜像，依据该 fact 接纳标准 runtime declaration，把确定性版本
mismatch 变成 hard contradiction，并在 fresh attempt 之间保持由候选操作支撑的 satisfaction。
合成 transition 测试和真实 Docker 边界验证了这些语义；这只是机制验证，不是部署成功率提升证据。
新的 5-pair development qualification 已完成预注册、在不检查 repository 的前提下盲选并冻结执行
入口。它以 runtime-state invariant 为主要检验，以 paired official outcome 为次要结果。Batch 启动后，
首个 ablation episode 在 verification 前被人工中断，并以 ineligible/Unknown 保留且不得
重跑，因此该 pair 被删失。随后 eligible full counterpart 真实触发机制：base-image identity 保持
正确，显式 runtime mismatch 后也存在后续 proposal 机会；但 mismatch 仍停留在文本，没有形成 hard
constraint 与 runtime operation obligation。这个主要不变量失败使 batch 在 pair 1 后关闭。它是负面
机制结果，不是 effectiveness estimate；其余 schedule case 不再执行。

当前最小 revision 只修复这条已观测到的状态转移缺口。它接纳精确的 subject-first Python mismatch
diagnostic，用 PEP 440 校验 version 与 range，并且只有 reported version 确实落在允许范围之外时才
创建 hard contradiction。合成正例、范围兼容、格式错误、信息不完整和模糊措辞反例共同约束 admission
边界；端到端 loop 测试证明被接纳的证据会在下一次 proposal 前生成 `runtime_configure` obligation。
该修改不包含 repository、package、tool 或具体 version 规则，也不改变 Poetry command coverage。
它已经冻结为 mechanism v10 与 Harness v24。这只建立内部语义，使用新 untouched development
identity 的资格验证仍未完成。

该资格实验现已完成预注册与执行绑定。Metadata-only hash 从 156 个 untouched development case 中
选择 5 个新 identity，剩余 151 个；在检查任何 selected repository 前，exact evaluator image 已完成
attestation。触发条件、停止规则、预算、调度和受限基础设施重试都在执行前冻结。随后 pair 1 因共享
verifier 缺陷关闭 batch。两条 eligible run 都进入 internal
test collection，其中 repository-local service 拒绝 localhost 连接；不感知阶段的 `ConnectionError`
签名把该 candidate failure 错标为 dependency-acquisition infrastructure，并在下一次 proposal 前终止
两条 loop。目标 v10 diagnostic 没有出现，因此 v10 是未触发，而不是被反驳。该 pair 被删失，其余
case 不执行，也没有 official result 或 effectiveness estimate。

最小修复使用已经记录的 failed-action phase。现在只有 candidate command 或 unknown phase 中的网络
签名可以删失 episode；固定 internal check 产生的异常必须保留为 candidate feedback。相反方向的合成
测试与 Q9 raw artifact 只读 replay 验证了这条边界，没有命名观测到的 service 或 repository。该
revision 已冻结为 v11。这仍只建立内部语义，不代表部署效果。

新的 5-pair v11 资格实验现已完成预注册与执行绑定。Metadata hash 从 151 个 untouched case 中选择
5 个 identity，剩余 146 个。Phase trigger、反向 network-safety invariant、schedule 与预算都在选样
前固定；当前没有查看 selected repository 或模型结果。

每项修正都先使用合成反例定义，再进入新的 outcome-blind development batch。触发问题的 batch
永久保留为 consumed diagnostic，机制变化后不得恢复执行。这些结果只能验证问题结构和协议行为，
不能证明 held-out effectiveness。当前没有使用 Official-Test 或 Canary 结果，论文也不作性能提升
claim。

### 5.3 主对比与消融

表 1 比较所有资源匹配对照的 Official Pass@1，表 2 报告组件消融；配套分析给出 success-resource
curve、重复失败率与 internal-verifier calibration。预注册确认性运行完成前，这些结果位置保持
为空。所有 Fail 与 Unknown 都保留在分母中。

## 6. 相关工作

EnvSolve 连接四类研究：面向软件工程的 LLM Agent、自动化软件环境构建、execution-guided program
synthesis，以及工具型 Agent 的 reflection 或 memory。预期区别不在于“存在执行 loop”，而在于
terminal-only evaluator 下使用类型化、带 provenance 的 constraint state 和显式 evidence admission。

与自由格式 reflection 和 memory 相比，EnvSolve 通过 evidence admission 限制状态更新；与
counterexample-guided synthesis 相比，它面对的是有噪声、被删失的软件执行，而不是完整符号规格；
与现有 deployment Agent 相比，它在预算匹配下隔离 state representation 的作用。本工作稿暂不加入
引用，待 related-work audit 完成后统一补齐。

## 7. 局限性

EnvSolve 不能在不违反环境任务边界的情况下修复应用缺陷。内部验证必然只是 terminal deployability
的近似，可能不完整。Fresh environment 提高因果清晰度，但增加时间与计算成本。网络和 package
index 故障会产生删失结果，尤其在本地开发机器上。EnvBench 只覆盖仓库部署问题的一部分，更广泛
语言和平台 claim 需要单独证据。

## 8. 结论

EnvSolve 研究这样一个问题：当执行反馈被视为显式约束状态的证据，而不只是更多对话上下文时，
仓库部署是否会更可靠。方法提出完整程序，在 fresh environment 中测试，只接纳有依据的反例，并
保持官方评测为终局操作。实验协议和核心 loop 已实现，但决定性的 held-out 对比仍待完成。修正后的
可执行语言、双层审计、调度器和分析流水线均不使用 case-specific 或 evaluator-derived rule。
首次 outcome-blind runtime-state qualification 已暴露窄 diagnostic-admission failure 并关闭。
最小合成修复与新 mechanism freeze 已完成，但下一次资格实验在 v10 被触发前，因不感知 failure
phase 的 infrastructure classifier 缺陷而关闭。Phase-aware v11 现已冻结，下一里程碑是使用新的
untouched development identity 完成资格验证；该实验现已可执行。机制通过资格验证前，held-out
evaluation 保持锁定。

主 loop 也已经实现最小的“约束到操作”边界：hard conflict、unresolved requirement 和由候选支撑的
satisfaction 产生带 provenance 的操作义务，类型化 guard 要求下一份完整程序在 fresh execution 中
覆盖这些义务。
