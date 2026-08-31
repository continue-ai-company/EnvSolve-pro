# EnvSolve-Pro Protected Canary 方案 V3

状态：等待审查的最终启动合同；仍不授权执行 protected case。

## 主张与固定两臂

**主要假设**是：session 内完整程序目标态反例重放能够提高强模型 `gpt-5.6-sol` 的 paired Official
Pass@1。DeepSeek V4 Flash 是次要的机制复制分层，用于分析能力依赖，不能救回强模型的零结果或
负结果。

`A-F` 是只接收普通构建反馈的连续 Agent session。`B-FR` 使用完全相同的 runner、prompt、工具、
模型和时间 allowance，只多一个接口：从目标初始状态执行完整候选，把可执行结果返回同一 session，
并且只能交付原样通过重放的程序。Official feedback 只在 episode 结束后产生。两臂都没有模型外
约束状态、frontier、checkpoint 搜索、handoff 策略、包级规则或跨 case 记忆。

## 数据与固定执行合同

Canary 使用尚未打开的 20 行 `experiments/cases/canary20.jsonl`。它在 2026-07-13 排除 Dev-5 后，
从 Official train outcome-blind 地预选；现有行序就是 case 顺序。位置 1--10 的完整 pairs 在 Spark，
11--20 在 AgentHub；奇数位置先 A 后 B，偶数位置先 B 后 A。同一 pair 不跨主机。每个 episode 从
同一个运行前 package-cache 基础快照派生独立 cache，不能继承另一 arm 的暖缓存。Mac 只调度和分析。

| 分层 | 精确身份 | 两臂共享限制 |
|---|---|---|
| 主要强模型 | `gpt-5.6-sol`；Codex CLI `0.151.0-alpha.7.2`；现有 `CodexCliRunner` 和 `EnvSolveProMinimalBRunner`；原生 Codex 账户后端 | generation 18,000 秒；command 1,800 秒；Official 2,400 秒 |
| 次要弱模型 | `deepseek/deepseek-v4-flash-0731`；OpenRouter；只用 DeepInfra；无 fallback；现有 OpenRouter control 与 Minimal-B runner | generation 18,000 秒；command 1,800 秒；provider request 600 秒；Official 2,400 秒 |

请求数、Token 和美金都只做结果测量，不是停止阈值。如果 runner 要求填写数字，则把 request、Token
和 cost 字段设到 18,000 秒内物理上不可能触及的范围，不把它们当科研限制。触及 generation 总时长
但没有成功提交，按算法失败计。

## Phase 0：必须完成的 Consumed-Dev 资格检查

打开 Canary 前，用同一个已消费仓库覆盖两种模型、两臂和两台主机，共 8 个不计效果的 smoke
episode。它们必须核验上述精确身份、分层内一致的 A/B 时间限制、独立 cache 派生、全新构建状态，
以及 Official 只在 episode 结束后可见。

强模型资格检查还必须证明：A-F 和 B-FR 使用同一个 Codex session 接口；B-FR 至少真实提交一次
完整程序 replay；replay 的 Pass 或 Fail 返回该活跃 session。它不要求产生 success effect。如果
现有 runner 无法做到，强模型分层记为 **unavailable**，不能用原生 Codex 替代因果配对。

当前 TFMA terminal pair 也必须自然结束并封存。它只验证共享 cwd 与 exact-delivery 语义；发现共同
测量缺陷就阻止启动 Canary。两臂结果不计入算法效果，也绝不复活已否决的 frontier。

## 算力与时间表

已消费实验的 generation p50/p90：弱模型 16.0/30.2 分钟（n=8），强模型 19.7/51.0 分钟（n=10）；
failure-enriched 弱模型 Bad6 平均 51.5 分钟。因此每 episode 按 70 分钟估算 replay 与 Official 开销。

- Phase 0 身份/cache 资格检查：3--6 小时，可与 TFMA 等待并行；
- 核心 Canary：每台主机 40 个 episode、最多 2 条 lane；同 pair 两臂在 lane 内串行。最早 11 小时，
  p90 计划 24 小时；
- 封存 paired 结果和基础设施裁决：1 小时；批准启动后预计 15--30 小时得到核心裁决；
- Repo2Run、EnvBench FreeAgent 和原生 Codex 外部 baseline 只在核心结果封存后启动，不与 paired run
  抢主机资源，也不拖延核心裁决。

## 主指标与裁决

按 backbone 分开分析 Official Pass@1，报告 paired transition、效应区间和 exact McNemar。20 pairs
只是 protected 方向 Canary，不是统计确认；没有 control-only success 时，需要 6 个 treatment-only
success，双侧 exact McNemar 才低于 0.05。只有 strong treatment-only 多于 control-only、至少一次
真实 replay activation 且无共享测量缺陷，才允许原样方法进入 100-case strong Test。这只说明方向
promising，不是论文的确认性成功率结论。

- **Strong tie：** 可以支持 reliability，但默认停止 strong Test；
- **Strong negative：** 否定强模型方向并停止对应 Test；
- **Strong unavailable：** 报告缺失的因果接口，等待用户决定是否还值得做 weak-only paper；不能用
  native Codex 替代；
- **共享测量缺陷：** 整个 Canary 无效，不能修复后继续消费同一 protected set。

弱模型按相同分支独立报告。只有不改算法的 100-case Official Test 能承担确认性成功率主张。推理
开始后的未提交和程序自身超时都是失败。只有首次模型响应前的获取、主机、认证或 provider 故障可以
重跑同一 case/arm；只有 evaluator 崩溃或传输故障可以对原样程序做 evaluation-only retry；不替换
case。

只有同 runner A-F 对 B-FR 是因果比较。接入同 DeepSeek 的 Repo2Run/EnvBench FreeAgent 和原生
`gpt-5.6-sol` Codex 都是端到端比较。打开 Canary 后，不修改算法、prompt、工具、replay/提交语义、
模型身份、时间限制、cache 隔离或 OCO 规则；后续机制属于独立研究。最终论文报告 OCO 分布前必须由
两名标注者盲化复标，但复标不阻塞 paired generation。

