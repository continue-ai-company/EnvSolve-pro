# Post-v7 Evidence Proposal / v7 后续证据实验提案

Status: proposed, not started. This is an experiment memo, not an ICLR draft.
状态：仅提案，尚未启动。本文是实验备忘录，不是 ICLR 稿件。

## 中文

### 当前判断

主要矛盾不是规则不足，而是尚未确认强 Agent 的可修复终局失败有多普遍，且同一程序的执行结果会波动。
历史 v7 的固定 8 个位置中，5 个 P0 首次执行通过，1 个重试通过，1 个基础设施未解决，1 个源码不可得；语义修复机会为 0。
python-control 的同字节程序却出现在线通过、终评缺失导入和另一分支通过。这支持研究执行稳定性，但不支持反馈算法增益。
因此保留最小 replay 假设为未证实候选，不晋升 v7；Live frontier 维持 kill。

v7 在线返回 Official 路径结果，并使用已结束 P0 的无工具子会话。它不能充当当前“同一活跃 session 中的独立 target-state replay”的资格证据。
以后 Official 只用于 episode 结束后的最终评估，不把输出传给任何在线 Agent。

### 实验 1：同程序重复执行

- 问题：固定仓库、revision、完整脚本、镜像和执行器时，终局评分是否一致？
- 对象：已消费的 python-control、qtconsole、yapf 三个 P0 原脚本。前者和后者已有不一致，qtconsole 作为对照。这个选择是诊断性选样，不能估计全体 Dev 的稳定率。
- 数量：每个脚本 5 次新执行，共 15 次。按三个项目轮换顺序执行 5 轮，避免把项目与时间段完全混淆。
- 条件：同一 Spark；沿用已记录镜像身份与执行器版本；每次独立干净目录和容器；复用只读源码，不新增跨执行可写依赖缓存。记录实际解析出的依赖版本，不声称未固定的包索引是恒定的。
- 终点：每次记录原始 bootstrap exit、报告是否存在、官方 issuesCount、缺失导入集合以及外部故障证据。模糊的 versions:none 或解析回溯保留为原因未决，不能自动叫作网络失败。
- 停止规则：完成预定 15 次尝试即停止；不追加“直到通过”的重试，不替换项目。传输观测超时先检查原进程，不能重复启动。主机不可用则保留未完成状态，恢复后继续同一计划。
- 裁决：一次无外部故障解释的同字节语义差异即可否定本配置的确定性假设；5 次一致只能给出有限稳定证据。只观察到外部删失时，报告可用性不足，而不是证明程序不稳定或稳定。
- 本实验没有在线 Agent、没有 treatment，也没有模型调用。它只检验评分可重复性。

### 实验 2：强 Agent 首次程序的 Dev 普查

- 问题：不按弱基线输赢挑样本，强 Agent 形成完整程序后真实失败的比例是多少？失败中有多少能给 replay 提供反例？
- 抽样：先确定当前授权的显式 Dev 名单，不读取 Protected Canary/Test；按 case ID 排序后，用 Python Random(20260904) 不放回抽取 24 个。抽样不读取任何基线胜负或新 treatment 结果，公开记录与历史样本的重叠。授权池不足 24 个时先修订方案，不静默缩样。
- 样本量理由：24 是快速估计机会率的 pilot，不是方法有效性检验。若 24 个独立有效样本均无失败，失败率的一侧 95% 二项上界仍约 11.7%，不能宣称强 Agent 已刷满；有删失时该界不能直接用于全样本。
- 方法：Mac 统一控制同版本强 Agent，AgentHub 最多两个构造槽；Spark 单独做 episode 结束后的 Official。模型、工具、公开目标和初始条件在执行前记录，过程不限制自由 Agent 的操作策略。
- 终点：首先按全部 24 个抽样位置报告有效程序提交及合法 Official Pass@1；另列未提交、bootstrap 失败、缺失导入失败、源码不可得、明确基础设施故障和原因未决。合法性审核未完成的 metric pass 不能升级为合法成功。
- 停止规则：只跑固定 24 个位置，不因看到失败或成功提前停止、不替换删失位置、不启动 F/N/A2。未完成进程按原身份恢复。时间、token、费用只报告；保留公共安全超时并单列触发情况。
- 解释：同时报告完整样本成功下界、把未决位置视为可能成功的上界，以及有效执行条件下的描述性机会率。该样本代表授权 Dev，不自动代表 EnvBench 全榜。
- 只有确认真实的强 Agent 终局失败后，才提出下一版独立 target-state replay 对照。失败若发生在完整程序形成之前，明确列为 replay 当前无法直接解决的边界。

### 待监督裁决

先审定历史 v7 与当前目标的不兼容、CLI 版本偏差及模糊重试资格，再审定上述两个实验。此文不修改旧协议，也不授权进入代表性 treatment Phase 2 或受保护数据。
不引入新的 frontier、跨 case 经验、checkpoint 或符号约束框架。

## English

### Judgment

The immediate uncertainty is the prevalence of repairable terminal failures from a strong Agent, compounded by outcome variation for identical programs.
In the fixed historical v7 batch, five initial P0 executions passed the metric, one passed only on retry, one remained infrastructure-unresolved, and one had unavailable source. There were zero semantic repair opportunities.
The identical python-control program nevertheless produced an online pass, a postepisode missing-import failure, and a pass in another arm. This motivates repeatability diagnosis, not a feedback-effect claim.
Retain minimal replay as unproven; do not promote v7. Live frontier remains killed.

Historical v7 returned Official-path results online and continued completed P0 prefixes in tool-free child sessions. It cannot qualify the current mechanism: independent target-state replay inside the same active session. Official must remain postepisode-only in new work.

### Experiment 1: Repeatability

Use the original consumed P0 programs for python-control, qtconsole, and yapf: two observed instability examples and one comparison. This diagnostic selection cannot estimate population-wide stability.
Execute each five times on Spark, in five interleaved rounds, for 15 total executions. Preserve repository revision, program bytes, recorded image identity, executor version, independent clean workspaces, and read-only source reuse. Do not introduce mutable shared dependency caches. Package-index state remains a possible source of variation and is not assumed fixed.

Record every raw exit, report presence, Official issuesCount, missing-import multiset, and external-failure evidence. Empty indexes and resolver backtracking remain unattributed unless corroborated. Stop after the 15 scheduled attempts; no success-seeking retries or replacement projects. Observation timeouts require checking the original process, not launching another execution.

One unexplained semantic disagreement refutes deterministic behavior for this configuration; five agreements provide only limited evidence. External censoring alone establishes neither semantic stability nor instability. This diagnostic has no online Agent, treatment, or model calls.

### Experiment 2: P0 Prevalence

Establish the explicitly authorized Dev population without reading protected data. Sort IDs, then sample 24 without replacement using Python Random(20260904), independently of all baseline outcomes and treatment results. Record prior exposure overlap. If the authorized pool is smaller, revise the proposal before execution rather than silently shrinking it.

Twenty-four cases are a prevalence pilot, not an efficacy test. With zero failures in 24 independent evaluable cases, the one-sided 95% binomial upper bound is still about 11.7%; censoring prevents directly applying this bound to the full sampled population.

Use a common Mac Agent controller and recorded model/CLI configuration, at most two AgentHub construction jobs, and serial postepisode Official scoring on Spark. Do not constrain the free Agent's action strategy. Report legitimate Official Pass@1 over all 24 sampled positions, plus non-submission, bootstrap failure, missing-import failure, source unavailability, explicit infrastructure failures, and unresolved attribution. Metric passes pending admissibility review are not legitimate successes.

Complete exactly the 24 positions, with no outcome-driven early stopping, replacements, or F/N/A2 continuations. Report tokens, time, and cost rather than using them as success thresholds. Record safety-timeout events separately. Report observed success bounds and conditional opportunity rates; the target population is authorized Dev, not the entire benchmark.

Only after establishing actual strong-Agent terminal failures should a new same-active-session independent-replay contrast be proposed. Failures before a complete program exists remain an explicit boundary of the replay mechanism.

### Review Needed

Review historical protocol incompatibility, CLI drift, and ambiguous retry eligibility before approving these experiments. This proposal does not amend the old protocol, authorize treatment Phase 2, or release protected data. No frontier, cross-case memory, checkpoint search, or symbolic constraint framework is added.
