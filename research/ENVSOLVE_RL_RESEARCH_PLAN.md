# EnvSolve-RL Research Plan / EnvSolve-RL 研究计划

Status / 状态：独立后续项目，当前不属于 EnvSolve 的论文 claim、方法或实验。

## 中文版

### 1. 核心问题

EnvSolve-RL 研究：能否利用大量可执行部署轨迹，学习一个比固定 LLM policy 更有效的
constraint-to-action policy，并在严格的跨仓库划分和预算约束下泛化到未见项目？

它不研究如何重新定义 verifier，也不把 EnvSolve 的规则包装成 RL。前置条件是 EnvSolve 已经产生
稳定、可审计的状态、操作和结果接口，并且数据规模足以支持学习。

### 2. 从 EnvSolve 继承什么

冻结并复用：

- 不可变 observation 与 provenance；
- typed constraint state；
- `OperationPlan` 与合法 action space；
- fresh-environment verifier；
- 统一的 candidate、token、environment、wall-time 和 cost ledger；
- terminal-only official evaluation 规则。

可以学习：

- 给定约束状态时的 operation kind 选择；
- 具体 operation 参数和完整部署程序生成；
- 在剩余预算下继续、停止或探索的策略；
- 对 hypothesis 的风险敏感排序。

不得学习或读取：

- Official-Test case 的在线 evaluator feedback；
- 同一 evaluation case 的官方结果；
- 违反环境边界的源码修复；
- train/evaluation 之间的仓库身份泄漏。

### 3. 最小数据单元

每个 transition 至少包含：

```text
repository split and revision
state before action
source constraints and hypotheses
operation requirements
candidate action/program
guard decision
fresh-environment observation
verifier outcome
resource cost
termination reason
```

Raw event 永远不可修改。Reward、advantage、failure cluster 和训练样本都是独立版本化的 derived view。

### 4. 暂定研究假设

1. Typed state-action trajectories 比 raw terminal-history trajectories 更具样本效率。
2. 在相同 backbone 和总预算下，学习后的 policy 能提高 unseen-repository success-cost frontier。
3. Provenance、Unknown censoring 和合法 action mask 能减少错误 credit assignment。

### 5. 必要实验

- 固定 EnvSolve 与 EnvSolve-RL 的 verifier、action space、信息和评测权限；
- 按 repository identity 做严格 train/dev/test 切分；
- 比较 imitation learning、offline RL、online RL 和无训练 EnvSolve；
- 消融 typed state、provenance、Unknown mask、operation mask 与 cost-aware objective；
- 报告 Official Pass@1、success-cost frontier、OOD 泛化和 invalid-action rate；
- 检查训练数据规模曲线，证明收益不是简单来自更多推理计算。

### 6. 启动门槛

只有满足以下条件才启动正式研究：EnvSolve 的核心算法和 evaluator 冻结；轨迹 schema 稳定；具有足够
数量的跨仓库有效 transition；数据泄漏审计通过；固定 policy baseline 已经建立。否则只收集数据，
不提前声称 RL 是有效方向。

### 7. 版本化轨迹契约与最终系统

每个 transition 必须额外绑定 `harness_version`、`policy_version`、前后状态哈希、candidate lineage、
constraint delta、effect-audit 结果和 termination provenance。Official evaluator 只形成 episode 结束后的
独立标签，不能混入在线 state。这样同一条 raw trajectory 可以派生 imitation、offline RL、reward model
和 failure-census view，而不重写原始事实。

EnvSolve-RL 与 Auto-EnvSolve 的职责不能混淆：前者学习在一个冻结 harness 内如何从约束状态选择操作；
后者决定何时以及如何发布新的 harness 版本。最终的自进化环境对齐系统可以交替进行版本化 harness
改进和 policy 训练，但在正式 held-out episode 中两者都保持冻结。当前 EnvSolve-Pro 实验应持续积累
这种可复用数据，而不是只保留最终 pass/fail。

P4 还给出新的数据要求：transition 不能只保存平铺 module constraint，而要保存 root-cause edge、scope、
trust level、platform identity 和 surface-to-root amplification；effect-audit 误杀、verifier 被绕过和网络删失
必须是不同标签。Reward 以最终成功为词典序第一目标，token、候选数和时间只作为同成功条件下的次级
信号；不能把当前会删失搜索的 5-candidate 上限学习成“正确停止”。

P5 将这份要求落成可执行 transition view：每个 action 保存操作前后的 causal frontier、各观测通道的
scope、根因首次出现、复发与闭合，以及完整 raw evidence 的哈希引用。Policy 输入可以使用前沿，但动作
仍是开放部署程序；因此后续可以比较 raw-history policy、flat-state policy 和 frontier-conditioned policy，
而不会把收益混同为更小的动作空间。训练标签必须区分“根因被后续同通道观测证明闭合”和“后续候选
未运行到该探针”；后者是删失，不是正 reward。

## English Version

### 1. Core question

EnvSolve-RL asks whether executable deployment trajectories can train a
constraint-to-action policy that improves unseen-repository deployment under fixed
information and total budgets. It is a separate project, not an extension of the
current EnvSolve claim.

### 2. Inherited and learnable components

The immutable observation/provenance layer, typed constraint state, operation
schema, fresh verifier, budget ledger, and terminal-only evaluation protocol remain
frozen. The policy may learn operation selection, concrete parameters, complete
program generation, budget-aware stopping, and hypothesis ranking. It may not use
official online feedback, evaluation-case leakage, or source-edit repairs.

### 3. Data and evaluation contract

Training examples preserve the complete state-constraint-action-guard-observation-
outcome-cost chain. Raw events are immutable; rewards and training views are
versioned derivatives. Experiments require repository-disjoint splits, matched
budgets, fixed verifier access, comparisons with imitation and RL alternatives, and
ablations of typed state, provenance, censoring, action masks, and cost objectives.

### 4. Start criterion

Formal work starts only after EnvSolve and its trajectory schema are stable, enough
cross-repository transitions exist, leakage audits pass, and a fixed-policy baseline
is available.

### 5. Versioned trajectory contract and final system

Every transition additionally binds the harness and policy versions, before/after
state hashes, candidate lineage, constraint deltas, effect-audit outcomes, and
termination provenance. Official evaluation is a separate post-episode label and
never part of the online state. EnvSolve-RL learns actions within a frozen harness;
Auto-EnvSolve governs evidence-based harness version changes. A future self-evolving
alignment system may alternate these two processes, while freezing both during
held-out evaluation. EnvSolve-Pro should therefore retain reusable transitions, not
only terminal pass/fail labels.

P4 adds concrete schema requirements: transitions must preserve root-cause edges,
scope, trust level, platform identity, and surface-to-root amplification rather than a
flat module list. Effect-audit false positives, verifier manipulation, and network
censoring require distinct labels. Reward is lexicographic with final success first;
tokens, candidates, and time are secondary among equally successful outcomes, and a
binding candidate cap must not be learned as a correct stopping signal.

P5 makes this requirement executable: every action transition stores the causal frontier
before and after the action, observation-channel scopes, first appearance, recurrence,
closure, and hashes of the complete raw evidence. The policy may condition on the
frontier, but still emits an open deployment program, allowing raw-history, flat-state,
and frontier-conditioned policies to be compared without an action-space confound. A
root is a positive closure label only when a newer observation from the same channel
retires it; failure to reach that probe is censoring, not reward.
