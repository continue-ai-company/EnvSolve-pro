# EnvSolve-Pro Protected Canary 方案 V2

状态：等待审查；本文档不授权打开 protected case。

## 估计目标与固定两臂

主要假设是：session 内完整程序目标态反例重放能够提高**强 Agent**的配对 Official Pass@1。较弱
backbone 分层用于验证机制复制和能力依赖；两个分层绝不合并。

`A-F` 是只接收普通构建反馈的连续 Agent session。`B-FR` 使用完全相同的 runner、prompt、工具、
模型和运行 allowance，唯一差别是：Agent 可以从目标初始状态执行完整程序，在同一 session 接收
失败，并且只能交付原样通过重放的程序。Official feedback 只在 episode 结束后产生。两臂都没有
模型外约束状态、frontier、checkpoint 搜索、handoff 策略、包级规则或跨 case 记忆。

## 数据、执行身份与隔离

Protected Canary 使用已有的 20 行 `experiments/cases/canary20.jsonl`。它在 2026-07-13 预先选定：
排除 Dev-5 后，从 Official train 中 outcome-blind 地按 SHA256 排序取前 20 个。成员和行序早于本研究
固定；截至 2026-08-30 的 exposure audit 仍把它保留给未见估计，case 内容尚未打开。

位置 1--10 的完整 pairs 在 Spark，11--20 在 AgentHub；奇数位置先 A 后 B，偶数位置先 B 后 A。
同一 pair 不跨主机。每个 episode 从同一个运行前 package-cache 基础快照派生独立 cache，避免先运行
的 arm 给后运行的 arm 暖缓存。Mac 只调度和分析。

执行身份与启动缺口如下：

| 分层 | 精确身份 | 固定 allowance | 启动状态 |
|---|---|---|---|
| 较弱 | `deepseek/deepseek-v4-flash-0731`；OpenRouter；只用 DeepInfra；无 fallback | 120 次模型请求；generation 18,000 秒；command 1,800 秒；provider request 600 秒；Official 2,400 秒 | 已在 consumed Dev 通过资格检查 |
| 强 | `gpt-5.6-sol`；Codex CLI `0.151.0-alpha.7.2`；现有 `CodexCliRunner`/`EnvSolveProMinimalBRunner`；原生 Codex 账户后端 | generation 18,000 秒；command 1,800 秒；Official 2,400 秒 | **启动前硬缺口：** consumed-case adapter qualification 尚未完成，而且当前 runner 不会真正执行配置中的逐轮 request guard。在不新建 runner 的前提下证明同 runner 接口并固定 request policy 之前，不启动强模型 Canary。 |

Token 和美金只做测量，不是停止阈值。一次 scientifically eligible episode 只要已经开始推理，却没有
提交、触及运行保护或由程序导致超时，都按算法失败计。

## 可完成的时间表

已消费实验中，弱模型 generation p50/p90 为 16.0/30.2 分钟（8 个 episode），强模型为
19.7/51.0 分钟（10 个 episode）。Failure-enriched 弱模型 Bad6 的平均时间是 51.5 分钟，因此排期
不采用乐观中位数，而按每 episode 70 分钟估算 replay 和 Official 开销。

| 阶段 | 工作与顺序 | 目标时间 |
|---|---|---:|
| 0 | 只用 consumed Dev：资格检查 `gpt-5.6-sol`，解决 request policy 缺口，在两台主机验证独立 cache 派生 | 3--6 小时 |
| 1 | 只跑核心 Canary：每台 40 个 episode，最多 2 条并发 lane；同 pair 两臂串行；不并发外部 baseline | 最早 11 小时，p90 计划 24 小时 |
| 2 | 封存 paired Official 结果并裁决基础设施事件 | 1 小时 |
| 3 | 核心结果封存后再跑通过资格检查的 Repo2Run/EnvBench/Codex 端到端 baseline；同时开始 OCO 盲化复标 | 不拖延核心裁决 |

因此，批准后最早约 15 小时得到核心裁决；按实测 p90 负载，计划最晚约 30 小时。Provider 或主机
中断作为排期偏差报告，不能靠提高并发掩盖。

## 主指标、删失与裁决分支

主指标是按 backbone 分开报告的 paired Official Pass@1，包括配对迁移表、效应区间和 exact McNemar。
在 20 pairs 且没有 control-only success 时，至少需要 6 个 treatment-only success，双侧 exact
McNemar 才低于 0.05；p 值大于 0.05 不等于证明无效，仍要报告区间和可检测效应。

基础设施删失只包括第一次模型响应前的源码获取、主机中断、认证或 provider outage，以及与提交程序
无关的 evaluator 崩溃或传输失败。前者只能重跑同一 case/arm；后者只能对原样程序做 evaluation-only
retry。有效 Official Fail、Agent 导致的超时和开始推理后的未提交都是失败；不替换 case。

Canary 预先规定四种分支：

- **进入 Test：** treatment-only 多于 control-only，没有共享测量缺陷，并且至少观察到一次真实 replay
  activation。它只表示方向 promising，不能承担确认性成功率主张；允许不改算法进入 100-case Test。
- **平局：** replay 与 Official 一致可以支持 reliability，但 Canary 不提供 effect 证据。默认不打开
  昂贵 Test，除非用户明确决定继续缩小置信区间。
- **负向：** control-only 多于 treatment-only。否定该 backbone 上的成功率方向，停止对应 Test。
- **共享测量缺陷：** 整个 Canary 无效，不能修复后继续消费同一 protected set。

只有 100-case Official Test 承担确认性成功率主张。强模型分层是主要假设；较弱分层用于解释复制与
能力依赖。Reliability、activation、候选形成、完整性、时间、请求数、Token、流量、磁盘和内存都是
次要指标，不能覆盖 Official 成功率。

## Baseline 与打开后的规则

只有同 runner 的 `A-F` 对 `B-FR` 是 replay 因果比较。接入相同 DeepSeek 的 Repo2Run/EnvBench
FreeAgent，以及原生 `gpt-5.6-sol` Codex，都因为 prompt、工具和恢复语义不同而只属于端到端系统
比较。外部 adapter 只在 consumed Dev 上做资格检查，也不能拖延核心 Canary。

第一个 Canary episode 启动后，不再修改算法、prompt、tool schema、replay 时机、提交语义、validity
boundary、模型身份、allowance 或 OCO 规则。任何后续机制都是独立研究，不能回写 Canary。最终论文
报告错误分布前，两名标注者必须对隐藏 arm 身份的 OCO 轨迹包独立标注；复标不阻塞 paired generation。
