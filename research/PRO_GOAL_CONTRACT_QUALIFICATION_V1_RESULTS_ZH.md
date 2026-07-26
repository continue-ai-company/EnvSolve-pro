# Goal-Contract Evidence-Anchor Qualification V1 结果

## 1. 范围

这是一个已经消费的 5-case EnvBench Dev qualification，对比两个冻结方法：

- 显式状态：`envsolve-pro-goal-contract-evidence-anchor`；
- 对照组：`envsolve-pro-goal-aware-raw-evidence-anchor`。

两者均使用 `deepseek/deepseek-v4-pro`、同一个公开可执行目标、finding 定向仓库证据、保留的
admissible anchor、开放 Bash 操作空间、全新候选环境和仅终局可见的 Official evaluation。唯一预期
差异是显式约束状态与有界 raw goal history。

官方成功严格等于 `exit_code == 0 && issues_count == 0`。`error_count` 与 `warning_count` 只是
描述性诊断，不参与计分。

## 2. 冻结结果

| Case | 显式状态 | Raw history | 显式候选槽位 / token / 生成墙钟 | Raw 候选槽位 / token / 生成墙钟 |
|---|---|---|---:|---:|
| River | Unknown：Official evaluation 前命令超时 | Unknown：反馈超过上下文契约 | 4 / 56,699 / 2,970.3 秒 | 11 / 215,561 / 12,958.5 秒 |
| LitGPT | Unknown：Official evaluation 前命令超时；最佳内部目标剩 2 条 finding | Official Fail：2 issues | 3 / 42,150 / 2,477.6 秒 | 12 / 220,855 / 5,021.6 秒 |
| ILAMB | Official Pass | Official Pass | 5 / 98,346 / 2,106.8 秒 | 6 / 105,771 / 4,089.0 秒 |
| Flask-Security | Official Pass | Official Pass | 3 / 41,636 / 470.3 秒 | 3 / 46,510 / 1,935.2 秒 |
| Starsim | Official Pass，但完整性无效 | Official Pass，但完整性无效 | 4 / 74,785 / 627.1 秒 | 4 / 85,151 / 1,365.2 秒 |

ILAMB 显式结果采用预注册替代 run
`pro-goal-anchor-qv1-c03-ilamb-exp-replacement1`。更早的 run 因监控竞态被研究者误终止：当时新的
模型请求已经开始。因此它属于 experimenter-censored，而不是 provider-censored。

Starsim 不进入科研效果分析。两个终局脚本都把缺失模块名 symlink 到 `starsim`，可以消除 benchmark
表面 finding，却没有提供这些名字对应的真实项目。冻结的 v1 执行前 guard 能拒绝手写空模块，但没有
拒绝语义等价的 import alias。

资格实验后的 integrity v2 已在两层拒绝这种行为：open-program validator 在执行前拦截指向 Python
搜索路径的符号链接；两条内部 verifier 主路径还会在执行后审计活动解释器。该修复不会追溯改变或接纳
两个历史 Starsim 结果。

## 3. 描述性汇总

五个计划结果合计，显式状态使用 19 个候选槽位、20 次模型请求、313,616 tokens 和 8,652.1 秒生成墙钟；
raw history 使用 36 个候选槽位、37 次请求、673,848 tokens 和 25,369.5 秒。对应减少 47.2%、45.9%、
53.5% 和 65.9%。

这些总量只能描述，不能作为因果效率估计：River 与 LitGPT 的终局删失不同，provider latency 方差很大，
Starsim 还违反完整性。

两个方法都获得 integrity-valid Official Pass 的配对只有 ILAMB 与 Flask-Security。显式状态使用
8 对 9 个候选、139,982 对 152,281 tokens、2,577.1 对 6,024.2 秒。结果与更低搜索负担一致，但两个
已消费配对不能确立效果。

Gross Official 口径下，两个方法各有 3 个 Pass；显式状态没有计分 Fail，raw history 有 1 个计分 Fail；
未进入 Official evaluation 的数量分别为 2 和 1。排除完整性无效结果后，当前证据不足以支持成功率
提升结论。

## 4. 机制发现

1. 显式状态经常用更少候选和模型上下文达到同一有效 finding 前沿，同时没有限制强模型的开放操作空间。
2. 很小的状态修复仍会重复执行昂贵安装前缀；River 与 ILAMB 上尤其明显。
3. Raw history 产生无进展候选，并最终在 River 超过反馈上下文。
4. 冻结 v1 无法按 transport attempt 观察输出延迟与 provider retry；Flask-Security raw 的一个局部
   修复响应耗时约 30 分钟。
5. 冻结 v1 完整性策略会拒绝直接文件 stub，但 symlink import alias 能绕过同一语义边界。
6. Repository effect audit 正确拒绝了一个会升级并覆盖 Starsim 被测源码树的依赖安装。
7. Adapter 预创建的 `build_output/` 会与 setuptools flat-layout discovery 冲突，因此 benchmark
   workspace precondition 必须成为显式仓库构建证据。

## 5. 决策

当前不应增加新的依赖配方。下一版本分两步：

1. **测量与完整性修复：** integrity v2 已在 admission 与 runtime 两层拒绝观测到的 import alias。
   v1.1 资源 ledger 关闭 SDK 隐藏重试，分开逻辑调用与 transport attempt，让多个 attempt 共享同一
   deadline，并区分研究者删失与已完成的 provider 故障。该实现已由
   `experiments/validations/pro_provider_attempt_recovery_v2_results.json` 完成 synthetic
   qualification，仍需一次真实 provider canary。
2. **操作层假设：** 对 suffix repair，从一个不可变、通过 effect audit 的环境前缀分支；但进入
   Official evaluation 前，必须在全新环境完整重放并认证拼接后的最终程序。若修复需要改写前缀，仍可
   选择 replacement。

第二步直接针对“状态层修复很小，但执行层仍全量重放”的重复矛盾。检验表示效果时，该执行机制必须同时
提供给显式状态与 raw-history 方法，并在 repository-disjoint qualification 上验证。

逐 run 数值、替代关系和排除原因保存在
`experiments/validations/pro_goal_contract_evidence_anchor_qualification_v1_results.json`。
