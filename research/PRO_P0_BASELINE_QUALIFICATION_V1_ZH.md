# EnvSolve-pro P0 Baseline 资格测试 v1

## 目的

在选择任何 untouched P0 case 之前，本轮确认每种方法都能运行自身原生 loop，产生可审计轨迹，并到达
自身终止状态或 terminal-only EnvBench evaluator。诊断 case
`markqvist/reticulum@6ded42e` 已被消费，不提供效果证据。

## 已资格化方法

| 方法 | 原生 loop | 模型 | 有效终局 |
|---|---|---|---|
| Codex CLI | 通过单个持久容器 MCP 执行 Codex 工具循环 | `gpt-5.5`，high reasoning | Official 失败，`issues_count=18`；1,306 个总 error 不计分 |
| Repo2Run reproduced | Repo2Run 配置循环与命令历史 | `deepseek/deepseek-v4-pro` | Official 失败，`issues_count=18`；1,295 个总 error 不计分 |
| EnvBench raw ReAct | EnvBench FreeAgent ReAct loop | `deepseek/deepseek-v4-pro` | Official 失败，`issues_count=18`；1,295 个总 error 不计分 |
| 冻结 EnvSolve v1 | 来自 `07a208f` 的观测-约束-操作候选循环 | `deepseek/deepseek-v4-pro` | 原生终止失败：五次候选预算耗尽 |

Repo2Run 不被表述为未经修改的上游版本。当前 baseline 是上游提交 `65042aa` 加上可审计的兼容修复，覆盖
当前 CLI/模型调用、精确 revision checkout、ARM64 Docker 和依赖时间漂移。最后一项修复将
`pipdeptree` 固定为该上游提交时已经发布的 `3.1.0`；未固定安装会解析到缺少 Linux ARM64 wheel、要求
Cargo 的 `4.0.0`。

## 不计入算法结果的 Wrapper Failure

- Codex v1-v3 因 prompt 传输和 MCP approval 配置失败，没有形成有效工具 episode。V4 是首个有效原生
  episode；通用仓库完整性策略修复后，从其不可变轨迹重新 finalization。
- Repo2Run v1 在辅助镜像构建阶段失败，模型请求为零。V2 是首个有效 episode。
- Raw ReAct v1 因预算 wrapper 缺少 LangGraph `bind_tools` 而在零模型请求时失败。V2 完成模型 loop 后，
  Replay IR v8 错误拒绝只读点分测试模块管道。Replay IR v9 修复通用 finalizer，并在不增加模型调用的
  情况下复用已审计不可变轨迹。

这些尝试属于 harness 或兼容性证据，不属于方法失败。

## 诊断发现

Repo2Run 和 raw ReAct 最终都只保留 `pip install -e .`；它们验证了 import 或项目测试，但没有覆盖
EnvBench 要求的平台可选依赖。Raw ReAct 使用 16 次模型请求和 173,537 token，多次用不同过滤方式重跑
同一套测试；Repo2Run 使用 4 次请求和 27,118 token。Codex 执行 20 条成功容器命令，覆盖更广的测试和
文档检查，但仍遗漏同一可选依赖边界。

冻结 EnvSolve v1 展示了有用的状态化修复：先安装 `pytest`，再修复测试发现方式，最终暴露 unresolved
import constraints。但其 fixed verifier 将 unittest 风格仓库的 pytest exit 5 当作失败，前四次候选主要
消耗在到达 verifier；第五次才发现真正缺失模块，随后耗尽原生五候选上限。

## Gate 结论

四种方法均已完成操作资格测试。这不构成公平性或效果结论。P0 现在可以选择五个 untouched development
case，保留每种方法的原生 loop；token 和美元只报告为资源指标，不作为成功阈值；零信息基础设施失败与
方法结果分开统计。
