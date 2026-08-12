# EnvSolve-Pro 实验计划 v2

状态：活跃设计；Dev-12 继续受原预注册约束
日期：2026-08-11

## 1. 研究主线

自动仓库部署是一个部分可观测、状态化的约束求解问题。Agent 只能看到当前环境和当前操作暴露出的
失败；它必须推断兼容性要求、改变环境，并交付一段能够从干净 checkout 重建兼容状态的程序。

第一篇论文包含三项贡献：

1. 基于 Observation--Constraint--Operation 三层架构建立因果失败分类，并比较不同 baseline 的
   错误分布。
2. 提出固定且最小的 verifier-guided repair 算法 EnvSolve-Pro：自由搜索、软反例约束和 session 内
   干净重放。
3. 与原生 Codex、Repo2Run、EnvBench Agent 和旧硬约束 EnvSolve 做受控比较，同时报告同模型增益、
   错误分布迁移、Official Pass@1 和成功优先的资源效率。

EnvSolve-Pro 不搜索 harness 设计。跨 case 修改 harness、机制组合搜索、版本晋升和自动回退属于
Auto-EnvSolve；模型训练属于 EnvSolve-RL。

## 2. 部署机制与公共实验底座

我们用四种可以组合的机制描述部署系统，不把系统名称本身当成解释。这些机制描述 deployer 如何推理
和行动，与保证实验有效的公共 harness 严格分开。

| ID | 原语 | 定义 | 典型风险 |
|---|---|---|---|
| F | 自由反馈搜索 | 连续 Agent 根据普通执行反馈，自由选择环境操作。 | 漫游、状态污染、成功不可重现。 |
| C_h | 硬约束部署 | 编码的兼容规则强制、拒绝或改写部署操作或候选。 | 误杀合法修复，压制更强模型。 |
| C_s | 软约束部署 | 将执行证据规范化为可操作义务，但保留原始证据且不限制动作空间。 | 错误归纳可能误导 Agent。 |
| R | 干净重放与恢复 | 在全新环境执行完整候选程序，并把失败返回同一个活跃 session 修复。 | 增加时间、网络和存储成本。 |

所有 arm 共享实验完整性底座 **E**：evaluator 隔离、仓库与目标完整性、结果通道保护、精确脚本绑定和
内容寻址 artifact。E 不推断兼容性，也不选择部署动作，因此既不是部署机制，也不是 EnvSolve-Pro 的
论文贡献。连续 session 权限同样在受控 arm 间保持一致，只是执行条件，不是 treatment。

根据冻结代码和原生轨迹进一步核验以下初步映射：

| 系统 | 机制组成 | 实验角色 |
|---|---|---|
| EnvBench FreeAgent / Raw ReAct | F，终局再蒸馏成功命令 | 原生 API baseline |
| 原生 Codex | 连续 session 和持久构建环境中的强 F | 独立 frontier baseline |
| Repo2Run | F，加修改失败后的局部 checkpoint/rollback | 外部恢复 baseline |
| 旧 EnvSolve | F + 大范围 C_h + 历史重放机制 | 代表性硬约束 baseline |
| goal-aware boundary-v5 | F + 大范围 C_h + session 后 R | 冻结历史 baseline，不代表能力上限 |
| EnvSolve-Pro | F + C_s + session 内 R | 本文方法 |

旧 EnvSolve 的比较属于系统级比较，不能解释成 C_h 的纯因果效应，因为它的 replay 与 policy 实现也
不同。第一篇论文明确不穷举机制排列组合。

## 3. 错误分类

标注单元是最早产生决定性影响的因果失败，而不是报错字符串。每个失败 episode 只有一个主类别，
可以带 secondary tags，并必须关联 artifact 证据。基础设施事故单独删失，不归为算法错误。

### 3.1 观测失败

- 从未观察到必要事实；
- construction 与 clean 环境暴露了不同事实；
- 错认 runtime、架构、依赖管理器或目标身份；
- 把部分或噪声观测当作完整事实。

### 3.2 约束失败

- 遗漏声明的运行时依赖；
- 遗漏传递构建依赖或系统依赖；
- 没有表达版本、runtime、ABI、平台或架构冲突；
- 把榜单目标通过误认为完整可执行部署。

### 3.3 操作失败

- 所选动作无法解除 active constraint；
- 动作顺序或 shell 状态传播错误；
- 最终程序无法重现 construction 成功状态；
- 硬 guard 拒绝了合法修复；
- 通过不完整或不一致的环境满足指标。

### 3.4 跨层闭环失败

- 已观察证据没有转化为 active constraint；
- active constraint 没有影响下一步操作；
- 修复没有在它必须成立的状态中重新验证；
- 表面症状消失，但根约束仍未解决。

taxonomy 只从多个系统已经消费的轨迹中归纳，并在 confirmatory evaluation 前冻结。后续新现象统一
标为 `unresolved`，可以推动下一版 taxonomy，但不能在看到本文结果后修改当前类别。

## 4. EnvSolve-Pro 算法

EnvSolve-Pro 是一个反例驱动的部署修复循环：

```text
P0 <- 连续 Agent 构造可重放 bootstrap 程序
for t = 0, 1, ...:
    Et <- 在精确干净 checkout 和基础环境中执行 Pt
    Vt <- 运行公开可执行目标与最小完整性检查
    if Vt 通过:
        认证 hash(Pt) 并返回 Pt
    ct <- 从 (Et, Vt) 中规范化最早的可操作反例
    把 ct 与有界原始证据返回同一个活跃 Agent session
    Pt+1 <- Agent 自由修复完整程序
```

软反例记录只包含：

- Pass、Fail、Unknown 或 Infrastructure；
- 失败阶段和最早失败操作；
- required condition 与 observed state；
- 有界原始证据和 provenance；
- retryability 与环境 identity。

它只是建议。Agent 始终看到原始证据，可以推翻或修正归纳。算法不包含包规则库、候选图、跨 case
记忆、学习权重、物理 checkpoint frontier 或 harness 自修改。

公共 E 底座只保护 benchmark 完整性：不能把 Official evaluator 反馈放进 loop，不能修改 goal 或
tests，不能伪造结果通道。它对所有 arm 完全相同，不属于算法。它不会仅仅因为部署程序生成配置、编译
tracked source 或采用陌生包策略就拒绝动作。部署完整性作为非计分次要轴报告，不替代 Official 指标。

## 5. 模型与 Provider 规则

### 5.1 同模型 API 比较

除 Codex 外，所有模型方法统一使用：

- OpenRouter 模型：`deepseek/deepseek-v4-pro`；
- 原生接口支持时使用 `xhigh` reasoning effort；
- OpenAI-compatible API：`https://openrouter.ai/api/v1`；
- 不允许 model fallback；
- 在已消费 case smoke 后固定一个 provider endpoint；
- tool-calling 实验设置 `require_parameters=true`。

OpenRouter key 只通过进程环境提供，绝不写入仓库文件、命令参数、artifact、日志或 schedule。每次运行
记录 provider identity 和响应模型元数据。provider 故障只能按冻结规则进行一次语义完全相同的重试。

### 5.2 Codex frontier baseline

Codex 保持原生 CLI 和原生 OpenAI 模型，不使用共享 API backbone。计划使用当前 `gpt-5.6` alias
指向 GPT-5.6 Sol，并采用 CLI 支持的最强 reasoning 设置。首次运行前冻结 CLI 版本、请求模型、可获得
的 resolved model metadata 和 reasoning 设置。Codex 是独立 frontier 参考，不是同模型因果 control。

## 6. 实验阶段

### Stage T：回顾性 taxonomy discovery

- 输入：全部科研有效且已经消费的 Codex、Repo2Run、EnvBench、旧 EnvSolve 和 EnvSolve-Pro 轨迹；
- 输出：taxonomy v1、baseline 机制向量、主因果标签和 unresolved queue；
- 不从这个样本不均衡的回顾性语料声明成功率；
- 按系统与主类别分层确定性抽取 20% 样本独立复标，报告原始分歧、Cohen's kappa 和 adjudication。

### Stage Q：adapter 与测量资格检查

- 使用两个已消费仓库；
- 验证 DeepSeek V4 Pro slug、tool calling、provider 固定、token 统计、密钥脱敏、轨迹保存、干净重放、
  Official 隔离和 Spark 执行；
- 结果不得参与算法选择。

### Stage D1：小型 outcome-independent Dev pilot

- 在任何新 arm 运行前，按标识符确定性哈希冻结 12 个仓库；
- 主配对：DeepSeek V4 Pro 下的 API 自由 Agent F 与 EnvSolve-Pro F+C_s+R；
- 配对随机运行顺序，共享仓库、revision、基础镜像、架构、公开目标和基础设施规则；
- 只诊断 terminal reach、首次 replay 失败、真实 repair activation 和无法解释的 regression，不做 SOTA
  声明。

### Stage D2：定向消融与开发扩展

只有 D1 完整结束并通过完整性门槛后：

- 在运行任何新 arm 前，从冻结 reserve 中仅按 identity 哈希选择新的 16-case Dev batch；
- 在相同 DeepSeek V4 Pro backbone 下，以 case 内随机顺序比较 F、F+R 和 F+C_s+R；
- 在相同 identity 上运行冻结的旧 EnvSolve，作为代表性 F+C_h+R 系统 baseline；
- 用 F+R 减 F 估计 replay 效应，用 F+C_s+R 减 F+R 估计软约束的增量效应；
- EnvSolve-Pro 与旧 EnvSolve 只解释为软约束系统和硬约束系统的比较，不包装成 C_s 对 C_h 的纯因果
  效应。

该设计共 64 个 episode，不搜索其他机制组合。如果 D1 没有出现 feedback-conditioned repair，应在
D2 前收缩算法主张，而不是用更多 case 掩盖机制没有触发。

### Stage C：冻结 Canary 验证

- 冻结实现、prompt、tool schema、model/provider identity、taxonomy 和分析代码；
- 在未触碰的 20-case Canary 上运行 F 对 F+C_s+R 主配对；
- 外部 baseline 只有在 Stage Q 不改变原生语义的前提下才进入；
- 打开 Canary 后不得再修改算法。

### Stage P：protected 与 leaderboard 实验

- 在 protected 100-case split 上运行最终系统；
- protected test 与 development 结果分开报告；
- 所有主张和分析规则冻结后，再运行官方完整 329-case protocol 直接比较榜单；
- Codex GPT-5.6 是原生 frontier 参考，DeepSeek V4 Pro 构成受控同模型矩阵。

## 7. 指标与统计

### 主指标

- 冻结 EnvBench evaluator 下的 Official Pass@1。

### 机制指标

- construction 成功但 clean replay 失败比例；
- 首次 replay 失败比例；
- feedback-conditioned repair rate：同一 session 中先 replay 失败，随后不同程序得到认证并 Official Pass；
- 错误类别分布和配对类别迁移；
- 硬边界假阳性率；
- Official Pass 但部署完整性被标红的比例。

### 资源指标

- wall-clock；
- input、cached input、output 和 reasoning tokens；
- 模型请求数和工具调用数；
- clean replay 次数与时间；
- 能直接测量时记录网络字节、磁盘增长和峰值内存。

Token 和美金价格只是评估指标，不是科研停止阈值。每个 episode 只设置宽松的运行安全 deadline 和
provider 请求保护。优先求解成功；资源 Pareto 比较要么以成功为条件，要么与成功率联合报告。

### 分析

- paired pass-rate difference 和 bootstrap confidence interval；
- 双方都有 Boolean Official 时做 exact McNemar；
- 错误类别 paired transition table；
- 带不确定性区间的类别比例；
- 始终把基础设施删失单独保留的 sensitivity analysis；
- 不补算缺失的资源测量。

## 8. 优化边界

EnvSolve-Pro 开发阶段可以修改：

- 反例规范化字段与证据长度；
- 何时提交完整候选进行 replay；
- replay 证据如何返回同一 session；
- 脚本认证和 exact-hash handoff；
- 资源测量与基础设施分类。

第一篇论文不能修改或优化：

- Official evaluator、benchmark goal、split identity 或 protected data；
- 为了让比较有利而修改 baseline 源码；
- 看到 confirmatory outcome 后修改 taxonomy；
- 模型权重；
- 跨 case 记忆或经验；
- 自动搜索机制组合；
- 自动生成 harness patch、晋升版本或回退版本。

这些被排除的能力构成 Auto-EnvSolve 和 EnvSolve-RL 的研究边界。

## 9. 晋升门槛

Stage D1 只有满足以下条件才能扩展：

1. 每个 arm 使用绑定的 model/provider 和精确 repository revision；
2. Official 输出从未进入活跃 Agent session；
3. 至少一条 treatment 轨迹真实经历 replay 失败并继续修复，或者明确得出机制未触发的结论；
4. 不用基础设施删失掩盖无法解释的 treatment regression；
5. 所有提交程序和 replay 结果都有内容寻址且可复现。

只有方法、taxonomy、analysis code 和 claim 冻结后才能打开 Stage C；只有 Canary 封存且算法未修改，
才能打开 Stage P。

## 10. 当前冻结状态

Stage Q 已在已消费 case 上完成链路资格检查，不进入效果统计。Stage D1 已冻结 12 个仓库和 24 个配对
episode：从 Dev-209 中仅按身份排除 153 个已有运行清单或终局证据的 case，对剩余 56 个使用固定 salt
排序取前 12 个；选择过程不读取内容、结果或错误分类。每个 case 的 F/FSR 先后顺序也由 salt 冻结。

执行依据为：

- `experiments/validations/envsolve_pro_v2_dev12_preregistration.json`；
- `experiments/validations/envsolve_pro_v2_dev12_mechanism_semantics_amendment.json`；
- `experiments/validations/envsolve_pro_v2_dev12_preselection_audit.json`；
- `experiments/cases/dev_envsolve_pro_v2_pilot12.jsonl`；
- `experiments/schedules/envsolve_pro_v2_dev12.json`。

打开首个 episode 后，不再修改算法、prompt、tool schema、模型、provider 或 batch identity。零模型请求的
基础设施故障可以在保留原始证据和预先记录 amendment 后做一次同语义重试。后续发现的 provider
空响应和容器超时进程残留也都保留为 infrastructure-censored 尝试，只允许通过预先记录、与 case 无关
的通用接口修复后重跑。EnvSolve-Pro V2 现已使用独立 registry 与 schedule 入口，旧 baseline 的冻结哈希
保持逐字节不变。

语义 amendment 不改变任何 episode。A 解释为公共 E 下的 F，B 解释为公共 E 下的 F+C_s+R；冻结的
F/FSR run ID 保持不变。预注册中的 minimal-H 标签只是公共实验完整性，不是算法 treatment 或论文贡献。

## 11. 进行中证据

首个冻结配对 `tensorflow/model-analysis` 是双方都失败：A-F 与 B-FSR 均用完 120 次请求且没有提交
bootstrap，因此 Official Pass@1 都计为 false。B-FSR 的 clean replay 调用数为 0，所以该配对暴露的是
候选形成失败，不能估计 replay 反馈在真正激活后的效果。不可变结果记录为
`experiments/validations/envsolve_pro_v2_dev12_pair01_result.json`。

单个配对不支持任何成功率主张。它提出了一个需要由完整 Dev-12 回答的问题：候选形成过晚或完全缺失
是否是跨 case 的主要矛盾，还是这个异常困难的 ARM 依赖闭包所特有。

第二个冻结配对 `rcmdnk/homebrew-file` 是双方都通过。B-FSR 真实激活了目标机制：首次 clean replay
暴露 6 个缺失导入，同一 session 修改程序，之后两个 replay 均通过，再按精确脚本提交。A-F 也通过
Official。描述性地看，B 使用 31 对 56 次模型请求、557,816 对 2,325,002 tokens、43 对 88 次 shell
调用，生成耗时约 461 对 1,600 秒。一个配对只能作为机制证据，不能据此声称期望资源开销下降。B 首次
session 外 Official 评测因网络失败被删失，随后仅按预登记规则对同一脚本做了一次重试，没有重新调用
模型。不可变记录为 `experiments/validations/envsolve_pro_v2_dev12_pair02_result.json`。

前两个配对汇总后，两个 arm 的 Official Pass@1 都是 1/2。目前证据支持机制可行性，但不支持成功率
或效率增益主张。其余冻结配对需要回答：候选形成是否是主要失败，以及反馈驱动修复能否产生可重复优势。

第三个冻结配对 `nabla-ntnu/nablaweb` 也是双方都通过，并提供了第二条、更完整的机制激活轨迹。A-F
在第 55 次请求提交并通过。B-FSR 在第 19 次请求首次 replay：本地可用的 Pipenv 隔离了依赖，trusted
evaluator 看不到它们，因此产生 806 个缺失导入。第二版程序在解析锁文件时异常退出，尚未进入验证；
第三版把锁定依赖装入 evaluator 可见的 Python，通过 clean replay，并在第 46 次请求通过 Official。
本配对中 B 约少用 30% tokens、34% 生成时间和 44% shell 调用。不可变记录为
`experiments/validations/envsolve_pro_v2_dev12_pair03_result.json`。

前三个配对汇总后，两个 arm 的 Official Pass@1 都是 2/3。B 已有两条 feedback-conditioned repair，
但尚无成功率优势。无条件资源结果也没有两个成功激活案例那么漂亮：B 使用 197 对 231 次模型请求、
288 对 307 次 shell，但 tokens 为 11.061M 对 11.044M，生成时间为 8,606 对 8,209 秒。首个配对的
候选形成失败抵消了条件效率收益。这反而强化了尚待验证的假设：系统必须足够早地产生“下一个不确定
但完整的候选”，replay 才有机会发挥作用。

第四个冻结配对 `wpi-lnl/lnldb` 不能产生配对 Official 效应。A-F 在第 71 次请求形成程序。第一次
Official 适配器启动因为宿主 PATH 中缺少 `uv` 被基础设施删失；按事前规则进行的唯一一次 exact-script
retry 又在下载公开的 Python 3.7.7 源码时发生 TLS EOF，Pyright 尚未执行。重试额度已经耗尽，因此不为
A 推断 pass/fail。B-FSR 到冻结的 120 次请求安全上限仍未提出程序，clean replay 调用为 0，属于算法
失败。B 使用 6.986M tokens、146 次 shell 调用，A 分别为 2.852M 和 110。该配对不能估计通过率差异，
但给出了很强的失败机制证据：如果 Agent 把“本地完整依赖闭包”当成形成程序的前置条件，仅仅提供
replay 接口并不足以让 replay 进入控制回路。不可变记录为
`experiments/validations/envsolve_pro_v2_dev12_pair04_result.json`。

四个已尝试配对中有三个具备双臂可观测的 Official 结果，在这三个配对上两臂仍均为 2/3。第四对只进入
轨迹与资源分析，不进入配对 Official 分母。冻结 Dev-12 内不会根据该 case 修改算法。

第五个冻结配对 `pypa/twine` 是双方都通过。A-F 在第 18 次请求首次观察到本地
`reportMissingImports` 为零，但随后重复进行本地检查，直到第 49 次才提交。B-FSR 在第 11 次请求首次
观察到本地目标通过，第 16 次把完整程序送入干净重放，首次新环境验证即通过，并在第 17 次请求提交。
B 使用 17 对 49 次模型请求、244,539 对 1,153,043 tokens、25 对 72 次 shell 调用，生成耗时约
222 对 696 秒。这支持“干净重放可以充当明确的认证与停止信号”，但不属于 feedback-conditioned
repair，因为首次 replay 已经通过；一个配对也不能建立期望效率增益。B 的第一次 session 外 Official
评测在获取仓库时被基础设施删失，同一脚本随后在唯一一次审计重试中通过，模型没有重新运行。不可变记录
为 `experiments/validations/envsolve_pro_v2_dev12_pair05_result.json`。

五个已尝试配对中有四个具备双臂可观测的 Official 结果，在这些配对上两臂均为 3/4。B 目前有两条
feedback-conditioned repair 和一条首次 replay 认证，但仍没有通过率优势。必须继续完成剩余七个冻结
配对，才能判断 replay 的主要增益究竟是修复、停止、两者兼有，还是总体上都不稳定。

第六个冻结配对 `quantumjot/btrack` 是双方都通过，并把终止策略问题刻画得更清楚。B-FSR 在第 16 次
请求首次达到本地目标，但直到第 40 次才形成可 replay 的完整程序；首次 clean replay 通过，第 41 次
请求随即提交。A-F 在第 24 次请求首次达到本地目标，到第 56 次才提交。中间两臂都在追求不计分的
运行时完整性，包括 Pydantic、NumPy、Napari、Qt、Eigen 和原生 tracker 库。B 使用 41 对 56 次模型
请求、0.981M 对 2.302M tokens，生成耗时约 861 对 1,774 秒。A 生成了 Eigen 和 ARM 兼容的原生库，
B 只安装 Python 依赖表面；这是部署路径差异，不能证明 A 已实现完整复现，也不能证明 B 在 Official
目标之外更优。A 的首次 Official 在下载公开包时被网络删失，同一脚本在唯一一次审计重试中通过，模型
没有重新运行。不可变记录为 `experiments/validations/envsolve_pro_v2_dev12_pair06_result.json`。

六个已尝试配对中有五个具备双臂可观测的 Official 结果，在这些配对上两臂均为 4/5。B 目前有两条
feedback-conditioned repair 和两条首次 replay 认证。第五、六对都显示 clean replay 一旦成功，Agent
会立即提交；但第六对也说明当前接口并不能促使 Agent 尽早提出完整候选：B 从首次本地目标通过到首次
replay 相隔 24 次请求。因此正在浮现的算法问题不再是 replay 能否验证候选，而是如何在 Agent 继续
探索可选完整性时保留一个已经足够好的候选，同时不把次要质量目标变成新的硬门槛。
