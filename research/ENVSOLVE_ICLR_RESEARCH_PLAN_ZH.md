# EnvSolve-Pro：部分可观测仓库部署的状态化约束求解

> 持续更新的 ICLR 论文稿。工程过程与逐轮实验账本保留在详细研究计划中，不进入正文。

## 摘要

自动部署陌生仓库不是照抄依赖声明，而是在不完整信息下恢复隐藏的 runtime、依赖、构建和平台条件。
Agent 只能通过执行看到局部症状；在构造环境中成功的方案，可能在目标镜像的新 checkout 中失败。因此，
仓库部署更适合被视为**部分可观测的状态化约束求解**，而不是一次脚本生成或无边界命令试错。

本文首先建立轨迹观测系统，并以最早产生决定性影响的因果失败为单位，将错误定位到**观测、约束、操作**
三层。该分类与部署方法族正交：自由反馈搜索、硬约束、软约束和干净重放可以组合，但会产生不同的错误
分布。

我们进一步提出 **EnvSolve-Pro**。一个连续 Agent session 先自由构造完整 bootstrap；观测层在目标初始
状态中重放该程序，约束层把可执行反例作为当前 case 的软约束返回同一 session，操作层据此修改完整程序
并再次重放。算法不含包规则库、跨 case 记忆、物理 checkpoint、候选图或 harness 自修改。

开发期证据表明，该机制能修复普通构造环境隐藏的完整程序缺陷。在预先固定的 6 个强 baseline 失败 case
上，自由 Agent 通过 `2/6`，EnvSolve-Pro 通过 `4/6`；但精确 McNemar `p=0.5`，尚不足以支持显著性、
泛化或 SOTA 声明。轨迹同时揭示下一主要矛盾：Agent 经常已经满足 Official 目标，却因继续追求更广的
部署完整性而没有交付候选。确认性实验将在算法冻结后进行。

## 1. 引言

项目复现、测试、程序分析、迁移和安全审计都依赖一个可执行环境，但真实仓库通常没有完整、可靠且可
直接执行的环境规格。一个 missing import 可能意味着 distribution 缺失、Python 版本不兼容、平台分支
未满足、项目没有正确安装，或静态分析器观察了错误的环境。相似日志可以来自不同原因，同一原因也可能
产生不同日志。

这个问题有三个困难：

1. **隐藏条件。** 有效环境由源码、metadata、构建系统、平台和外部 package index 共同决定，无法一次
   读出。
2. **局部观测。** 一次执行只能反驳或支持当前方案的一部分；网络超时还可能让结果无法归因。
3. **状态迁移。** Agent 在污染过的构造环境里逐步成功，不代表这些操作能从目标初始状态重建同一结果。

强编码 Agent 已经擅长阅读仓库和自由试错，但强模型并不会消除上述结构：模型仍可能在错误环境中验证、
忘记早期必要操作、继续优化已经足够的候选，或只在终局 evaluator 中发现 fresh-state 缺陷。我们的目标
不是用规则替代强 Agent，而是给它一个能够暴露真实反例、保留推理连续性并交付可重放程序的闭环。

本文有三项贡献：

1. **轨迹系统与失败分类。** 我们记录部署命令、环境身份、完整候选、干净重放和终局结果，并提出与方法
   族正交的 Observation--Constraint--Operation 因果分类，用于比较不同 deployer 的错误分布。
2. **EnvSolve-Pro 算法。** 我们提出一个最小三层算法：目标状态观测、session 内软反例约束、完整程序
   修复与重放。它保留强 Agent 的动作空间，不依赖跨 case 手工规则。
3. **受控实证研究。** 我们在 EnvBench 上比较同模型自由 Agent、旧硬约束 EnvSolve、Repo2Run、EnvBench
   Agent 和原生 Codex，报告 Official Pass@1、错误分布迁移、候选到达率、重放修复和成功优先的资源结果。

EnvBench 只是 testbed。Evaluator 隔离、仓库审计和统一结果采集属于公共实验底座，不被包装成算法贡献。

## 2. 问题定义

给定固定 revision 的仓库 `R` 和目标初始环境 `E0`，隐藏兼容状态 `Z_R` 包含语言 runtime、包版本、ABI、
系统库、构建工具、平台谓词和环境变量。部署程序 `P` 必须从 `E0` 构造一个满足公开目标 `G` 的环境。

执行内部 verifier 得到观测：

`O_t = V(R, P_t, E0; Z_R, ξ_t)`，

其中 `ξ_t` 表示网络和 package-index 等干扰。`O_t` 通常不能唯一确定 `Z_R`：bootstrap 成功只能说明该
路径在本次状态可执行，失败也可能同时兼容多个原因。

EnvSolve-Pro 的状态由当前完整程序、同一活跃 session 中已经观察的反例，以及对应重放记录组成。状态化
并不要求一套庞大的类型规则；它只要求 fresh environment 被重置时，已经证实的失败和程序修订不会随之
丢失。

不可见的 Official evaluator `Q` 只在 episode 结束后评测最终程序。对 EnvBench Python，Official Pass
要求 bootstrap 退出码为 0 且 `reportMissingImports` 为 0。在线求解不能读取 `Q` 的反馈。

资源限制属于实验设置，不属于问题定义。首要目标是部署成功；Token、时间、命令数和存储都是需要报告的
结果，只有在不牺牲成功率时才讨论效率改善。

## 3. 失败分类

### 3.1 两个正交维度

我们区分**部署机制族**与**失败发生层**。

部署方法族描述 deployer 如何行动：

- **F，自由反馈搜索：**Agent 根据普通执行反馈自由选择下一步；
- **C_h，硬约束：**编码规则强制、拒绝或改写候选；
- **C_s，软约束：**可执行证据影响当前推理，但不禁止 Agent 的动作；
- **R，干净重放：**在目标初始状态执行完整候选，并把反例返回当前求解过程。

失败层描述最早的决定性原因：

- **观测失败：**必要事实未被看见、看错环境、把噪声当事实，或 construction 与 target state 不一致；
- **约束失败：**没有识别缺失条件或冲突，误判因果，或混淆 Official 目标与更广的部署完整性；
- **操作失败：**动作不能解除约束、顺序或 shell 状态错误、程序不能重建成功状态，或没有及时形成和交付
  候选；
主算法归因只有这三层。表面的闭环停滞，如果是证据没有被保留或更新，归入约束层；如果已经表示出的
要求没有改变动作或触发重验，归入操作层。轨迹无法区分时标为 Unresolved，而不是新增第四层。基础设施
事故单独标为 Unknown。每个失败 episode 归入“修复后最早可能改变终局结果”的那一层，并可保留
secondary tags；分类依据完整轨迹，而不是最后一条报错字符串。

### 3.2 Baseline 的机制位置

EnvBench FreeAgent 和同模型 Raw ReAct 主要属于 F；原生 Codex 是连续 session 和持久构造环境中的强 F；
Repo2Run 结合 F 与修改失败后的局部 checkpoint/rollback；旧 EnvSolve 结合 F、大范围 C_h 和历史重放。
EnvSolve-Pro 研究最小的 F+C_s+R。

这些映射用于解释错误分布，不把复杂系统比较伪装成单一组件的纯因果效应。第一篇论文不穷举所有机制
组合；自动搜索 harness 组合属于后续 Auto-EnvSolve。

## 4. EnvSolve-Pro

### 4.1 三层闭环

**观测层：发生了什么？**

Agent 可以在连续构造环境中自由读取仓库和执行命令。当它形成完整 bootstrap 后，观测层在目标镜像的
新 checkout 中从头执行该程序，并运行与公开目标等价的内部 verifier。记录包含目标环境身份、程序、最早
失败阶段、退出状态和有界原始日志。

**约束层：现在缺什么或冲突在哪里？**

重放失败原样返回同一个活跃 session。Agent 根据仓库上下文，把它解释为当前 case 的软约束，例如“可编辑
安装前 Git 必须接纳该 checkout”或“隔离构建看不到 Cython”。反例不会被自动升级为跨仓库规则，也不会
通过 guard 限制强 Agent 的动作空间。网络或基础设施信号保持 Unknown。

**操作层：怎样改变环境？**

Agent 修改的是完整 bootstrap，而不是只修当前容器的一条命令。新程序再次从目标初始状态执行。通过后，
交付的正是被重放过的程序；失败则继续同一 session 中的观察、约束更新和操作修订。

### 4.2 算法

```text
在连续 session 中自由探索仓库并形成完整程序 P0
for t = 0, 1, ...:
    Ot <- 在目标初始状态中执行并验证 Pt
    if Ot == Pass:
        return Pt
    if Ot == Unknown:
        保留候选，不把 Unknown 写成兼容规则
    else:
        将可执行反例返回同一活跃 session
    Pt+1 <- Agent 根据仓库、历史和 Ot 修改完整程序
```

算法刻意保持最小。它不包含包规则库、跨 case memory、typed persistent ledger、候选图、物理 checkpoint、
假设搜索、程序最小化或 harness 自修改。这些机制只能作为后续正交 treatment，而不是在缺乏证据时叠加。

### 4.3 为什么强 Agent 仍需要它

强 Agent 可以记住对话，也能自主总结事实，但它无法仅靠推理知道程序在尚未执行的目标初始状态中会发生
什么。EnvSolve-Pro 提供的不是更多文字经验，而是一个新的干预：把完整程序放进必须成功的状态中执行，
并让反例回到仍然理解整个仓库和修复历史的同一 session。模型越强，越能利用该反例；方法不依赖模型
不会自行推理。

## 5. 实验设计

### 5.1 研究问题

- **RQ1：失败结构。** 不同部署机制族在观测、约束和操作错误上的分布如何？
- **RQ2：成功率。** 同 backbone、同信息和同 Official 权限下，F+C_s+R 是否优于 F？
- **RQ3：模型依赖。** EnvSolve-Pro 对较弱 API 模型和原生 frontier Agent 是否都提供增益？
- **RQ4：代价与质量。** 达到相同或更高成功率时，重放如何改变时间、Token、命令、存储和部署完整性？

### 5.2 比较方法

同模型因果主比较使用固定 DeepSeek V4 Flash：自由 Agent F、F+R、EnvSolve-Pro F+C_s+R，以及冻结的旧
硬约束 EnvSolve 系统。外部比较包括 EnvBench Agent 和 Repo2Run。原生 Codex 使用其原生 CLI 和当前可用
的 frontier 模型，作为独立能力上界参考，不被称为同模型 control。

所有方法共享仓库 revision、目标镜像、公开目标和终局 Official 权限。只有算法本来就拥有的反馈可以进入
loop；Official evaluator 对所有方法都只在终局调用。

### 5.3 数据与防过拟合

回顾性已消费轨迹只用于归纳 taxonomy 和提出机制。算法开发使用预先声明的 development batch；一个 case
一旦被观察，就不能再支持未见泛化结论。算法、prompt、模型、provider、taxonomy 和分析规则确定后，才
依次打开 Canary、protected test 和完整官方协议。

EnvSolve-Pro 第一篇不进行跨 case 学习。开发/测试分离限制的是研究者和 harness 的适配，不是假装算法在
训练参数。EnConda-Bench 不属于本文。

### 5.4 指标与统计

主指标是端到端 EnvBench Official Pass@1。一个科学有效但没有形成候选的 episode 计部署失败；只有明确的
基础设施或实验者事故才删失。

次指标包括候选形成率、首次重放失败率、同 session Fail→Pass 修复率、final replay 与 Official 一致率、
错误类别迁移，以及 Token、请求、命令、wall-clock 和存储。Official success、环境纯度、部署完整性和
路径成本分别报告，不通过事后 gate 改写主标签。

主要比较使用 case 内配对结果、置信区间和 exact McNemar。资源是成功优先的 outcome，不是停止 Agent 的
核心目标。

## 6. 当前开发证据

轨迹 census 已覆盖多种系统，并暴露了 fresh-state drift、硬边界误杀、package-index 歧义、候选不交付和
指标通过但路径不完整等重复模式。该语料用于 taxonomy discovery，不用于估计系统成功率。

重建后的已消费跨方法矩阵包含 48 个 method--case row，其中 36 个完成 Official：原生 Codex 在完成评测的
episode 上为 6/15，旧 causal-v3 为 3/10，复现 Repo2Run 为 1/11。模型能力、公开目标可见性和删失模式
不同，因此这些数值不能作为可比成功率；它们只用于暴露不同轨迹并建立三层 taxonomy。算法效果只由后续
同 backbone 的 matched study 估计。

目标状态重放的 outcome-independent 开发证据累计 8 对：自由 Agent 为 `6/8`，EnvSolve-Pro 为 `7/8`，
只有一个 discordant pair（`p=1.0`）。这些 case 证明机制可执行，但大多过于容易，无法识别效果。

因此我们在实验前从既有强 baseline Official 失败 census 固定 Bad-6。结果为 A `2/6`、B `4/6`，配对表
是 2 both-pass、2 B-only、0 A-only、2 both-fail，精确 McNemar `p=0.5`。B 的 4 个候选共执行 7 次重放，
得到 3 次 Fail→Pass；最终重放与 Official 在 `4/4` 上一致。

HARK 提供最干净的因果案例：A 只在 Official fresh checkout 中遇到 Git `dubious ownership`；B 的第一次
内部重放复现同一错误，同一 session 增加 safe-directory 操作，第二次重放和 Official 均通过。这支持
“目标状态反例可以修复隐藏的完整程序缺陷”这一窄结论。

但 quacc B 在候选前耗尽搜索；ajenti 两组都已达到 0 missing imports，却继续追求 runtime completeness
而没有提交。B 在 Bad-6 上多用 5.8% Token 和 10.4% 端到端时间。因此当前证据不支持显著性、总体效果、
效率或 SOTA 声明，并把下一主要矛盾定位为成功候选保留与停止决策。

我们在另一组 6 对 prospective development case 上检验了最简单的保留策略。Control 为 `6/6`，prompt
引导的程序化加 certified incumbent 为 `5/6`，并且在共同成功 case 上仍消耗更多资源。失败 treatment
虽然达到可信目标 Pass，却没有交付程序，因此根本没有 incumbent。这个负结果区分了**状态已经充分**与
**程序已经交付**，否决了 prompt 引导加 replay 后 retention 作为核心方案。下一候选是在同一活跃 session
中，由 verifier 把可信 Pass 转换为程序化和 replay 阶段；其效果尚未验证。

## 7. 局限性

当前结果来自小型、失败富集的 development batch；模型、provider、ARM64 平台和网络状态都可能影响轨迹。
EnvBench 的 missing-import 目标不能代表完整可执行部署。软约束仍由模型解释，可能误判反例；目标重放也会
增加网络和执行成本。最终结论必须来自未见 case、多模型、外部 baseline 和路径质量审计。

## 8. 结论

仓库部署的核心困难不是生成更多命令，而是在部分观测下发现隐藏兼容条件，并把反例转化为能够从目标
初始状态重建的程序。EnvSolve-Pro 用一个最小三层闭环连接强 Agent 的自由推理与目标状态执行。开发证据
证明 replay 能产生真实修复，也说明“状态已经充分”不会稳定地导致“程序已经交付”。Prompt 引导的
incumbent treatment 已被该检验否决。尚未解决的算法步骤是在不限制自由搜索、不增加 case 特定规则的
前提下，用可执行 verifier trigger 把观测层的 Pass 交接到程序化阶段。
