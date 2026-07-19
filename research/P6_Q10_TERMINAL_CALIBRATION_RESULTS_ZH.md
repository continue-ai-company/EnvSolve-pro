# P6 Q10 终局校准结果

状态：development calibration 已关闭。10 份预注册脚本均严格尝试一次；没有模型调用、replacement、
overwrite 或 retry。

## 完整性

10 条 run 全部通过 harness audit。每份实际评测脚本都匹配预提交 SHA256，每个 repository revision
都匹配选定 case，每条 run 也都记录了冻结且干净的 EnvBench revision，以及不可变 Docker image ID
和 RepoDigest。

| 结果 | 数量 |
| --- | ---: |
| Audit-valid script attempt | 10 |
| Official evaluation completed | 9 |
| Infrastructure `Unknown` | 1 |
| Official Pass | 0 |
| Internal false / Official false | 9 |
| Internal false / Official true | 0 |
| Bootstrap succeeded | 3 |
| 观测到 Pyright result | 3 |

唯一的 `Unknown` 是预注册规定不重试的 `read-timeout`。它不作为 Boolean failure，也不进入 verifier
一致性估计。

## 校准结论

完成评测的脚本中没有 internal-verifier false negative。9 次 completed evaluation 中有 6 次在
bootstrap 阶段失败；剩余 3 次完成 bootstrap，但 terminal static analysis 失败：一份脚本产生
824 个 Pyright error 和 58 个 warning；reddit2telegram 的两份配对脚本都产生 61 个 error 和 3 个
warning。

Full condition 的 5 份脚本中有 2 份进入 Pyright；ablation 为 1/5，另有 1 份 ablation `Unknown`。
这些小规模 development 计数只能描述，不能支持效果 claim。

Bootstrap failure 暴露的是通用 operation-feasibility family，而非单一 verifier scope 缺陷：native
build prerequisite 不可用、隔离构建环境缺少 build dependency、package/source mapping 不可用、语言
toolchain 缺失，以及旧构建链不兼容。具体 repository 日志只是例子，不能成为算法规则。

## 科研决策

Boolean internal gate 保持冻结。本次校准没有证据表明放松它能恢复任何成功部署。同时，结果暴露了
feedback quality 问题：即使 Official bootstrap 后来能够成功，某个 fixed check 也可能让 internal
verification 在观测其他独立约束前提前停止。正确修复不是接受该脚本，而是在保留 mandatory check
合取条件的同时避免 first-error masking。

更主要的 solver 缺陷发生得更早：确定性的 candidate-command failure 目前只作为有界反馈与精确失败
prefix 被记录，尚未成为 constraint state 中一等、带 provenance 的 operation outcome。下一项最小
机制 revision 应表示失败 operation、观测环境及其未满足 precondition，但不编码 repository 或 package
名称。合成反例必须证明：下一份 complete program 在重复失败 operation 前改变了相关 precondition。
只有该机制冻结后，才能选择新的 outcome-blind development batch。

后续代码审查发现了一个必须优先检验的更简单竞争解释。Q10 的 candidate、environment 和 command
limit 被耦合为 5；50 个 proposal 中有 9 个在创建 environment 前被拒绝，导致 9 个允许的 fresh
execution 未使用，而 model-request cap 仍为 15。因此 operation-outcome revision 暂缓。下一项使用
consumed Q10 identity 的 budget-only calibration 只把 candidate-proposal limit 从 5 改为 15，
environment、command、model request、token 和 time 都保持原上限。

## 声明边界

本校准使用已经消耗的 Q10 development identity，不重开 Q10、不估计榜单性能，也不解锁 held-out
evaluation。它证伪了一个假设：在 9 次完成的校准中，无法进入 terminal evaluator 并没有隐藏成功
脚本。下一主目标是部分可观测条件下的 operation feasibility 与 search efficiency。
