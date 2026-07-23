# EnvSolve-pro 跨方法轨迹普查协议 v1

## 目的

本轮在同一组 16 个仓库上比较 EnvSolve-pro、Codex CLI 与 Repo2Run 的完整轨迹，用于识别下一版
算法的跨仓库主要矛盾，不估计 held-out 效果，也不打开新的 untouched case。

## 冻结目标

唯一终局成功标准是未修改的 EnvBench Python contract：

`exit_code == 0 and issues_count == 0`

其中 `issues_count` 只统计 `reportMissingImports`。Pyright 总 `errorCount`、warning 和其他 diagnostic
不计分，不能决定失败类别、候选优先级或机制优先级。

## 方法

| 方法 | 主机 | 角色 |
|---|---|---|
| EnvSolve-pro causal v3 | DGX Spark | 当前三层方法 |
| Codex CLI，`gpt-5.5`，high reasoning | Mac | 强原生 Agent 参照 |
| Repo2Run reproduced open program | DGX Spark | 外部部署 baseline |

更早的 EnvSolve-pro census 轨迹保留为历史对照；由于模型可见的约束前沿已经变化，当前方法需要重跑。

## 分析

每个 method-case 记录：

- terminal reach、Official Pass、bootstrap exit 和 `issues_count`；
- 模型请求、token、执行环境、命令与 wall time；
- 是否输出可重放的最终程序；
- 最早决定性分歧属于观测层、约束层、操作层、终局化还是基础设施。

主要机制统计量是每类“最早决定性分歧”覆盖的不同仓库数。只有某一类别唯一最大、至少出现在四个仓库，
并能写成 repository-independent counterexample，才允许进入下一版。基础设施失败保持 Unknown。
执行开始后不得修改源码、prompt、wrapper 或 solver。

## 执行

16 个 case 是两组已消费 P4 census 的完整并集，执行顺序由 salted hash 固定。Mac 运行一条 Codex
队列；Spark 运行一条 EnvSolve-pro 队列和两条互不重叠的 Repo2Run 队列。每个最终程序只调用一次
未修改的 terminal-only evaluator。
