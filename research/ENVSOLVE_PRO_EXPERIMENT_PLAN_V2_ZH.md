# EnvSolve-Pro 实验计划 v2

状态：Minimal B 已选定；taxonomy v2 已审计；定向 Bad4 实验已设计
日期：2026-08-30

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

### 2026-08-19 算法选择修正

预注册的定时观测资格实验已完成 16 条有效 episode。B-FSR 与 E-SCHEDULED 都是 8/8 Official Pass。
机制本身稳定执行，但没有 treatment 独占成功，也没有预注册效率信号。因此固定 cadence 被冻结为负候选，
不作为 EnvSolve-Pro treatment；不再调 cadence，也不为该候选打开冻结 Dev identity。下一个方法假设必须
针对既有固定 baseline bad-case 语料中的决定性失败，并在运行新 treatment 前写清楚。

### 2026-08-20 算法选择结论

固定 bad-case profile 表明，旧 replay 臂继承了构建 package cache，会认证在冷 Official 中失败的程序。
当前选择最小形式的 F + C_s + R：同一个自由 Agent 提交完整程序；R 在不使用构建缓存的目标初始状态中
执行；失败在同一 session 中成为 case-local 软反例 C_s。定时观测、增量 ledger、checkpoint、跨 case
规则和新的硬约束全部排除。

三个已消费 case 的预注册机制检查通过激活与保真问题：2/3 case 在 session 内修复失败重放，三个最终
重放全部与 Official 一致且全部通过。随后四对 outcome-independent 开发 case 中，F 的 Official 为
2/4，F+C_s+R 为 3/4，包含一次反馈修复和一次 treatment 候选形成失败。这只批准保持 treatment 不变并
扩大开发集实验，不能估计效果。

保持 treatment 不变的扩展现已在 Dev16 最后四个固定位完成。两臂都是 4/4；三条 treatment 首次 replay
通过，`pygeo` 修复一次网络获取 timeout 后通过。treatment 资源总量更低，但配对中位数没有显示一般性的
请求或时间收益。合并 outcome-independent 证据为 F 6/8、F+C_s+R 7/8，只有一对 discordant
（`p=1.0`）。随机 Dev 扩展到此停止；下一组必须从既有 census 中预先固定强 baseline Official failure
分层，且不能使用 treatment 结果选样。

### 2026-08-30 收敛更新

更大的定时观测、强制 handoff、current-goal 和 compatibility-ledger treatment 均未获得晋级证据。固定
方法为 Minimal B：一个不受限的连续 session，加 Agent 可反复调用的目标状态 replay，并要求原样交付
程序通过 replay。Taxonomy v2 将方法机制（`F`、`C_h`、`C_s`、`R`）与唯一最早 O/C/O 主因、删失状态
和路径质量分开。205 个 Dev identity 已全部消费；下一组四 case 配对实验是完整的“当前 treatment 未运行
历史失败层”，不是未见评估。受保护 Canary 和 Official Test 继续承担泛化验证。

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
- 把榜单目标通过误认为完整可执行部署；
- 错误的准入或成功规则拒绝合法修复，或把不完整状态认作完整状态。

### 3.3 操作失败

- 所选动作无法解除 active constraint；
- 动作顺序或 shell 状态传播错误；
- 最终程序无法重现 construction 成功状态；
- 在正确的完整性要求已经表示后，所选动作仍通过不完整或不一致的环境满足指标。

两层以证据区分：错误的要求属于约束失败；只有正确要求已经 active、状态变换仍然无效时，才属于操作失败。

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

除 Codex 外，所有新模型实验统一使用：

- OpenRouter 固定模型：`deepseek/deepseek-v4-flash-0731`；
- 原生接口支持时使用 `xhigh` reasoning effort；
- OpenAI-compatible API：`https://openrouter.ai/api/v1`；
- 不允许 model fallback；
- 在已消费 case smoke 后固定一个 provider endpoint；
- tool-calling 实验设置 `require_parameters=true`。

OpenRouter key 只通过进程环境提供，绝不写入仓库文件、命令参数、artifact、日志或 schedule。每次运行
记录 provider identity 和响应模型元数据。provider 故障只能按冻结规则进行一次语义完全相同的重试。

此前 `deepseek/deepseek-v4-pro` Dev-12 保留为冻结的历史 pilot，不与 Flash 结果合并。实验不使用会
漂移的 `flash-latest` alias。Flash 0731 已在已消费 case 上通过资格检查，覆盖 tool calling、53-request
连续 session、clean-replay 反馈修复、精确 hash 提交和 Official evaluation。

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
- 验证固定 DeepSeek V4 Flash 0731 slug、tool calling、provider 固定、token 统计、密钥脱敏、轨迹保存、
  干净重放、Official 隔离和 Spark 执行；
- 结果不得参与算法选择。

### Stage M：已消费 case 的机制选择

- 可选观测 pilot 否定了由 Agent 自愿调用工具是一种稳定机制；
- 确定性观测实验实现 34/34 完整观测、8/8 treatment 调度合规，但两臂均 8/8 Official Pass，效率条件
  为 false；
- 决策：不晋级、不调整定时观测，只把它保留为观测基础设施和负 treatment 结果；
- 下一输入：冻结 baseline bad-case census，按最早决定性的观测层、约束层、操作层失败分析，而不是按
  最后一条错误字符串选 case。

### Stage D1：小型 outcome-independent Dev pilot

- 在任何新 arm 运行前，按标识符确定性哈希冻结 12 个仓库；
- 已完成的 V4 Pro 配对只作为历史机制 pilot，不与新模型合并；
- 新主配对：固定 DeepSeek V4 Flash 0731 下的 API 自由 Agent F 与 EnvSolve-Pro F+C_s+R；
- 配对随机运行顺序，共享仓库、revision、基础镜像、架构、公开目标和基础设施规则；
- 只诊断 terminal reach、首次 replay 失败、真实 repair activation 和无法解释的 regression，不做 SOTA
  声明。

### Stage D2：定向消融与开发扩展

只有 D1 完整结束并通过完整性门槛后：

- 在运行任何 Flash arm 前，从已用于 taxonomy 的 reserve 中仅按 identity 哈希选择 16-case Dev
  batch；这些 case 对 Flash treatment 未运行，但不是仓库级未见；
- 在相同固定 DeepSeek V4 Flash 0731 backbone 下，以 case 内随机顺序比较 F、F+R 和 F+C_s+R；
- 在相同 identity 上运行冻结的旧 EnvSolve，作为代表性 F+C_h+R 系统 baseline；所有 API arm 使用
  相同 Flash 0731 快照；
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
- Codex GPT-5.6 是原生 frontier 参考，固定 DeepSeek V4 Flash 0731 构成受控同模型矩阵。

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

第七个冻结配对 `has2k1/plotnine` 给出了目前最强的修复轨迹，但不能产生配对 Official 效应。A-F 在
第 42 次请求达到整个仓库的本地目标，第 68 次提交；原始 Official 和唯一一次 exact-script retry 都在
pip 从 GitHub 克隆公开 `qrenderer` 依赖时发生 TLS 截断，Pyright 尚未运行，因此 A 仍按基础设施删失，
不推断 pass/fail。B-FSR 在第 52 次请求开始 replay。前三个候选分别没有把控制权交回目标、暴露 34 个
evaluator 可见的缺失导入、以及遭遇同类 Git TLS 失败；同一 session 随后把 Git clone 换成 tarball，
第 4、5 次 replay 通过，精确程序最终通过 Official。B 使用 73 对 68 次模型请求、3.174M 对 1.973M
tokens、100 对 66 次 shell 调用，生成耗时约 4,984 对 3,093 秒。这证明 feedback-conditioned repair，
不证明通过率或效率提升。不可变记录为
`experiments/validations/envsolve_pro_v2_dev12_pair07_result.json`。

七个已尝试配对中仍只有五个具备双臂可观测的 Official 结果，在这些配对上两臂均为 4/5。B 目前有
三条 feedback-conditioned repair 和两条首次 replay 认证；另外两对保留有价值的轨迹，但因为 A 用完
预登记的基础设施重试而不能估计配对效应。第七对还暴露了下个实验必须事前冻结的协议边界：依赖下载失败
若在活跃 session 内被修复，可以体现部署能力；相同故障若发生在 session 结束后，当前规则却会将其删失。
Dev-12 不做事后修改，剩余五对继续沿用冻结规则。

第八个冻结配对 `mov-cli/mov-cli` 是双方都通过，并在简单依赖闭包上隔离出“认证驱动终止”。B-FSR 在
第 12 次请求达到本地零 missing imports，第 14 次首次 clean replay 通过，第 15 次提交。A-F 在第 13 次
首次达到相同目标，之后又重复检查 8 次，到第 43 次才提交。两份最终程序都安装 editable 项目以及
`fastapi`、`mov-cli-youtube`；B 还安装了 verifier 侧便利包。B 使用 15 对 43 次模型请求、158,559 对
1,007,718 tokens、21 对 69 次 shell 调用，生成耗时约 172 对 1,963 秒。双方均通过 Official，且非计分
error count 相同。不可变记录为
`experiments/validations/envsolve_pro_v2_dev12_pair08_result.json`。

八个已尝试配对中有六个具备双臂可观测的 Official 结果，在这些配对上两臂均为 5/6。B 目前有三条
feedback-conditioned repair 和三条首次 replay 认证。第五、六、八对独立显示 clean replay 一旦成功就
会立即提交；第八对的最终依赖策略近似，因此最清楚地把资源差异归因于终止行为。这仍不建立期望效率
增益：第七对说明修复可能很昂贵，同时还有两次候选形成失败。剩余四个冻结配对尚未运行。

## 12. 目标状态重放机制检查与资格实验

### 12.1 已消费机制结果

正式效果实验前，我们在 basxconnect、Graphium 和 cvxportfolio 上检查了隔离缓存后的目标状态实现。
三个 case 的 replay 与 Official 全部一致。basxconnect 在 Git ownership 反例后修改程序；Graphium 在
无效 wheel 版本、Git ownership 和遗漏测试依赖反例后修改程序，另有一次网络获取失败，随后通过；
cvxportfolio 第一次 replay 通过。结果记录在
`experiments/validations/envsolve_pro_v2_target_state_replay_mechanism_v1_result.json`。

### 12.2 Qualification 结果

资格实验在四个与新 treatment 结果无关的 case 上比较两臂：

- **F control：** 一个使用普通构建反馈的连续自由 Agent session；
- **F+C_s+R treatment：** 相同 session 和权限，加上可反复调用的目标状态完整程序重放。

两臂匹配 Provider、模型、host、镜像、prompt 内容、源码权限、evaluator 和宽松安全上限。F 通过 2/4，
F+C_s+R 通过 3/4。`importlib_metadata` 产生 Fail-Fail-Pass 修复；probatus 产生首次重放即通过的 B-only
结果；cellrank B 在形成候选前失败。法证纠正把原 cellrank B 从基础设施删失改判为研究者中断。主分析
使用预先规定的 replacement，必要敏感性分析排除整个 pair。

该结果只满足扩大开发证据的晋级条件。treatment 的总时间和 Token 更高，四对 case 不能估计真实效果。
完整记录位于
`experiments/validations/envsolve_pro_v2_target_state_replay_qualification_v1_result.json`。

### 12.3 固定开发扩展结果

已有随机 Dev16 顺序最后四位得到 4/4 对 4/4 的 ceiling tie。四条 B 候选全部通过 Official，并与最终
replay 一致；rstcheck、plasmapy 和 starsim 首次 replay 通过；`pygeo` 在 package 下载 timeout 后修改
完整程序并于第二次 replay 通过，属于网络鲁棒性修复，不是兼容性修复。

B 的请求、Token、命令和生成时间总量更低，但配对中位数没有显示典型请求或时间增益，总量差异由
`pygeo` 主导。qualification 与 expansion 合并后，F 为 6/8，F+C_s+R 为 7/8，精确 McNemar 为
`p=1.0`。不可变结果位于
`experiments/validations/envsolve_pro_v2_target_state_replay_development_v2_result.json`。

### 12.4 下一组效果实验

算法保持不变。当前机制大多只是认证首次通过程序，不再用随机 Dev batch 消耗样本。下一组从既有跨方法
census 中定义固定分层：强匹配 baseline 已到达 Official evaluation，并因算法性而非基础设施原因失败。
选样不能使用本文 treatment 的任何结果；执行前预注册 case identity、baseline 证据、失败分层、抽样规则
和所有排除项。这才是第一组能检验“自由搜索确实有提升空间时，目标状态反例能否提高成功率”的实验。

## 13. Bad-6 结果与下一实验

Bad-6 已完成。端到端 Official Pass@1 为 F `2/6`、F+C_s+R `4/6`，配对 discordance 全部朝向
treatment，但 exact McNemar `p=0.5`。候选形成率两组均为 `4/6`；B 的 4 个候选全部重放，最终与
Official `4/4` 一致。HARK 给出目标状态反例导致 B-only Pass 的干净因果链，HA-Battery-Notes 给出双方
都通过时的修复链。micropy-cli 的 B-only Pass 同时带有未跟踪兼容 shim，主 Official 标签保持 Pass，
路径质量单独标红。

资源没有改善：B 比 A 多用 5.8% Token 和 10.4% 端到端时间。失败分析把下一实验从“再加重放 case”
改为“候选交付 treatment”：当公开目标首次可执行通过时，系统保存候选并立即允许目标状态重放；Agent
可以继续探索完整性，但不能丢失已保存候选。该机制不添加 package 规则、跨 case 记忆、checkpoint 或
hard gate。

代码审计发现，这个最小机制已经以 certified-incumbent runner 存在：它只保存 clean replay 通过的
bootstrap 及证书，具备确定性的 fallback 测试，也完成过 3 个已消费 case 的实现资格检查；但那组实验
没有建立它相对 soft replay 的效果。因此下一实验前不再增加算法代码。

前瞻比较改为在预先存在的 `dev_envsolve_pro_v2_flash0731_remaining28.jsonl` 顺序前 8 个 identity 上做
B-FSR 对 C-GCI。当前审计确认 28 个 identity 在本地 terminal validation 记录和 Spark run manifest 中
均无命中。8 个 pair 内模型、provider、seed 相同，arm 顺序交替，唯一差异是 certified incumbent 的
保留与 fallback。主分析把科学上有效但未提交的 episode 计为部署失败；完整性、路径质量和资源继续单独
评价。设计记录在
`experiments/validations/envsolve_pro_v2_certified_incumbent_untouched8_v1_preregistration.json`。
Bad-6 只用于诊断，不能再次承担新 treatment 的效果验证。

## 14. Certified-Incumbent 结果与交接假设

原调度全部执行完成，但历史 registry 审计在最后三对执行前修正了 claim scope。主分析包含 6 对
prospective case；Futaba 作为已消费描述性证据；revision 不可获取的 Flask-Security 记源码获取删失。
看到结果后没有选择 replacement。

B-FSR 为 `6/6`，bundled C-GCI 为 `5/6`，唯一 discordant pair 是 qibolab，方向有利于 B。
C 没有一次 incumbent fallback。即便只看 5 对共同成功 case，C 仍多用 21.4% Token 和 19.9%
生成时间。因此否决该 treatment 作为 EnvSolve-Pro 核心算法，不在这些 case 上继续调参。

Qibolab 精确定位了下一处矛盾。C 在第 93 次请求得到完整根目录的公开目标 Pass，却继续做可选环境工作，
直到第 120 次请求触发安全上限仍没有提出程序。Incumbent retention 只能在 replay 之后开始，因此无法
解决候选不交付；prompt 引导不是可执行 trigger。

下一候选只改变三层之间的交接：

1. **观测层：** 在活跃构建状态中识别可信完整目标 Pass。
2. **约束层：** 把当前状态标记为足以立即交付程序，完整性和成本仍是可选质量目标。
3. **操作层：** 在进一步可选探索前，让同一活跃 session 汇总累计 bootstrap 并调用 clean replay。
4. Replay 失败则返回反例并恢复自由修复；replay 通过则以认证程序终止。

这是验证器触发的程序化，不是 package 规则或动作过滤。搜索和修复时操作空间仍然自由。打开下一组
prospective case 前，先在已消费轨迹和确定性测试上验证 trigger 识别、单次阶段转换、反例回传和通过后
终止，再预注册一组新的固定 development comparison 与 B-FSR 比较。

完整结果：
`experiments/validations/envsolve_pro_v2_certified_incumbent_untouched8_v1_result.json`。

## 15. 否决 Handoff 与 Replay Obligation Ledger

完整三 case bad-set 配对否决 verifier-triggered handoff 作为主要成功机制。定时观测 control 与
handoff 的 Official Pass@1 分别为 `3/3`、`2/3`；协议合规成功为 `2/3`、`1/3`，且没有
treatment-only Pass。PlatformIO 只提供一条成功条件下的效率信号，不是成功率增益。Runner 0.6.3
面向未来修复重复 cwd 观测缺陷，并加入共享、窄范围的 import-provider 完整性边界；两者都不改写冻结
结果。

下一候选是 **Replay Obligation Ledger（ROL，重放待办表）**。通俗地说，每次 clean replay 失败，
系统都把“当前完整部署程序还必须满足什么”加入 case 内待办表。后续局部观测可以增加证据，但不能随意
删除旧待办；只有完整 replay finding set 或 replay Pass 才能消掉它。活跃 Agent 会看到当前待办及其
变化，但每个修复操作仍由 Agent 自由决定。

三层结构保持最小：

1. **观测层：** 把一次真实 replay 投影为完整 Pass、完整目标失败、局部 bootstrap/完整性失败或
   Unknown，同时保留可执行证据。
2. **约束层：** 在部分可观测条件下跨候选保留未解决结构约束；完整证据替换当前可见集合，Pass 清空。
3. **操作层：** 把 active obligations 返回同一 session，不选 package、不筛命令、不恢复 checkpoint、
   不强迫提交。

ROL 作为固定 Base B 上的单一正交 treatment：连续 Agent session、从项目根执行的定时目标观测，以及
可反复调用的 clean replay。Control 获得现有 normalized replay evidence；treatment 额外获得状态化
active-obligation list，以及 introduced/resolved/preserved delta。Prompt、工具、模型、provider、镜像、
源码权限、evaluator 和宽松安全上限其余完全匹配。

确定性测试和已消费 case 只能验证提取与保守更新语义。回顾性曝光审计在 209 个 census case 中为
207 个找到了执行证据，因此不能再把另一个开发 batch 重新标成“未见”。首轮真实 ROL 对照明确是
**已消费的机制开发 batch**，且选择不使用任何 ROL 结果：PlatformIO 检验局部证据到完整证据的
状态转换，qibolab 检验依赖版本冲突，HARK 检验 construction 与 target 环境之间的操作差异。选择记录为
`experiments/validations/envsolve_pro_rol_v1_consumed_mechanism_selection.json`。

Official Pass@1 仍是端到端指标；请求数、Token、时间、流量、replay 次数和 obligation transition 是
诊断性结果。这个三 case 对照可以判断 ROL 是否改变轨迹，但不能估计泛化或总体成功率。
`fonttools/fontbakery` 与 `vertica/verticapy` 是仅剩两个没有发现执行证据的 case，在机制和分析策略固定前
保持未打开。两个 case 也只能作为确认性检查；排行榜与 SOTA 结论必须依赖官方隐藏测试集或新收集的
外部样本。机制固定后，强弱 backbone 使用完全相同算法，用于检验状态化可执行记忆是否补充模型能力，
而不是定义两套方法。

首轮 ROL 对照统一使用 DeepSeek 官方直连接口和正式模型 ID `deepseek-v4-flash`；官方将其
底层版本标为 `DeepSeek-V4-Flash-0731`。Control 与 treatment 使用相同 endpoint、思考模式、
reasoning effort 和请求上限。Direct API 未声明支持 seed，因此预注册 seed 只保留为 episode
身份，不在任一臂转发。此次 provider 迁移不改变 prompt、tool、replay、ledger、evaluator 或
case 选择机制。

## 16. 当前最小三臂实验

ROL 和已否决的 handoff treatment 只保留为已消费开发证据，不进入第一篇论文的核心方法。当前方法选择
实验只隔离三个接口：

1. `F`：连续自由搜索与仓库反馈；
2. `F+O`：相同接口增加完整可执行公开目标；
3. `F+O+R`：相同 goal-aware session 增加可反复调用、从目标初始状态执行的完整程序重放。

固定的已消费 6-case batch 覆盖历史 Observation、Constraint、Operation 失败。它只能提供机制诊断，
不能估计 held-out 泛化或排行榜表现。Official Pass@1 是主指标；replay 激活、首次 replay 认证、
Fail-to-Pass 修复、反例后的程序变化、replay/Official 一致性，以及共同成功 pair 上的资源共同解释结果，
但不改写结果定义。

开跑前，失效的官方凭据要求三组统一迁移 provider。所有 arm 改用 OpenRouter 模型
`deepseek/deepseek-v4-flash-0731`，固定 DeepInfra、转发 seed、禁止 provider fallback。Case、算法、
prompt、tool、evaluator 和分析规则均不改变。设计与 amendment 分别记录在
`experiments/validations/envsolve_pro_for_v1_consumed6_design.json` 和
`experiments/validations/envsolve_pro_for_v1_provider_amendment.json`。

## 17. 固定 Bad4 结果与下一算法门槛

四对有效 Bad4 比较已经完成。Goal-aware 自由搜索（`F+O`）与 Minimal B（`F+O+R`）的 Official
Pass 都是 `2/4`：Pysnmp 和 OpenQASM 两组都通过，Meerkat 和 Stopstalk 两组都失败。两个失败的
treatment 均没有调用 replay。这个结果否决了“完整程序 replay 足以解决当前 hard stratum”，并把下一
问题定位到候选形成之前。

Pysnmp treatment 前两次 replay Unknown，是因为导入来源审计在 Python 3.9.7 下调用了 Python 3.10
才有的 metadata API。Agent 改用 Python 3.11 后 replay 和 Official 通过。审计兼容缺陷已在 `f923d7e`
修复；Official 终局有效，但 replay 修复归因、资源比较和 Python 版本忠实度均标记为受混杂。OpenQASM
treatment 用更少资源达到 Official 目标，却安装了更不完整的环境，因此部署完整性与 Official 效率继续
作为独立评价轴。

Minimal B 现在是 baseline 和认证原语。实现下一算法前，先对四个 pair 做回顾性状态转换分析：找出最后
一个可复现环境状态、第一条未解除约束，以及阻止或促成合法 bootstrap 的操作。后续方法可以向同一个
活跃 Agent 暴露可执行中间状态，但除非重复因果失败明确要求，不加入 package 特定规则、固定动作选择、
新的跨候选 ledger 或 controller handoff。完成分析后，才固定 treatment 和比较 batch。

证据：

- `research/ENVSOLVE_PRO_MINIMAL_B_BAD4_RESULTS_ZH.md`
- `experiments/schedules/envsolve_pro_v2_minimal_b_bad4_v1_effective.json`
- `experiments/validations/envsolve_pro_v2_minimal_b_bad4_v1_result.json`

## 18. 增量可执行程序候选

Bad4 状态转换分析明确区分了环境充分、程序形成、干净认证和 Official 成功。Meerkat 对照在第 117 次
请求已经满足完整公开目标，却没有形成程序；另外三条失败轨迹从未达到充分状态。因此下一 treatment 只
消除“终点重建整份程序”，不声称已经解决未解除的兼容性约束。

每条由模型选择的持久操作都通过 `apply_environment_step` 执行，只有构建成功才追加到有序程序。每次追加
自动触发完整公开目标；目标 Pass 就立即从目标初始状态重放累计程序，失败回到同一 session，成功直接
结束。观察仍使用普通 shell。算法不增加 package 规则、checkpoint、跨 case 记忆、固定周期、候选图，
也不新增 hash、冻结 contract 或 gate。

开真实 episode 前先完成确定性资格验证。首轮真实资格验证只使用已消费的 goal-to-delivery case，验证
机制是否激活，不估计效果。完成后才固定算法和结果未知的比较 batch。

已消费资格验证在效果比较前否决了双工具界面。三个 episode 中，Agent 调用普通 shell 69 次，定义性
操作工具仅 1 次；Qibolab 和 HARK 从未激活，Meerkat 直到第 20 次请求才首次调用。HARK 还通过
普通 shell 执行了真实 editable install。没有 episode 进入 replay 或 Official 评测。这是操作界面
失败，不是对增量程序假设的检验。V1 不再通过提示词补丁续命；下一最小候选保留任意 Bash，但只使用一个
shell 通道，并要求每次调用声明“观察”或“持久步骤”。

标注式增量程序 V2 只实现这一项变化，并保留 V1 作为负基线。`envbench_shell(command, effect)` 仍能
执行任意 Bash；`effect=inspect` 只执行不记录，成功的 `effect=persist` 进入有序程序并触发已有目标
检查与 replay。harness 不分类命令，也不纠正错误标注。V2 只在 V1 的同一已消费 case 集上验证界面
激活；任何效果结论都必须等待后续结果未知的固定 batch。

证据与设计：

- `experiments/validations/envsolve_pro_v2_minimal_b_bad4_v1_transition_analysis.json`
- `research/ENVSOLVE_PRO_INCREMENTAL_PROGRAM_V1_ZH.md`
- `research/ENVSOLVE_PRO_INCREMENTAL_PROGRAM_V1_RESULT_ZH.md`
- `experiments/validations/envsolve_pro_v2_incremental_program_v1_consumed3_result.json`
- `research/ENVSOLVE_PRO_INCREMENTAL_PROGRAM_V2_ZH.md`
- `experiments/validations/envsolve_pro_v2_incremental_program_v2_consumed3_design.json`
