# EnvSolve-Pro Stateful-Agent V2.3 Pilot-3 结果

## 状态

这是已消费的开发证据。九个 artifact 的哈希与内容完整性均有效，但运行开始时 worktree 不干净，
因此全部不具备科学统计资格。这批结果只能用于提出通用机制修复，不能支持效果、论文主表或榜单结论。

三个 repository-disjoint case 比较了：

1. 强单 session goal-aware Codex；
2. 同模型多 session raw repair；
3. EnvSolve-Pro structured V2.3。

所有条件都使用 `gpt-5.5`、相同公开可执行目标、相同的终局官方 evaluator 边界，以及开放的累计
Bash 部署程序。

## 描述性结果

| 条件 | Official Pass | Wall time (s) | 命令数 | Input token | Output token | Reasoning token |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 强 goal-aware baseline | 2/3 | 4,576.2 | 97 | 4,805,038 | 50,680 | 21,775 |
| Raw repair V2.3 | 2/3 | 4,335.7 | 98 | 3,601,859 | 42,902 | 22,050 |
| Structured V2.3 | 2/3 | 7,940.6 | 218 | 11,176,127 | 123,352 | 64,447 |

| 仓库 | Strong | Raw | Structured | 决定性观测 |
| --- | ---: | ---: | ---: | --- |
| pypose | Pass | Pass | Pass | 不需要有效的结构化修复优势就能解决。 |
| StopStalk | Generation fail | Official fail | Generation fail | caller 可见的操作契约与 verifier 归因决定了最终结果。 |
| Pulser | Pass | Pass | Pass | source root 加 `PYTHONPATH` 已经足够，额外状态没有增加成功率。 |

V2.3 没有效果增益，structured V2.3 在这个小样本中也是资源效率最低的条件。由于运行源代码不干净，
即使这些描述性数字也不能合并到正式统计结果中。

## 错误分析

StopStalk 暴露了一个通用矛盾：**目标是否满足与操作是否合法是两个不同的状态变量**。

- Raw-repair 候选完成了部署目标，但 bootstrap 结束时把 caller 留在临时目录。终局 evaluator 的
  相对输出路径因此解析到了错误位置。
- Structured 第三轮构造了合法环境，读取真实 Python 源文件，只写 analyzer 配置；旧验证器却把任意
  带引号的 `.py` 路径与任意写调用做全局关联，产生错误拒绝。
- 更早一轮已经满足可执行目标，但违反 repository effect。紧凑投影把二者压成普通失败，下一轮重新
  搜索，而不是保留已有构造并精确修复 effect violation。
- 强 baseline 已满足内部目标，却在恢复状态时修改了一个受版本控制的嵌套仓库。

这些都不是特定包知识问题，而是目标导向 Agent 与可执行操作验证之间的接口问题。

## V2.4 决策

V2.4 不增加部署启发式，也不收窄终端动作空间，只修正四个接口：

1. 使用 AST 分析真正的 embedded-Python 写入目标，替代全局文本关联；
2. 独立表示 `goal_status` 与 `operation_contract`；
3. 要求提交程序恢复 caller 的工作目录；
4. 当目标已经通过时保留精确操作反例；终局合法 Pass 后移除过期拒绝元数据。

V2.3 的三个 case 已经消费。V2.4 必须从干净、已提交的版本冻结，并在新的 repository identity 上
验证。主结果仍是 Official Pass@1；机制结果是“目标已满足但操作后置条件违规”后的修复成功率。
