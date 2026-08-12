# EnvSolve-Pro Boundary-v5 Untouched-4 实验结果

## 状态

预注册实验已经完成：4 个从未打开过的仓库、3 个配对方案、12 个有效 Agent episode。实验期间算法和边界始终冻结。本文只记录结果，不修改论文主张，也不提前决定下一版算法。

## 实验问题

让 Agent 在干净环境中看到重放结果，能否比单独使用强 coding Agent 获得更高的 EnvBench 官方 Pass@1？

- **A，强 Agent 对照组：** Agent 在一个连续 session 中完成部署。结束后系统秘密重放一次，但不把结果告诉 Agent。
- **B，一次认证组：** Agent 可以看到一次干净重放，但看完后不能再修改方案。
- **C，可重试认证组：** 同一个 Agent session 可以看到干净重放结果、修改部署程序并再次重放。

三组使用相同的公开目标、模型、推理强度、候选程序语言、认证边界、仓库随机种子和 Mac 主机。

## 主要结果

| 方案 | 官方 Pass@1 | 相比 A 多通过 | 相比 A 少通过 |
| --- | ---: | ---: | ---: |
| A | 4/4 | - | - |
| B | 4/4 | 0 | 0 |
| C | 4/4 | 0 | 0 |

三组成功率的观测差值为零。样本很小，而且 4 个 case 全部被强 Agent 做成功，因此不能证明重放永远没用；但它足以说明 v5 在本轮没有带来榜单成功率提升。

## 机制结果

B 的 4 次首次重放全部通过，所以没有产生修复机会。

C 有 2 个 case 首次重放直接通过；另外 2 个 case 中，同一个 Agent session 根据失败反馈修改了程序，随后干净重放和官方评测都通过。因此，可重试机制在工程上确实跑通了。

但是，两次修复都来自我们定义的来源审计边界：

1. GPflow 使用了被边界拒绝的 Conda pip 安装路径。
2. NeuralForecast 使用 `uv venv --seed`，产生了无法被边界认定来源的 virtualenv seed 文件。

它们都不是 EnvBench 官方缺失导入错误。因此，这两次只能证明机制被触发并能修复，不能证明它修复了榜单上的失败 case。

## 核心发现

### 1. 当前主要矛盾不是缺少重放

强 Agent 已经做成功全部 4 个仓库。可见重放没有额外救回 case。继续增加跨候选约束目前没有数据依据。

### 2. 官方通过不等于完整部署

在 NeuralForecast 上，B 有意使用 `--no-deps`，只安装项目和能消除缺失导入的直接包。它通过了冻结的官方缺失导入指标，但 pip 明确报告仍缺少传递依赖。因此论文必须把官方 Pass@1 和完整可运行部署分开报告。

### 3. 同样通过，部署质量可能完全不同

三个独立 Agent 在 NeuralForecast 上得到了三种成功方案：

| 方案 | 部署路径 | 官方结果 |
| --- | --- | ---: |
| B | 只满足指标的直接依赖，传递依赖不完整 | Pass |
| C | 完整的 CPU-only PyTorch 环境 | Pass |
| A | 完整的默认 PyTorch 环境，包含 CUDA 依赖 | Pass |

包和硬件路径选择主导了时间、存储和网络流量。这些选择发生在重放反馈之前，所以它们说明成功路径质量差异很大，却不能算成 C 的因果收益。

### 4. 效率数字只能描述，不能下因果结论

A、B、C 的平均观测时间分别约为 1681、1318、1151 秒。B、C 的平均输入 token 分别为 616208 和 659831；A 因 GPflow wrapper 被中断，只保留了 3 个 episode 的 token，均值为 759556。每组只有 4 条随机轨迹，而且受到缓存、网络、运行顺序和部署路径差异影响，不能宣称 C 更省时或更省 token。

## 决策

不把可重试认证提升为 EnvSolve-Pro 的核心成功算法。将 boundary-v5 和 A/B/C 实现冻结为可复现 baseline 及正交 treatment。

修改核心算法之前，下一轮实验必须先讨论并预注册。它应当：

1. 从未见数据中按结果不可知的随机或分层方式抽样。
2. 包含足够多真实的官方失败，观察 A/B/C 是否出现不一致结果。
3. 继续以官方 Pass@1 作为刷榜主指标。
4. 把部署完整性和资源路径质量作为独立评价轴。
5. 只有多条轨迹反复暴露同一个因果失败模式时，才增加结构化规则。

目前没有启动下一轮实验，也没有修改算法。

## 证据位置

- 机器可读总结果：`experiments/validations/pro_certification_repair_boundary_v5_untouched4_gate_result.json`
- 预注册：`experiments/validations/pro_certification_repair_boundary_v5_untouched4_preregistration.json`
- 四组 case 对照：`experiments/validations/` 下的 `trafilatura`、`gpflow`、`zappa` 和 `neuralforecast` triplet JSON
- 冻结实现：`experiments/protocols/envsolve_pro_certification_repair_boundary_v5_implementation_freeze.json`
