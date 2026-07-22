# P4 轨迹普查结果

## 范围

P4 是已消费 Dev 上的诊断实验，不是效果实验。我们使用同一个冻结的 EnvSolve-pro 实现，对两组仅按
元数据盲选的 8 个仓库分别执行。独立复现组先单独分析，再做次级合并。复现组有两次依赖下载超时，
被判定为基础设施删失，并按冻结协议做了带 provenance 的新鲜重跑。

## 结果

| 样本 | 成功 | Evaluator | 观测 | 闭包 | 操作 | 唯一领先类别 |
|---|---:|---:|---:|---:|---:|---|
| 第一组，n=8 | 1 | 1 | 0 | 4 | 2 | 闭包 |
| 独立复现，n=8 | 3 | 0 | 0 | 1 | 4 | 操作 |
| 次级合并，n=16 | 4 | 1 | 0 | 5 | 6 | 操作 |

预注册的复现标准没有通过：第一组的 closure leader 没有在独立样本中继续领先。但两组都支持更高层的
预测：操作不可行与闭包缺口合计占严格多数，分别为 `6/8`、`5/8`，合并为 `11/16`。因此稳定的研究
目标不是单独某个失败标签，而是“约束闭包到可执行操作”的接口。

## 机制审计

大多数失败可以由三个跨仓库机制解释：

1. **Runtime/platform 前沿缺失或没有被诱导成约束。** LangGraph 反复暴露 Python 3.13 与 PyO3 最高
   3.12 的边界；Geoapps 和 RLberry 暴露 ARM lock/wheel 不兼容。初始观测记录了 Python，却没有记录
   machine architecture；精确错误也没有变成持续存在的根约束。
2. **平铺义务放大表面症状。** Conan 的一个根导入错误扩散为大量传递模块义务；scVelo、
   Python-holidays 与 Luigi 又被可选文档、脚本、负向测试和集成测试主导。当前状态没有因果父节点，
   也没有 scope 优先级。
3. **信任边界既过硬又可被绕过。** PyRollbar 已经构造出有效环境，但因为目录名是 `env` 而不是
   `venv/.venv` 被误判；Extension-helpers 的生成源码也被 effect policy 删除。相反，Sphinx-Gallery
   通过假 distribution 和工具 shim 让 Pyright 没有运行，而 raw evaluator 仍报告零 issues。

这些不是仓库特定的包安装错误。它们说明：可执行观测只有携带 scope、因果 provenance、平台 identity
与 trust level，才适合被硬化为操作义务。

## 敏感性与预算

Sphinx-Gallery 的预注册主分类仍保留为 `closure_gap`。完整性感知的敏感性分析将其改判为操作不可行，
此时第一组 closure 与 operation 变成 `3-3` 平局。`pyright=null` 的 raw evaluator 记录绝不计作成功。

16 个 case 中有 12 个达到 5-candidate 上限，说明该上限真实删失了搜索，不能作为“成功优先”主协议。
后续公平对比采用共享 wall-clock/container 边界，并把候选数和 token 上限放宽到非约束状态；token、
请求数、候选数和时间只作为效率指标报告。

## 决策

P5 不继续添加 package heuristic，也不只优化 closure。先修复 harness 正确性与受保护评测；之后只验证
一个最小的**因果约束前沿**假设：保留原始证据，诱导少量带来源的根约束，把有 scope 的表面义务连接
到根因，并向强模型暴露可行操作，但不封闭其动作空间。该机制先经过 synthetic 与已消费 case 的机制
验证，再进入预注册的新 Dev 配对实验。
