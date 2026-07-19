# EnvSolve v0 错误分析协议

## 目的

EnvSolve 的机制必须来自已观察失败结构，而不是先搭架构再组织叙事。因此 Round 0 在选择
任何 EnvSolve v0 机制前，只分析已经消费的 same-backbone FreeAgent Dev-5 trajectory。
本轮没有模型请求、仓库执行、official verifier 调用或 held-out 检查。

## 分析单元

分析器从模型 tool call、声明的 reason、对应 tool output 与权威 command-history exit code
重建每个 bash 决策。它记录 command 与规范化 output 哈希、动作类别、历史精确尝试、历史
失败、相同输出失败，以及精确重试是否最终恢复。tool call 与 command history 不一致时
fail closed。

第一个 artifact 只量化症状：不从 exit code 推断根因，不标注 infrastructure failure，
不选择 EnvSolve 机制，也不预设重复命令是不合理的。

## Round 0 结果

五条 trajectory 共执行 83 个命令，出现 12 个非零退出。6 个命令精确重试了此前失败的
同一命令，且全部来自 Poetry；六次规范化 output 哈希均不相同，第六次最终 exit 0。
模型 reason 明确提到网络 timeout、网络间歇性和下载逐步推进。

这构成“无条件禁止失败命令重试”的反例。当前证据支持在 trajectory schema 中保留 retry
progress，但还不能证明 retry control 是跨仓库主要矛盾，也不足以引入算法机制。下一步是
最小端到端 EnvSolve v0 runner；只有它在 blinded development cases 上产生的自身 trajectory，
才是选择 EnvSolve 机制的有效依据。

机器可读结果位于
`experiments/validations/envsolve_v0_round0_freeagent_trajectory_analysis.json`。

## Round 1 transport 资格验证

第一批冻结配对实验完成了 10 个 process attempt，但 v0 graph 写入空初始状态，导致
LangGraph 在任何模型请求前终止。这是 transport 缺陷，不是环境求解失败。原批次保持
不可变。最小 state schema 写入未修改的 human message，并通过离线 graph execution
测试和一个已消费同 case 的资格验证：7/7 请求完成，旧异常没有复现，固定 verifier
被调用一次且通过。之后的 replay 拒绝不能用于准入算法机制。

## Round 2 结果

Round 2 冻结 5 个新的 outcome-blind case，并交替 condition 顺序。10 个 first attempt
与全部 audit 均完成，两种 condition 都没有 provider error。EnvSolve v0 使用 67 次请求
和 665,867 tokens；FreeAgent 使用 123 次请求和 1,702,574 tokens，但两者都没有进入
官方评测。

4 条有效 v0 trajectory 各调用固定 verifier 一次并通过，随后都因完全相同的 replay
表示 `eval "$(pyenv init -)"` 失败。第 5 条 v0 trajectory 在仓库内创建 virtualenv 后
触发 repository integrity。重复的 pyenv 错误族因此满足预注册门槛：至少 2 个 case，
且构成可归因 v0 失败的 plurality。

准入后的处理被明确归类为基础设施修复，而不是 EnvSolve 算法。Typed Replay IR v5
只把精确 pyenv 初始化替换为显式 shim-path runtime action；任意 `eval`、命令替换和
无关工作目录效应仍然拒绝。全套 228 tests 通过；只读重蒸馏恰好解锁 4 条触发轨迹中的
2 条。

对这两条轨迹的官方反事实评测均未通过。Pyfirebirdsql 的 bootstrap 完成，但出现 11 个
公开 issue 和 701 个 Pyright error。Islandora 在 bootstrap 下载包时超时，因此该记录
属于网络删失。这些结果证明，原地执行的 `pip check` gate 与 fresh replay 及公开目标
verifier 都不对齐。

## Counterexample Loop v2 状态

最小 clean-replay counterexample loop 已完成设计预注册，并在 benchmark-independent
core 中实现：

1. 把候选动作序列蒸馏为类型化 effect；
2. 在干净环境中通过可插拔 verifier contract 执行；
3. 将 bootstrap 与 goal-verifier 失败规范化为显式 constraint；
4. 先把这些 constraint 追加到 solver state，再允许下一次 repair。

第一版内容冻结覆盖 candidate/verifier protocol、事件顺序、fresh-environment identity、
fail-closed contract 和选择性 evidence admission。真实 case 前的合成审计发现，可解析但
彼此一致的 feedback 仍可能错误地允许下一 proposal，因此 v2 要求至少存在一个显式
constraint conflict。structured adapter 随后冻结到 v3：显式 verifier goal decision
保持不变，finding provenance 保留在类型化 evidence 中。EnvBench Finding Collector v1
将官方 missing-import diagnostic 绑定到 revision-owned source，同时把 P5 semantic
disposition 单独保存。一次只读 recorded qualification 恢复了 11/11 goal-active finding，
其中 5 条 semantic active obligation、6 条 guarded optional、0 Unknown；690 条非环境
Pyright error 没有进入 repair。9 个 core、10 个 adapter、7 个 collector 测试和全套
254 tests 均通过；没有新 benchmark execution、模型请求或 repository rule。

这仍不是已准入的 EnvSolve 机制。下一步把冻结的 loop、adapter 和 collector 接到匹配预算
的模型 policy，再预注册单独选择的未见 development batch。只有相对 v0 和 same-backbone
FreeAgent 在该 batch 上取得提升后，才能接触 Canary-20。
