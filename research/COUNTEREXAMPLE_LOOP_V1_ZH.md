# 反例驱动部署闭环 v1

状态：设计预注册；尚未用该机制观察任何真实 case 结果。

## 假设

相对 EnvSolve v0，唯一 treatment 是持久化 verifier 反馈。候选部署在全新环境中回放后，
可执行 verifier 必须通过，或返回类型化 counterexample evidence。失败证据必须先规范化为
显式 solver constraint 并提交到事件日志，policy 才能提出下一候选。

该实验检验：在模型、工具和资源预算相同的条件下，状态化反例累积能否提高环境构建效果。
它不检验 repository map、更长 prompt、重试策略，也不引入按错误类型拼接的 repair 规则集。

## 状态机

对第 `t` 轮候选：

1. `propose(S_t) -> C_t`：policy 接收完整重建状态。
2. `verify(C_t) -> O_t`：可插拔 executable verifier 在具有唯一执行标识的全新环境中评估候选。
3. 若 `O_t` 通过，记录 verification 并以 satisfied 终止。
4. 若 `O_t` 为 unknown、格式错误、环境复用或基础设施阻塞，记录后以 blocked 终止；不得把它当作 repair signal。
5. 若 `O_t` 失败，依次记录 candidate action、verification、failure 和类型化 counterexample evidence；
   使用已有 P3 constraint engine 规范化证据并持久化所得 constraint。
6. 只有第 5 步完成后，才允许 `propose(S_{t+1})`。失败无法形成任何 normalized constraint，
   或候选预算耗尽时，以 blocked 终止。

core loop 只依赖 candidate policy 与 executable verifier protocol。EnvBench、Pyright、Docker、
P5 collector 和模型供应商均保留在 adapter 后方。

## 不变量

- 每个已尝试候选都对应一条不可变 action 记录和一次 verification。
- Pass 必须同时满足 bootstrap 成功且没有 counterexample。
- verifier failure 不能只变成自由文本 prompt；证据和规范化 constraint 必须进入可审计状态。
- Unknown 或基础设施失败不得变成 package/runtime constraint。
- 不同候选轮次不得复用 environment identity。
- verifier 输出不可解析、失败不可规范化时必须 fail closed。
- 闭环不增加 repository-name 条件、import-to-package 猜测表或源码修改路径。

## 准入实验

实现测试只使用合成 policy 与 verifier。算法准入必须使用单独预注册、outcome-blind 且未参与
v0 设计或 Typed Replay IR v5 调试的新 development batch。

在同模型 backbone 和匹配预算下比较：

- same-backbone FreeAgent；
- EnvSolve v0；
- 只启用 Counterexample Loop v1 的 EnvSolve。

只有全部 artifact 审计通过、provider/基础设施删失被单独报告，并且该闭环在不降低 repository
integrity 的前提下取得高于 v0 的 official case completion，机制才准入。次要指标包括 clean-replay
完成率、verifier-counterexample 覆盖率、请求数、token、wall time 和候选轮数。单个 repository
不能为新增 repair operator 或 parser rule 提供依据。

## 明确不做

v1 不加入搜索树分支、rollback 选择、learned value function、repository retrieval、benchmark-specific
verifier 语义或自动网络重试。这些机制必须由独立错误证据支持，并分别做 ablation。
