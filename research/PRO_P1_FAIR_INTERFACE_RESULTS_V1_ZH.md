# EnvSolve-pro P1 公平接口结果 v1

## 结论

P1 已通过 repository-neutral 测试和已消费 P0 证据的资格验证。开放候选边界消除了基于表示形式的拒绝，
adapter 前置条件暴露了原先隐藏的状态不一致，effect audit 保住了仓库完整性。这是接口结论，不是算法
效果结论。

本阶段没有打开 untouched Dev case，也没有发起新的模型请求。

## 冻结预测核验

| 预测 | 观测 | 判断 |
|---|---|---|
| 成功的 shell compound 与 probe 应保持可执行 | 6 条冻结 Raw ReAct/Repo2Run 轨迹全部编译，unsupported 为 0 | 支持 |
| Repo2Run `futaba` 依赖其原生 Python/Poetry 上下文 | 保留 Python 3.10 并激活 Poetry 环境后，official issues 从 159 降至 2 | 支持 |
| `importlib_metadata` 仍会与 evaluator 状态冲突 | Raw ReAct 与 Repo2Run 都因 `build_output/` 被识别为额外顶层包而失败 | 支持 |
| 旧 EnvSolve 的内部接受应在状态对齐后消失 | 预先创建 `build_output/` 后，冻结候选在第一次安装时失败 | 支持 |
| Effect audit 应拒绝越界副作用 | 修改源码、注入 import 文件、删除前置条件均被拒绝；正常环境产物被允许 | 支持 |

## 官方重放

最终开放接口重放全部完成 official evaluation，没有候选因表示层规则被拒绝。

| 候选 | Exit | Issues | Errors | Official Pass | 解释 |
|---|---:|---:|---:|---|---|
| Raw ReAct，`futaba` | 0 | 2 | 740 | 否 | 真实残余 Pyright 失败 |
| Raw ReAct，`importlib_metadata` | 1 | 0 | n/a | 否 | `build_output/` 包发现冲突 |
| Repo2Run，`marimo` | 0 | 372 | 2109 | 否 | 原生测试成功与 official Pyright 是不同目标 |
| Repo2Run，`futaba` | 0 | 2 | 740 | 否 | 恢复原生上下文后仍有真实 Pyright 失败 |
| Repo2Run，`importlib_metadata` | 1 | 0 | n/a | 否 | `build_output/` 包发现冲突 |

已消费的 Raw ReAct `marimo` 轨迹完成了编译，但没有再次执行 official evaluation，因为它在 P0 的原生
执行并未成功完成。编译足以核验冻结的 representation-loss 预测，但不计作效果实验。

## P1 实际改变

- 部署产物从封闭 action list 改为完整 Bash 程序；
- EnvSolve 在 fresh checkout 中执行每个候选，并审计最终副作用；
- Benchmark adapter 声明不涉及结果的 workspace precondition；
- Raw ReAct causal replay 按原顺序保留所有成功命令；
- Repo2Run replay 保留成功 shell 程序及有证据的原生 runtime 上下文。

结构化观测层和约束层仍然是推理支架：它们可以解释和排序操作，但不能因为 schema 中没有某种操作形式
就拒绝该操作。

## 验证

- 完整测试：431 passed、2 skipped、75 subtests passed；
- 真实 Docker 集成：1 passed；
- 冻结编译：6 个 target，0 unsupported；
- 最终官方重放：5 个全部完成，0 representation rejection，0 Official Pass；
- 冻结内部重放：effect audit 合法，候选在对齐 `build_output/` 后被正确拒绝。

机器可读证据位于
`experiments/validations/pro_p1_evaluation_v1/evaluation_summary.json`。

## 下一步科研动作

冻结 P1，然后进入 P2：从剩余 Dev 中重新 salted sampling，抽取 outcome-blind 样本。P2 先完整运行并
分析轨迹，不改方法；只有一个跨 case 高频、可干预的真实部署矛盾，才可以驱动 EnvSolve-pro 的第一次
算法改动。
