# P6 约束到操作协议 V1

状态：机制已经实现；在任何新真实 case qualification 之前冻结。

## 1. 目的

EnvSolve 将环境部署分为四个接口：

1. 观测层：把发生的事情记录为不可变证据；
2. 约束层：推导现在缺什么、冲突在哪里；
3. 操作层：限制可以怎样改变环境；
4. 验证层：在全新环境中执行并检查完整程序。

本协议冻结最小的“约束到操作”边界。它不加入仓库特定的 module-to-package map，
也不检索其他 case 的经验。

## 2. Operation plan

`ConstraintOperationPlanner` 将每个受支持的 active hard conflict 确定性投影为一个
`OperationRequirement`。每项 requirement 记录：

- conflict domain 和 subject；
- 允许的 operation kind；
- source conflict ID；
- source constraint ID。

V1 的 domain 映射是：

| Conflict domain | 允许的 operation kind |
|---|---|
| runtime | 配置运行时 |
| package | 安装 Python package |
| capability | 安装系统 package |
| module | 安装 Python 或系统 package |

不支持的 domain 显式保留在 plan 中。Hypothesis 不产生强制 operation requirement。

## 3. Candidate guard

模型负责选择具体参数并提出完整、可重放的程序。创建容器前，
`constraint-operation-guard-v1` 将候选的类型化 action 与最近一个真正获得 verification
record 的候选比较。对于每项 operation requirement，新候选必须引入至少一个类型允许的
新 action。

Guard 拒绝会：

- 持久化为 action 与 failure event；
- 消耗 candidate 和模型预算；
- 不创建环境，也不消耗 command 预算；
- 不能成为执行证据。

Guard 只检查 action 类别与新颖性，不判断某个具体包名是否是正确修复。只有 fresh
execution 和 verification 才能确认结果。

## 4. 为后续工作保留的轨迹契约

不可变 event stream 必须能重建：

`source conflict -> source constraint -> operation requirement -> candidate
mutation -> guard decision -> fresh-environment verifier outcome`。

EnvSolve v1 只能读取当前 episode 的状态，不得使用跨 case 自然语言经验、总结、轨迹、
reward 或学习后的 policy update。这既保证第一篇论文对照干净，也保留：

- EnvSolve-RL 所需的有监督 state-action-outcome transition；
- 未来 Auto-EnvSolve 外层系统所需的 unsupported domain、rejected action 和 parser
  coverage 统计。

后续项目生成的 derived dataset 必须独立版本化，且不得改写 EnvSolve raw event。

## 5. 准入标准

1. 合成测试覆盖 conflict projection 和 guarded fresh replay。
2. 被拒候选不能被误当成真实执行历史。
3. 既有全量回归与 Docker integration test 通过。
4. 不新增 benchmark-owned feedback 或仓库特定 repair mapping。
5. 在 unseen-case qualification 前哈希实现、测试和双语协议。

