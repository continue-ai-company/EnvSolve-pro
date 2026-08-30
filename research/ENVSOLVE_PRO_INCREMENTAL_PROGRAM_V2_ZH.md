# EnvSolve-Pro 标注式增量程序 V2

## 为什么需要 V2

V1 给 Agent 两个相似的 shell 动作：一个用于诊断，一个用于持久修改。固定的已消费资格验证中，Agent
调用普通 shell 69 次，只调用程序操作工具 1 次；HARK 还通过普通 shell 完成了真实 editable install。
因此，V1 实际没有检验“增量构建程序”假设，因为它的操作界面没有自然激活。

V2 只改变这个界面。Agent 继续使用一个熟悉、可执行任意 Bash 的 `envbench_shell`，但每次调用必须声明
预期效果：

- `effect=inspect`：在构建环境执行，但不把命令加入部署程序；
- `effect=persist`：在同一环境执行，成功后把原命令追加到有序部署程序。

这个标注不是命令分类器或权限边界。Agent 在两种取值下都可以执行任意 Bash；harness 不推断 package，
也不覆盖 Agent 的选择。如果 Agent 错把必需操作标成 `inspect`，该操作仍可能丢失，我们把它记为语义
绕行，而不是用内置规则偷偷修正。

## 三层算法

观测层返回普通命令输出，并在每个成功 `persist` 后执行完整公开目标。约束层表示当前目标残差或 clean
replay 反例。操作层仍是同一个连续强 Agent，通过一个任意 Bash 通道工作，同时判断每个动作是否应进入
可重放程序。

公开目标一旦 Pass，harness 立即从目标初始状态重放累计程序。Replay Fail 返回同一个 session，由
Agent 再选择一个 `persist` 修复；Replay Pass 交付累计程序本身。观察命令、失败的持久尝试和被声明为
`inspect` 的命令都不进入程序。

V2 不增加 package 规则、命令过滤、checkpoint、跨 case 记忆、固定观测周期、候选图、新 hash 机制、
冻结 contract 或安全 gate。Minimal B 原有完整性边界和 clean replay 语义保持不变。

## 资格验证

V2 首轮复用 V1 的同三个已消费 case，只验证机制，不估计效果。报告 inspect/persist 次数、首次 persist
请求、成功记录步骤、人工审计的语义绕行、自动目标观测、replay 结果、交付程序一致性、到达时的 Official
结果以及资源。

只有真实部署修改能够自然使用 `persist`，且记录步骤后的充分状态能在同一工具回合触发 replay，才认为
界面通过资格验证。如果 Agent 仍把必需部署修改标成 `inspect`、成功持久命令没有被原样记录，或目标
Pass 没有触发 replay，就否决 V2。不能用这三个 case 声称成功率提升。
