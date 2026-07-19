# P6 约束操作层资格实验 V6 结果

状态：开发资格实验已完成，五个 case identity 全部 consumed。

## 冻结执行

- 选样与 schedule revision：`47fa4e56f4d76acbac53ac78f09e5b5bb5a06464`。
- Schedule SHA256：`b5c640e40b0e38af259758565077070e5c28dda34f5fc939d66ee70d4c6bb025`。
- 模型为 `deepseek/deepseek-v4-pro`；每个 episode 最多 5 个 candidate、command 和 fresh
  environment；generation 上限 7,200 秒，coordinator 上限 9,600 秒。
- 10 个 run 全部 artifact-valid、schedule 一致、未超原始预算，heartbeat 完整且没有 host
  suspension；按照冻结的 Q6 contract，10 个 run 全部 scientifically eligible。模型请求错误为 0。

## 结果

| Case | 完整 EnvSolve | Free-form 消融 | Official pair |
|---|---|---|---|
| `django-mysql` | candidate limit；5 candidates；28,710 tokens；182.1 秒 | candidate limit；5 candidates；41,408 tokens；603.0 秒 | 无 official evaluation，删失 |
| `plugins` | candidate limit；5 candidates；47,351 tokens；492.6 秒 | candidate limit；5 candidates；39,216 tokens；382.2 秒 | 无 official evaluation，删失 |
| `helios-server` | candidate limit；5 candidates；31,885 tokens；583.1 秒 | candidate limit；5 candidates；39,270 tokens；720.7 秒 | 无 official evaluation，删失 |
| `rebench` | 2 candidates 后 internal pass；official fail，`issues_count=1` | 2 candidates 后 internal pass；official fail，`issues_count=28` | 双方都未通过 |
| `datasets` | 1 candidate 后 execution-timeout Unknown；5,604 tokens；935.4 秒 | 2 candidates 后 execution-timeout Unknown；15,603 tokens；1,926.2 秒 | 无 official evaluation，删失 |

确定性汇总包含 0 个 official pass、2 个 official fail 和 8 个没有 official Boolean 的 run。五组
pair 只有一组能进入 official paired estimate，且双方都失败。Q6 没有让当前 operation mechanism
获得资格，也不支持任何效果 claim。

## 错误分析

1. **Operation layer 在 episode 起点只是被动反应。** 首个 full-method `OperationPlan` 为空，因为
   仓库观测尚未被转成初始约束。三个 candidate-limit case 中，两组都逐个发现依赖并撞上五候选上限。
2. **内部 import coverage 漏掉 documentation source。** Full EnvSolve 把 `rebench` 的 official
   missing-import issues 从 28 降到 1；剩余的 `recommonmark.parser` 位于 `docs/conf.py`。
3. **没有基础设施签名的执行超时被删失成 infrastructure failure。** `datasets` 日志实际显示 pip
   dependency backtracking 和昂贵的 build dependency 安装。只有日志含可识别的 DNS、TLS、HTTP 或
   connection signature 时，timeout 才应保持 infrastructure Unknown。
4. **Internal success 尚未与 official success 校准。** “环境可执行”和“官方静态闭包”是两个不同
   结果。Full 的 `issues_count=1` 是有信息的 near miss，但仍然是 Fail。
5. **Evaluator provenance 被记录，但尚未形成干净 commit。** EnvBench checkout 有三处通用兼容补丁，
   source hash 已冻结；confirmatory experiment 前必须形成可分享的 clean evaluator revision。

## Q6 后机制修正

两项修正只在 Q6 完成后实现。普通执行 timeout 现在是带结构化 cost hypothesis 的 candidate failure，
可驱动下一 fresh candidate；只有带明确基础设施签名的 timeout 保持 Unknown。Documentation import
现在与 runtime、test、build import 一样进入有界、与 benchmark 解耦的两层 inventory。合成测试、
全量回归（`347 passed, 1 skipped`）和显式真实 Docker boundary 均通过。这些修正属于 development-set
adaptation，必须在新的 outcome-blind case 上验证；Q6 永不重跑。

下一算法里程碑是预注册“首次动作前，如何把初始仓库观测保守地转成约束”，随后使用干净 evaluator
revision 开展新的配对资格实验。
