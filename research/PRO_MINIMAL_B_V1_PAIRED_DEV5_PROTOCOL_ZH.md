# EnvSolve-Pro Minimal B v1 配对 Dev-5 实验协议

日期：2026-08-04

## 研究问题

在模型、公开目标、构建环境、终端、候选契约和终局 Official evaluator 都保持不变时，
把干净重放的反馈在线返回强部署 Agent，能否提高部署成功率？

## 对照条件

- **A，强 goal-aware Agent：** 一个连续 Codex session 和一个持久构建环境。Agent 返回一份
  完整 bootstrap 程序；session 结束后 harness 执行该程序，执行结果与 evaluator 结果均不
  返回 Agent。
- **B，Minimal B v1.0.2：** 共享上述设置，并增加 `submit_and_replay`。每次调用都在独立的
  干净 checkout 和容器中执行完整程序，把有界的公开目标与完整性证据返回仍然活跃的同一
  session。最终程序必须与通过重放的证书精确一致。

额外工具及使用该工具所必需的指令，是唯一预期的 treatment 差异。两种条件都不能在线看到
Official evaluator 输出。

## 样本与顺序

从冻结的 58 条未消费开发池中，以
`SHA256(salt + NUL + repository)` 升序选择 5 个仓库 identity。选择只使用元数据，不读取
仓库内容、历史结果，也不做失败预筛。case 顺序和每个 case 内的两种条件顺序分别由 salted
hash 冻结。每个仓库都运行两种条件，并共享模型、reasoning effort、镜像、公开目标和宽松的
安全上限。

## 结果指标

主指标是配对 Official Pass@1。完整性失败、generation failure、Official Fail 和基础设施
Unknown 必须分开报告。核心机制指标是 replay-conditioned repair：Minimal B 在同一 Agent
session 中收到一次失败或 Unknown 的 replay 后，继续修复并最终认证通过程序。

replay 次数、命令数、模型 token、wall-clock time、峰值内存、磁盘增长和可获得的网络流量只作
描述性指标。token 和美元成本都不是停止成功搜索的硬预算。

## 分析规则

必须完成或分类全部 10 个 episode，之后才能修改机制。禁止加入 case 特定规则、包特例、仓库
相关 prompt 或选择性替换 case。该开发 batch 可以否定或推动下一项通用机制，但不能支持
held-out 或榜单结论。

外部 provider 故障、Docker 不可用、主机 suspend 或独立记录的断网可以判为基础设施 Unknown。
任何完全相同的重试都必须先冻结 amendment；被 censor 的原始 artifact 继续保留，并且不作为本
batch 的模型训练样本。
