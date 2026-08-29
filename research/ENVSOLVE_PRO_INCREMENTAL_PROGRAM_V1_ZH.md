# EnvSolve-Pro 增量可执行程序 V1

## 问题

Minimal B 让强 Agent 自由工作，最后再把成功的构建历史重写成一份 bootstrap。Bad4 证明失败有两种：
环境一直没有达到目标；或者环境已经满足公开目标，但始终没有变成可交付程序。Clean replay 只能在第二个
转换完成后工作，因此救不了“候选根本没形成”。

旧 handoff 在发现目标 Pass 后才要求模型现场汇总整份程序；incumbent 只在完整程序 replay 通过后才能
保留它。两者都没有消除“最后凭历史重写程序”这项独立任务。

## 最小算法

EnvSolve-Pro V1 让部署程序与环境一起生长：

1. `envbench_shell` 只负责观察和诊断。
2. `apply_environment_step` 执行一条由模型选择的持久环境操作。命令成功才原样追加到有序部署程序；失败
   命令不追加。
3. 每追加一步，harness 自动在活跃环境执行完整公开目标。
4. 目标一旦 Pass，harness 立即从目标初始状态执行已经存在的程序。Replay Pass 就用该程序结束；Replay
   Fail 则把可执行反例返回同一个 session，由模型再选择一个修复步骤。
5. Agent 也可以主动调用 `replay_current_program`，但交付时不再需要重写完整历史。

观测层是由持久操作触发的可执行测量；约束层是当前目标残差或 clean-replay 反例；操作层仍是可以选择任意
Bash 命令的强 Agent，并由它判断哪些成功变化属于部署。算法不增加 package 规则、封闭动作词表、容器
checkpoint、跨 case 记忆、固定观测周期、候选图或新的完整性 gate。

## 与旧方案的区别

| 方法 | 部署程序第一次出现的时刻 | 仍未解决的问题 |
| --- | --- | --- |
| Minimal B | Agent 在终点附近编写 | 可能一直不形成候选 |
| Verifier handoff | 观测到目标 Pass 后 | 仍要由 Agent 重建历史 |
| Certified incumbent | Replay Pass 后 | 第一份候选之前无法工作 |
| 增量可执行程序 | 每次成功环境操作时 | 对已经存在的程序做目标状态验证 |

这不是把所有命令机械记下来：观察、失败试验和诊断通过另一工具执行，由 Agent 明确选择是否进入程序。
它也不是封闭 planner，模型仍保留完整 Bash 操作空间。

## 开发期资格验证

确定性测试必须验证：步骤顺序持久化、失败命令不入程序、操作后自动观测、Pass 后目标状态 replay、
Fail 后同 session 修复，以及 replay Pass 后终止。这些测试只验证实现语义。

第一轮真实资格验证只使用已经消费过的“目标已满足但没有交付”case，检验机制能否在候选丢失前激活，
不估计泛化。完成固定的已消费资格验证后，才选择结果未知的比较 batch。Official Pass@1 仍为主指标；
机制激活、步骤覆盖率、replay 结果、部署完整性、请求、Token、时间、流量和存储分别报告。

## 证伪

如果 Agent 经常绕过 operation-linked 路径、增量程序无法表达真实成功路径、充分状态没有自动触发 replay，
或者固定配对实验没有成功率增益却提高成本，就否决该 treatment。由指标最小环境获得的 Official Pass 仍是
主指标成功，但不能当作部署完整性的证据。
