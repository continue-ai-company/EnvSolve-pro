# EnvSolve-Pro Minimal B v1：配对 Dev-5 结果

## 范围

这是冻结的、repository-disjoint 的**开发集**比较，双方都使用一个连续的 `gpt-5.5` Agent，
唯一核心差异是能否在线调用 clean replay。它只提供机制证据，不是 held-out、榜单或统计确认。

预注册主指标是 paired Official Pass@1。只有真正获得 Official Pass 的 episode 才记 1。四次发生在
Agent 启动前的中断或源码获取故障按照书面 amendment 重跑，原始 artifacts 仍然保留并从效应分母中
排除。

## 主要结果

| Repository | Minimal B | 强 Agent control | 配对结果 |
| --- | ---: | ---: | --- |
| `pymanopt/pymanopt` | Pass | Pass | 双方通过 |
| `datactive/bigbang` | Pass | 未通过 | 仅 treatment 通过 |
| `rdmorganiser/rdmo` | Pass | Pass | 双方通过 |
| `jazzband/tablib` | Pass | Pass | 双方通过 |
| `castagnait/plugin.video.netflix` | Pass | Pass | 双方通过 |

Minimal B 为 `5/5`，control 为 `4/5`，绝对差值 `+0.20`。只有一个 discordant pair，精确双侧
McNemar 检验为 `p = 1.0`。方向值得继续，但 5 对样本远不能证明稳定增益。

`bigbang` control 完成了大量有效工作，但最终程序直接创建可导入 stub artifact，被共享 candidate
policy 在 Official evaluator 前拒绝。这是在冻结开放程序边界下的方法失败，不是基础设施 Unknown。

## 机制审计

5 个 Minimal B episode 都只调用了一次 clean replay，而且第一次 replay 全部通过。没有任何轨迹
出现“replay 失败后，同一个 Agent session 继续修复”。因此，这一批**没有验证**我们提出的修复循环。
`bigbang` 的 treatment-only success 可能来自面向认证目标的提前规划，也可能来自普通运行方差，
不能归因于 replay-conditioned repair。

下一轮因果实验必须拆开三个条件：

1. 强 Agent 只接受终局 post-hoc replay；
2. 同一个 Agent 只能在终局调用一次 clean certification；
3. 同一个 Agent 可以反复 replay，并在失败后继续修复。

条件 1 对 2 测“面向认证交付物进行构建”的价值；条件 2 对 3 才真正隔离“根据重放反馈继续修复”
的价值。

## 资源结果

全部 5 对尝试中，Minimal B 使用 `2,855,195` total model tokens，control 使用 `2,724,528`
（`+4.8%`）；容器命令分别为 `94` 和 `107`（`-12.1%`）。在 4 对 wall-clock 可比的 pair 中，
Minimal B 共用 `9,664.4 s`，control 共用 `7,102.8 s`（`+36.1%`）。这些只是开发集描述结果，
不能声称效率更优。

峰值内存、磁盘增长和网络字节虽然已经预注册，但 runner 没有持久化，必须报告为缺失，不能靠印象
补数。`bigbang` 的 wall-clock pair 被删失，因为多次 GitHub 故障后，control 按 amendment 使用了
精确 revision 的本地源码缓存。

## Verifier 局限

两个方法都通过把 Pylint 内部 `_pylint_config` 目录加入 `PYTHONPATH`，让一个名为 `setup` 的模块
可解析，从而 Official Pass `plugin.video.netflix`。但 `docs/conf.py` 实际导入该模块中的
`get_addon_data`，而 Pylint 的模块并不提供这个符号。Clean replay 证明的是公开目标下精确程序可复现，
不是解析到的 provider 具备所需语义接口。

这个事后发现不改变 Official Pass@1，但给出了后续实验必须区分的一般问题：**模块能解析**只是必要
条件，不等于**所需接口兼容**。任何新增语义诊断都必须对所有方法完全相同，并与榜单 official score
分开报告。

## 决策

Minimal B 继续冻结为 baseline，但它还不是已经收敛的 EnvSolve-Pro 算法。打开下一批 outcome-blind
case 前，共享基础设施需要在 timeout 时杀死整个进程树、为所有条件统一使用 immutable exact-revision
source cache，并持久化内存、磁盘与网络 telemetry。这些是测量修复，不是算法贡献。

完成资格验证后，在更大的 repository-disjoint 开发批次上运行上述三臂机制分解。结构化状态、
checkpoint、假设搜索和最小化继续延后，直到重复失败模式说明其中某项确有必要。

机器可读证据位于 `experiments/validations/pro_minimal_b_v1_paired_dev5_results.json`；
`experiments/analyze_pro_minimal_b_v1_paired_dev5.py` 会从有效 episode 裁决和原始 run artifacts 重新
计算全部结果。
