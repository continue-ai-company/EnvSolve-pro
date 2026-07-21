# EnvSolve-pro P2 主导矛盾结果 v1

## 结论边界

冻结的 P2 已完成 6 个 metadata-only Dev case、4 种方法、共 24 个实验位置。P2 只用于诊断。
由于 Codex、Repo2Run 以及两个 raw ReAct 位置受到 adapter 或完整性审计删失，本批不能估计方法效果。

Official Pass 共两次：EnvSolve-pro 通过 `ansible-zuul-jobs`，raw ReAct 通过 `heltour`。它们只能
作为机制案例，不能被写成有效的 1/6 对比。

## 主导矛盾

三个仓库出现了同一个确定性的 EnvSolve 失败：候选执行返回零、effect boundary 有效，但只要内部
约束仍有残余，系统就不输出任何终局候选。

| 仓库 | 最佳完整候选 | Active | Satisfied |
|---|---:|---:|---:|
| `democracyclub/uk-polling-stations` | 5 | 693 | 42 |
| `sphinx-contrib/spelling` | 5 | 2 | 36 |
| `roboflow/supervision` | 3 | 29 | 44 |

主归因是**约束层**：部分可观测的内部证据被硬化成了精确终局判断。次归因是**操作层 finalization**：
搜索预算结束后，所有可重放候选都被丢弃。该模式满足预注册的方法特定例外：至少三个仓库、直接轨迹
证据、确定性原因，以及与仓库无关的干预方案。

最小干预是区分 `certified` 与 `admissible`。完全认证的候选仍立即停止；否则 EnvSolve 按残余结构化
约束保留已完整执行、完整性有效且退出码为零的最佳候选，在搜索结束时以 `uncertified` 输出。内部目标
仍记录为 `blocked`，Official evaluator 仍只在 episode 结束后运行一次。这既不改变成功标准，也不把
官方反馈泄漏进在线 loop。

## 为什么先做这个机制

`cellrank`、`heltour` 和 `supervision` 还共同暴露了 runtime、lockfile、依赖与平台闭包问题。但它需要
更大的状态与操作设计。最佳候选保留的证据更直接、实现更小、预测更容易检验，因此按奥卡姆剃刀先
推进它；runtime closure 只冻结为次级假设。

## Baseline 有效性

- 5 个 Codex 位置因 `container_exec` 成为 GPT-5.5 保留工具名而在行动前失败；另一个表现出较强部署
  能力，但被构建产物的完整性误报删失。
- 4 个 Repo2Run 位置在空响应后崩溃；旧的 `inner_commands.json` 还可能让崩溃看起来像产生了候选。
- 两个 raw ReAct 位置被合法生成文件的完整性误报删失。

批次结束后已修复 Codex 工具名、Repo2Run 单次输出隔离、空模型内容重试，以及项目根命名空间解析。
这些修复不追溯改变冻结 P2 结果；任何比较结论都必须来自新的有效 baseline run。

## 下一道门槛

先在三个已消费诊断 case 上验证预测的输出变化，再预注册至少 5 个新 Dev pair，对比开启和关闭
admissible candidate retention 的 EnvSolve-pro。只有未见 case 的 paired terminal outcome 才能支持
效果声明。
