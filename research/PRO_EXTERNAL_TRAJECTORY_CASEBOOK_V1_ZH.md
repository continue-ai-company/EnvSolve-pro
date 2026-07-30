# EnvSolve-Pro 外部轨迹案例册 V1

## 范围

本案例册记录一次已消费开发集上的事后机制研究。选择这两个仓库，是因为先前的
EnvSolve-Pro 运行已经暴露了它们的结果，因此它们不能支持主实验、测试集或榜单结论。
Repo2Run 和 Codex 还使用了不同模型与目标可见性，所以这里只解释行为，不做性能排名。

## Lark

| 方法 | 在线目标 | 结果 | 决定性行为 |
| --- | --- | --- | --- |
| EnvSolve-Pro goal-frontier-v1 | 公开目标 | 第 8 个候选 Official Pass | 完整 finding 数量按 `7 -> 4 -> 2 -> 0` 下降；最终程序使用 Conda。 |
| EnvSolve-Pro causal-v3 | 公开目标加额外结构化反馈 | 12 个候选后 Official Fail | 4 个 finding 的 frontier 多轮重复；增加结构没有改变操作。 |
| Repo2Run | 仓库原生测试 | Official Fail，13 个问题 | 原生测试通过后 loop 就停止，没有修复公开 Pyright 目标。 |
| goal-aware Codex | 公开目标与可见候选契约 | Official Pass | 交互式探测发现 `PyQt5-stubs` 遮蔽了 conda-forge 安装的真实 `PyQt5.Qsci` 二进制模块。 |

Lark 轨迹区分了三种能力。目标可见性可以阻止系统在代理目标上提前结束；交互式终端探测可以发现难以
在一份完整脚本中预判的包交互；约束状态只有真正改变下一步操作时才有价值。causal-v3 保留了更多
结构，却比更简单的 control 更差。

Codex 的第一次结果是 wrapper 测量错误：完整性审计把真实的项目内 Conda 环境当成了任意未跟踪
文件。修复后的识别必须同时具有 Conda transaction history、合法 package record 和已安装文件证据。
重新裁决复用了不可变的模型轨迹与候选程序，没有再次调用模型。

## micropy-cli

| 方法 | 在线目标 | 结果 | 决定性行为 |
| --- | --- | --- | --- |
| EnvSolve-Pro goal-frontier-v1 | 公开目标 | 12 个候选后 generation failure | 所有候选都失败，没有得到完整目标快照。 |
| EnvSolve-Pro causal-v3 | 公开目标加额外结构化反馈 | 8 个候选后 execution timeout | 只得到一次完整快照，包含 41 个 finding。 |
| Repo2Run | 仓库原生测试 | 没有合法候选程序 | 只有修改受版本控制的依赖声明后原生测试才通过；私有编辑动作不能重放为环境部署。 |
| goal-aware Codex | 公开目标与可见候选契约 | 候选策略拒绝 | Agent 通过写入 6 个合成 `.pyi` 文件把 missing import 降到 0，被候选验证器和 effect audit 同时拒绝。 |

micropy-cli 暴露了 verifier 与完整性之间的冲突：只要物化名称，而不安装真实能力，也能把公开指标
降到 0。即使 prompt 已经明确禁止，强模型仍可能选择这条捷径。因此，自然语言要求不能替代可执行
验证。

被拒绝的轨迹仍包含有用证据：它找到了可用的 Python 3.11 环境和大量真实依赖。当前 adapter 在最终
候选被拒后会丢弃这些工作。下一版 solver 应把精确拒绝原因和候选中的合法部分转化为下一轮修复状态。

## 主要矛盾

当前主要矛盾不只是缺少依赖知识，而是强搜索过程与一次性合法程序边界不匹配：

1. Repo2Run 有交互 loop，但优化代理目标，并且可能修改源码；
2. Codex 看到了正确目标，也能有效探测，但一次不合法的最终提交会让整例终止；
3. EnvSolve-Pro 有跨尝试显式状态，但操作层要求模型在细粒度终端诊断之前先生成完整脚本。

因此，下一版最小假设是**状态化约束引导的 Agent loop**。观测层保留完整目标 finding、命令失败、
effect violation 和 clean replay 结果；约束层只维护带来源的小型 ledger，不充当封闭规划器；操作层
使用具有开放终端的强 Agent。Agent 提交完整程序并接收可执行验证结果，候选被拒后可以在新一轮继续
修复。只有通过完整性检查的 clean replay 才能成功结束。

## 实验含义

受控实验应该使用同一个强模型和同一个公开目标：

1. 单次原生 goal-aware Codex session；
2. 仅携带原始历史反馈的多次 Codex session；
3. 携带结构化当前目标、合法性状态、最佳有效程序和相关原始证据的 EnvSolve-Pro session。

主指标仍是 Official Pass@1。尝试数、wall-clock、token、请求数、命令数、候选拒绝和首次失败后的
恢复率作为次指标。资源数据描述成功率与效率的关系，但不能覆盖一次合法成功。

## Stateful-Agent V2.2 Dev-5 补充

repository-disjoint Dev-5 现在属于已消费开发证据。强单 session、raw feedback 与 structured V2.2
分别得到 `5/5`、`5/5` 和 `4/5` Official Pass。

三个 case 应长期保留在高价值轨迹集合中：

- **moat-mqtt：** 合法的 `pkgutil.extend_path` namespace composition 证伪了把同项目 provenance
  一刀切设为 hard constraint。这是约束权威错误。
- **smart_open：** 有意失败的 import fixture 可以区分“保留运行语义”与“仅让名称在静态分析中
  可见”。这是方案质量诊断，不属于官方计分。
- **plotnine：** 572 个 surface failure 只有 15 个 root obligation，但旧状态路径生成了 2,557 个
  event 和约 630 KB 模型输入。这是状态放大的标准案例。

`molecularnodes` 作为 benchmark 语义案例保留：静态 import 可见性可能接受与目标 runtime 不兼容的
二进制。`aqtinstall` 是 stateful repair 没有增加成功价值的 negative control。

这些 case 可以启发 V2.3，但不能检验 V2.3。后续轨迹分析必须记录 surface finding 数、root
obligation 数、模型可见字节、审计档案字节、state event 数、constraint authority，以及结构化修复
状态之前是否真的发生过首次失败。

## Stateful-Agent V2.3 Pilot-3 补充

三个 repository-disjoint case 都已经消费。所有条件都通过 pypose 与 Pulser，并在 StopStalk 上失败，
因此本轮不能对方法效果排序。

- **pypose：** repair structure 的 negative control。三种方法都找到合法环境，额外状态没有提高成功。
- **Pulser：** 第二个 negative control。仓库 source root 加 `PYTHONPATH` 已满足官方目标，结构化
  loop 没有增加成功价值。
- **StopStalk：** 操作接口的标准 case。一份候选已经满足目标，却没有恢复 caller CWD；另一份候选
  满足目标但违反 repository effect；之后一份合法候选只读取 `.py` 源文件并写配置，却被验证器错误
  关联后拒绝。因此真正需要保留的状态是“目标状态 + 精确操作后置条件”。

StopStalk 只能验证 V2.4 回归行为，不能验证 V2.4 性能。后续 case 应按最早失败接口标注：goal、
operation policy、repository effect、caller shell postcondition、clean replay 或 infrastructure。
