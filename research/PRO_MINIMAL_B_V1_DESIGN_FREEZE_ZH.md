# EnvSolve-Pro Minimal B v1 设计冻结

日期：2026-08-04

## 决策

EnvSolve-Pro 下一版只冻结一个 treatment：

> 强 Agent 保持一个连续推理 session 和一个持久构建环境，并且可以反复把完整 bootstrap
> 程序提交到独立的干净环境验证。每次重放结果都返回同一个 Agent session。

这是语义设计冻结，还不是源码冻结。最小机制通过单元测试和真实 Docker 集成测试后，再生成绑定
源码、prompt、工具 schema、镜像、模型、case 与分析代码哈希的 implementation freeze。

## 三层边界

### 观测层

Agent 观察普通终端结果和每次干净重放的原始结果：候选校验、bootstrap 退出状态、公开可执行目标
报告、仓库 effect audit、环境身份和基础设施状态。Official evaluator 输出永远不进入 session。

### 约束层

Minimal B 只执行公开可执行目标、共享候选契约和仓库完整性边界。它不维护派生约束账本、
compatibility frontier、包知识体系、假设图或跨尝试语义总结。

### 操作层

同一个强 Agent session 通过开放终端控制一个持久构建环境，并可反复调用
`submit_and_replay`。重放失败后，证据返回原 session；重放通过后，认证本次提交的精确程序。

## 冻结在线循环

1. 创建一个干净 checkout 和一个持久构建容器。
2. 启动一个 Agent session，向其提供仓库、公开目标、候选契约和开放终端工具。
3. Agent 在共享合法性边界内自由检查、安装、诊断和修改环境。
4. Agent 调用 `submit_and_replay(program)` 时，先校验完整、自包含的程序。
5. 使用相同基础镜像和 benchmark 声明的前置条件创建独立的新 checkout 与容器。
6. 在其中执行程序、公开目标和仓库 effect audit。
7. 释放重放环境，并把有界原始证据返回同一个 Agent session。
8. Fail 或 Unknown 后继续；只有精确程序通过一次干净重放才成功停止。
9. Agent episode 结束后才运行 Official evaluator。

持久构建环境与每个重放环境必须不同。重放不能修改构建环境。最终返回脚本的哈希若与已认证脚本
不同，则拒绝结果。

## 明确排除

以下机制不属于 Minimal B v1，默认必须关闭：

- 结构化状态或约束投影；
- checkpoint、分支、回退或 frontier search；
- 模型生成的假设调度；
- action-level 后置条件准入；
- 跨 session 或跨 case 记忆；
- bootstrap 最小化或资源感知搜索；
- 仓库、包、模块或 case 特定规则。

它们以后只能作为冻结 Minimal B 接口上的正交 treatment。任何机制都不能通过 prompt、隐藏工具行为
或分析阶段候选选择暗中进入 control。

## 受控比较

主要因果配对为：

- **A，强 goal-aware Agent：** 一个连续 session 和持久构建环境，结束后只做一次不会返回结果的
  clean replay；
- **B，Minimal B：** 模型、prompt 前缀、终端、构建环境、公开目标、镜像和安全上限均相同，唯一
  增加的是可在线调用、并把结果返回活跃 session 的 clean replay。

唯一预期 treatment 差异是 clean replay 是否作为在线工具。Official Pass@1 是主指标。重放修复成功、
重放次数、wall-clock、命令数、token、峰值内存、磁盘增长和网络字节是描述性次指标。Token 和价格
不是停止成功求解的预算；只有宽松安全上限可以终止失控执行。

## 实现冻结门槛

打开任何新的效果 case 前，代码必须证明：

1. 同一个模型 session 能经历多次重放失败后继续工作；
2. 每次重放使用新的环境身份和干净 checkout；
3. 重放证据通过工具返回，且不泄漏 Official evaluator；
4. 重放不改变构建环境；
5. 只能接受哈希与 clean replay Pass 完全一致的脚本；
6. Fail、Unknown、基础设施删失和 Pass 保持独立；
7. 所有排除 treatment 均不存在或保持关闭；
8. 冻结 EnvSolve 与强 Agent baseline 的原有行为不变。
