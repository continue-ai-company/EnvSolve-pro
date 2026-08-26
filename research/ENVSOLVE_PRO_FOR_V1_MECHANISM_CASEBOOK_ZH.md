# EnvSolve-Pro F/O/R 机制 Casebook

状态：已消费开发证据，2026-08-26；不是 held-out 效果结论

## 研究问题

固定实验从连续强 Agent session 中拆出两个增量：

- `F`：只使用仓库反馈的自由搜索；
- `F+O`：在 `F` 上增加完整可执行公开目标；
- `F+O+R`：在 `F+O` 上增加对完整候选程序的目标状态重放。

三臂使用相同模型、镜像、请求安全上限、完整性 contract 和 episode 后 Official evaluator。基础设施污染的
结果先删失，再做配对比较。校正后的机器可读分析位于
`experiments/runs/envsolve_pro_for_v1_consumed6_corrected_analysis.json`。

## 配对结果

| Pair | 仓库 | F | F+O | F+O+R | 因果用途 |
| --- | --- | --- | --- | --- | --- |
| 01 | conan-package-tools | Fail | Pass | Pass | O 带来增益；R 只认证，没有增加成功 |
| 03 | pyrollbar | 删失 | 删失 | Pass | 只能描述 |
| 08 | langgraph | 删失 | 删失 | Pass | 只能描述 |
| 11 | geoapps | 生成失败 | 生成失败 | 生成失败 | 两个 contrast 中都属于有效 hard-case failure |
| 12 | sphinx-gallery | Fail | Fail | Pass | R 独有的 Fail-to-Pass 修复 |
| 16 | nonebot2 | 删失 | 删失 | Pass | 只能描述 |

在三个可比较的 `F` 对 `F+O` pair 中，公开目标产生一次 treatment-only Pass，另两次双方都未通过。在
三个可比较的 `F+O` 对 `F+O+R` pair 中，重放产生一次双方都通过、一次 treatment-only Pass 和一次
双方都未通过。两个对比都没有 control-only Pass，但样本很小而且已经消费，不能据此估计泛化效果。

唯一双方都成功的 replay pair 是 Conan。相比 `F+O`，`F+O+R` 多用 24 次模型请求、1,358,064 Token、
6 条 shell 命令和 1,903.6 秒。因此当前 replay 不是效率 treatment。

## 决定性轨迹

### 公开目标：Conan

`F` 最后剩一个缺失导入 `conans.client.loader_parse`。`F+O` 根据精确公开 residual 闭合了最后的兼容缺口，
并通过 Official。`F+O+R` 也通过，第一次 replay 就成功。该 pair 支持观测层假设，但没有显示额外 replay
成功，而且 replay 成本明显更高。

### 目标状态重放：Sphinx-Gallery

`F` 和 `F+O` 都未通过 Official。`F+O+R` 提出的完整程序在第一次 clean replay 中失败，因为 Git 把
fresh checkout 判定为 dubious ownership。同一 session 把 `safe.directory` 操作加入程序；第二次 replay
和 Official 都通过。这是最干净的操作层反例：构造环境隐藏了目标初态前提，可执行重放及时暴露该事实，
让仍然活跃的 session 修复真正交付物。

### 目标不可满足与交付漂移：Geoapps

三臂都在 120 次模型请求后没有提交。goal-aware 两臂在 Linux ARM 上完成了大量真实构建，包括 PySide2、
GDAL/Fiona、`c-blosc2` 和仓库所需的旧数值栈。纠正 Python 路径观测后，源码包中的表观缺失导入从 477
降到 1。

完整 Official 扫描随后混合了三类 residual：

- 可以安装的开发依赖；
- 仓库自身缺陷或过时的 Python 2 文档导入；
- 专门测试“模块不存在”行为的故意缺失导入。

`F+O+R` 通过创建 `typings/` 在构造工作区达到过指标 Pass，但从未调用 replay 或 submission，之后又
reset 了构造 commit。`F+O` 尝试用 Pyright 配置排除目录，随后创建源码 compatibility shim 和复制出的
package tree；它还发现即使 package-scope Pyright Pass，仍有 19 个模块在运行时导入失败。最终没有候选
提交，候选工作区留下 258 个未跟踪文件。

因此 Geoapps 不能说明“replay 激活后无效”。它说明了另外两个问题：可选 replay 接口会被忽略；同时，
一个保持完整性的部署无法只靠改变环境消除这组 benchmark residual。该 case 仍作为 neither-Pass 留在
机制实验中，但 Official 成功和部署完整性必须分轴报告。

## 机制决策

证据支持一个最小接口修复：

```text
submit(P):
    从目标初始状态执行 P 和公开目标
    if Pass: return P
    if Fail: 把第一个可执行反例返回同一 Agent session
```

系统不再提供一个“不检查就交付”的提交动作，也不再把 replay 做成独立的可选动作。Agent 仍然决定何时
提交、怎样修复；harness 只保证交付是事务性的：候选程序要么重建出通过的目标状态，要么把证据返回活跃
session。

这个决策不增加 package 规则、结构化假设搜索、容器 checkpoint、forced handoff 或跨 case 记忆。它必须
在新的固定 batch 上做前瞻验证；上面的已消费 case 不能用于验证修改后的接口。
