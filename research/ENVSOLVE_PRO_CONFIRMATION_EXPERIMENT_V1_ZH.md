# EnvSolve-Pro 确认实验方案 V1

状态：等待审查；仅凭本文档不得启动任何 Canary episode。

## 科学问题与固定方法

**同一活跃 session 内的完整程序目标态反例重放**，能否在不限制强弱 Agent 操作空间的前提下，
提高项目部署的终局成功率？

候选方法是 Minimal B，包含两个 arm：

| Arm | 接口 |
|---|---|
| `A-F` | 一个连续 Agent session，只接收普通构建反馈。 |
| `B-FR` | 保持相同 session 和工具，额外允许从目标初始状态反复执行完整候选；失败返回同一个 session，只有通过重放的原样程序才能交付。 |

方法不包含模型外约束状态、frontier、checkpoint 搜索、handoff 策略、包级规则或跨 case 记忆。
Official evaluation 只在 episode 结束后运行，绝不返回 Agent。

## Protected Canary 与执行顺序

Canary 使用已有的 20 行 `experiments/cases/canary20.jsonl`。它在 2026-07-13 预先选定：排除
Dev-5 后，从 Official train 按 SHA256 排序 outcome-blind 地取前 20 个；文件行序就是固定 case
顺序。截至 2026-08-30 的 exposure audit 只把 205 个 Dev 身份记为已消费，并继续把 Canary 和
Official Test 保留给未见估计；本研究没有打开任何 Canary 仓库。执行开始后，不改变 case 身份、
顺序和集合。

每个“模型--case”配对的两臂必须在同一主机上运行，并共享相同源码快照、EnvBench 镜像、provider
策略、seed 和运行 allowance。位置 1--10 在 Spark，11--20 在 AgentHub；奇数位置先 `A-F` 后
`B-FR`，偶数位置顺序相反。每个构建环境从零开始；下载缓存只是只读穿透式基础设施，不能暴露另一
arm 的环境状态。

主要弱模型分层使用已经在 consumed Dev 上通过资格检查的固定 DeepSeek V4 Flash snapshot，用于
估计 replay 对较弱开放模型的作用。强模型分层在打开 Canary 前，先用 consumed Dev 资格检查得到
精确 Codex GPT-5.6 标识，再重复相同配对设计，用于判断 replay 对 frontier Agent 是增益、中性还是
限制。如果强模型 adapter 不能保留同一活跃 session 和完全一致的两臂接口，就把该分层报告为不可用，
不能拿不匹配的原生 Codex 结果替代。

该设计包含 40 组配对、80 个核心 episode。Token 和美金都不是停止阈值。每个模型分层只设置一个
根据已消费运行范围预先确定的宽松 wall-clock deadline 和 provider 请求保护，并在分层内对两臂
完全相同；Agent 开始推理后触及上限且没有 Official Pass，按算法失败计。

## 指标与裁决

每个模型分层的主指标都是**配对 EnvBench Official Pass@1**。未提交、耗尽请求上限和程序自身导致
的超时都算失败。报告 paired transition table、带区间的成功率差和 exact McNemar；不能合并两个
模型分层来掩盖其中一个回退。

基础设施删失范围严格限定为：

- 第一次模型响应前发生的源码获取失败、主机中断、认证失败或 provider outage，可以在同一 case、
  同一 arm 上重跑；
- evaluator 崩溃或传输故障，只允许对原样提交程序做 evaluation-only retry；
- 有效 Official Fail、Agent 导致的超时，以及开始推理后未提交，都不能删失；
- 不用新 case 替换被删失的身份。

次要指标包括 replay 激活、replay Fail-to-repair-to-Pass、候选形成、最终 replay 与 Official 一致性、
部署完整性、wall-clock、模型请求数、Token、网络流量、磁盘增长和峰值内存。资源比较必须 case 配对
并以成功为条件，不能覆盖 Official 成功率。

所有算法非成功轨迹只标一个最早 OCO 原因。两名标注者对隐藏 arm 身份的轨迹包独立标注，报告一致性
和分歧裁决；基础设施删失 episode 不进入 OCO 分布。

在观察结果前固定以下解释：

- paired success difference 为正，且 treatment-only success 多于 control-only，支持该模型分层的
  终局成功主张；
- replay 与 Official 一致，或出现真实 Fail-to-repair-to-Pass，但没有正的配对成功率差，只能支持
  replay reliability；
- 平局不提供成功率增益证据，负的配对差则否定该分层上的成功率主张。

强弱模型分层必须分别报告。只在一个分层上增益，只能说明该能力区间，不能声称效果与模型能力无关。

## Baseline 与主张边界

只有在同 runner、同 backbone 下比较 `A-F` 与 `B-FR`，才能解释为 replay 的因果效应。Repo2Run
和 EnvBench FreeAgent 即使接入相同 DeepSeek snapshot，也因为 prompt、工具、恢复语义和候选接口
不同，只属于端到端系统比较。原生 Codex GPT-5.6 是 frontier 端到端参考。Harness 内 GPT-5.6 的
`A-F` 对 `B-FR` 是因果配对；原生 Codex 对 EnvSolve-Pro 不是。

外部 baseline adapter 只允许在已消费 Dev case 上做资格检查。资格通过后才可运行 Canary，而且结果
不能反向修改 Minimal B。两台机器承接的是完整 episode，绝不把一个“方法--case”配对拆到不同主机。

## 机器分工与 Canary 后规则

Spark 运行位置 1--10、GPU/CUDA 敏感外部 baseline 和 Linux-native Official；AgentHub 运行位置
11--20、CPU-only Repo2Run/EnvBench baseline 和独立结果汇总；本地 Mac 只编排封存证据和分析，
不成为第三种实验环境。

第一个 Canary episode 启动后，不再修改算法、prompt、tool schema、replay 时机、提交语义、共享
validity boundary、模型标识或 OCO 规则。基础设施重试必须保持 Agent 可见语义不变。若发现共享测量
缺陷，本次确认实验整体失效，不能修完后在同一 Canary 上继续。无论结果为正、零还是负都必须封存
报告。在本文档和完整 Canary 证据通过明确审查前，不启动 protected 100-case evaluation。
