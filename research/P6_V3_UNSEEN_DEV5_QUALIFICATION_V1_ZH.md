# P6 V3 Unseen Dev-5 资格实验 V1

状态：在 case 选择、仓库检查、模型执行和官方评测之前完成预注册。

## 目标

检验 static-source evidence 能否纠正 runtime-only 的 internal-Pass 校准问题，同时保持模型、
仓库信息、execution probe、candidate language、fresh-environment policy 和总预算不变。
这是 development qualification，不是确认性证据。

## Outcome-blind 选择

- 总体：`experiments/cases/train_untouched201.jsonl`，SHA256 为
  `076ef72dbab0bb5cdefa72b10b2a84d4391914716fb640c5ab5f579b46677bfe`。
- Salt：`envsolve-p6-v3-qualification-v1-2026-07-16`。
- 按 `SHA256(salt + \"\\0\" + case_id)` 升序排列，选择前 5 个 case。
- 选择过程只读取冻结 case metadata；选择前禁止读取仓库源码、package metadata、历史轨迹或
  evaluator outcome。
- 入选 case 永久标记为 development-only，并从剩余 untouched-training pool 中移除。
  Canary-20 与 Official-Test-100 保持 untouched。

## 配对方法

每个选中 case 运行两个相互独立的 episode：

1. `envsolve-runtime-only`：使用 V3 inventory 与 probe，但只有 runtime-semantic evidence
   可以进入 obligation state。
2. `envsolve-full`：完全相同的实现，同时接纳 runtime-semantic 与 static-source evidence。

两组都使用 `deepseek/deepseek-v4-pro`、temperature zero、相同冻结价格、5-candidate 限制、
相同全局 token/request/cost/time 预算、相同 candidate DSL 和 fresh container。两组不共享轨迹、
container、ledger 或生成脚本。每个 case 内的方法顺序在执行前由 salted hash 决定。

## 评测边界

每个 method-case 的官方 evaluator 只能在 episode 结束后 claim 一次。官方输出是终局结果，
不得进入任一方法状态。网络、artifact 和 harness timeout 保持 Unknown，不产生 repair constraint。

## 记录结果

- internal Pass、Fail 或 Unknown 以及 candidate index；
- official Pass 与 missing-import count；
- 按 obligation layer 统计的 active 与 unknown finding；
- repair transition、重复约束、environment 数与 wall time；
- 模型请求、tokens 与估算成本；
- audit validity 与 clean replay。

## 资格解释

5 个 case 不能支持榜单或论文级效果 claim。只有所有 run 都通过 audit，并且每当 runtime-only
达到 internal Pass、却在终局 static import 评测失败时，V3 能在 internal Pass 前暴露对应失败或
正确返回 Unknown，才认为机制通过资格验证。Official Pass 数、成本与候选数只做描述性报告。
任何 V3 regression 都必须转化为通用错误分析与合成反例；选中 case 的名称或 outcome 不得成为
repair rule。

## Freeze 要求

在第一次模型请求之前，选中 split、剩余 untouched pool、method switch、本协议、测试和选择
provenance 必须进入新的有效 harness freeze。
