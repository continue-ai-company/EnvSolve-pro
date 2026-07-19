# P6 约束操作层资格实验 V6

状态：在 Q6 选样、仓库检查或执行之前预注册。

Q4 与 Q5 永久保留为已消费的开发诊断。两批都有完整产物，但在修正后的 scientific contract 下都
不能估计 treatment effect：Q4 早于 Git baseline，Q5 还包含主机休眠造成的 wall-clock 超限。
它们的结果不会为 Q6 引入任何仓库、package、module 或 provider 规则。

Q6 是第一批必须满足完整 scientific-eligibility contract 的 operation qualification。每个 run
必须使用已提交且干净的源码 revision，与冻结 schedule identity 一致，保持在原始资源上限内，保存
没有异常间隔的完整 runtime heartbeat，通过独立 artifact audit，并且只能由确定性的 hash-chained
analyzer 汇总。

Treatment 保持不变。两种方法共享同一模型、两层 obligation verifier、仓库上下文、candidate
validator、fresh environment、预算和 terminal-only official evaluator。只有完整 EnvSolve 接收
constraint-derived operation plan 和 operation guard；control 接收不含 operation instruction 的同一
状态投影，并自由提出完整 candidate。

五个身份从 SHA256 冻结的剩余 171-case pool 中 metadata-only 选择，排序规则为
`SHA256(salt + NUL + case_id)` 升序。Case 顺序与 pair 内方法顺序使用独立 salted hash。任何 Q1-Q5
身份都不能复用。选样产物只由预注册驱动工具生成一次；源池漂移或输出已存在都会失败。

生成过程有累计 7,200 秒 wall-clock 预算；官方评测有独立冻结的 1,800 秒 process 预算；coordinator
使用 9,600 秒 episode 硬截止，其中包含阶段切换和清理余量。美元仍只是非绑定运营断路器，不是科学
资源变量。

只有 pair 的两个 run 都具备 scientific eligibility 且都有 official Boolean result 时，该 pair 才
进入配对估计。Infrastructure Unknown、host suspension、artifact invalid 或 official evaluation
不完整都会删失 pair，不能变成方法 Fail。共享机制缺陷会在完成当前 pair 后关闭 batch；五个已选身份
全部保持 consumed，Q6 内不允许修改代码。

Q6 只用于 development mechanism qualification，不能支持论文主效果 claim、选择最终预算，或改变
Canary/Official-Test policy。
