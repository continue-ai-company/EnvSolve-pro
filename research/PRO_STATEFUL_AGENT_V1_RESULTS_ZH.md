# Stateful Agent V1：已消费机制实验结论

## 范围

本实验只使用两个已经消费过的 EnvBench 开发仓库，用来检查机制是否真的工作，不能支持 held-out、
泛化或榜单结论。两组都使用 Codex CLI 与 `gpt-5.5`，获得相同的公开可执行目标、开放累计 Bash
接口，并且在线过程中都看不到官方 evaluator 结果。

## 结果

| Case | Raw history | Structured state | 科学裁决 |
|---|---:|---:|---|
| Lark | Official Pass，1 轮 | Official Pass，1 轮 | 两次都有效 |
| micropy-cli | Official Pass，1 轮 | Official Pass，1 轮 | 两次都违反来源一致性 |

官方汇总是 `4/4`，但按更严格的科研契约，只有 Lark 的两个位置属于有效仓库复现。micropy-cli 的两份
程序都把旧版 `micropy-cli` distribution 加入 `PYTHONPATH`：`micropy.cli` 来自目标 revision 之外，
其余 `micropy` namespace 来自当前 checkout。Fresh replay 只证明这个混合来源环境可以重复执行，
没有证明目标 revision 本身被一致地部署。

## V1 实际检验了什么

四个 episode 都接受了第一个候选，没有候选拒绝，也没有任何可执行目标失败进入第二个模型 session。
因此唯一一次操作之前，结构化 goal-obligation frontier 还是空的。这轮检验了强交互操作层和终局重放
管道，却没有真正触发所提出的结构化修复机制。

Lark 配对证明开放 Agent 可以生成合法的纯环境程序。单次 structured run 使用的命令和 token 少于
raw history，但一对随机样本不能支持效率结论。micropy-cli 两组都选择相同捷径，说明问题位于共享
验证契约，而不是由某一种状态表示诱导。

## 科学决策

`stateful-agent-v1` 作为冻结诊断 baseline 保留，但不能认定为已经合格的 EnvSolve-Pro 方法。下一版只
做三个最小改动：

1. 在第一次模型操作之前执行两组共享的只读目标探针；
2. 拒绝外部搜索路径覆盖目标 checkout 已提供的顶层 namespace；
3. 在 verifier 控制的检查前恢复可信 shell 不变量。

V2 必须先在已消费数据上证明：不合法的第一候选会变成结构化观测，并改变后续操作。通过这个机制门
之后，才能打开 repository-disjoint 的新开发 batch。
