# P4E 仓库回放协议

## 目标

P4E 用于打通隔离的类型化修复与真实仓库执行。每次 bootstrap 或 verifier 输出都会
成为新证据；控制器据此分类约束状态，每轮最多应用一个经过验证的类型化修复，并从
干净 checkout 重新回放。产物中可以记录仓库身份，但 repair selection 不得根据仓库
身份分支。

P4 完成不等于隐藏全部静态分析诊断。Dev-5 case 必须进入以下可审计终态之一：

- `official_pass`：bootstrap 退出码为 0，benchmark 自有 issue count 为 0；
- `bootstrap_satisfied_verifier_open`：bootstrap 退出码为 0，剩余 verifier finding
  被保留为 P5 要处理的类型化 module obligation；
- `repair_exhausted`：所有受支持且有证据依据的修复均未通过独立 verification gate；
- `intrinsic_or_optional`：finding 被证明是平台条件、测试/文档/工具专用，或不属于
  项目声明的 metadata；
- `infrastructure_blocked`：执行未产生语义证据。

只有前两类满足 P4 的环境 bootstrap 目标。官方榜单成功仍严格使用冻结的 EnvBench
判定标准。

## Dev-5 审计

冻结的 deterministic 与 DeepSeek V4 Pro 运行均为已消耗的开发输入。EnvBench 的
Python evaluator 在 `issues_count` 中只统计 `reportMissingImports`；Pyright 总错误数
属于诊断证据，不是 P4 修复目标。

Agent run 的五个 case 中有四个成功 bootstrap。`pytest-xdist` 已官方通过；`gpkit`、
`reticulum` 和 `poetry` 完成 bootstrap，但仍有 module obligation；`inflect` 在 verifier
之前失败，因为 evaluator 创建的目录被 setuptools 当成第二个顶层 package。它是
P4E 第一轮回放目标。

## Round 1：verifier 自有工作区产物

只有同时满足以下条件，才能生成 `workspace_artifact_conflict`：

1. 失败诊断明确列出多个被发现的顶层路径；
2. 至少一个路径有 provenance 证明由 verifier 在 bootstrap 前创建；
3. 路径是相对的顶层非符号链接路径，且不受目标仓库版本控制；
4. mutation 前已记录内容哈希。

修复只能把证明确属 verifier 的路径临时搬到仓库外，执行不变的项目安装命令，然后
在 verifier 继续前恢复原路径。后置条件要求恢复后的内容哈希与修复前完全一致。
安装失败或恢复失败时，均不得提交 repaired fact。

## 迭代控制器

每次 clean replay 都记录仓库 revision、evaluator image、bootstrap script hash、动作
结果、规范化冲突、repair plan、独立 probe、官方指标和终态。遇到终态、不支持的
冲突、重复 state fingerprint、verification gate 失败或达到预注册轮数上限时停止。

后续 P4E 可以加入 module-to-distribution discovery，但候选名必须来自项目 metadata
或独立记录的 provider。禁止 import stub、源码修改、verifier 配置修改、宽泛 ignore
规则以及 case-specific package map。

## 完整性约束

- 仅可重复运行 Dev-5 和此前已消耗的开发扩展。
- Canary-20 与 Official-Test-100 保持未检查。
- 每次新 benchmark execution 必须先写预注册。
- P4E Round 1 不调用模型。
- 已冻结的 P0-P4D 源码和 manifest 保持不可修改。

