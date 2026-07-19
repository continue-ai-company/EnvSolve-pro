# P6 预算校准协议 v1

## 范围

本协议不修改已经冻结的 Dev-5 资格实验，而是规定后续 held-out 主对比如何选择并解释资源预算。
只有 development-only 的资源轨迹可以参与预算选择；held-out 结果保持未打开。

## 资源向量

公平性由一组共享资源上限定义，而不是要求实际消耗完全相等：

- 相同模型、provider、seed 策略与价格快照；
- 相同 candidate、fresh environment 与 command 上限；
- 相同模型调用、输入/输出/cache token 与美元上限；
- 相同单请求、容器创建、命令、episode 与 evaluator 超时；
- 官方 evaluator 只调用一次；只有机器判定的基础设施删失允许一次预注册、原脚本不变的重试。

方法提前停止所节省的资源本身就是结果，不需要为了“花满预算”继续执行。

## 外部锚定上限

900 秒 command/container 与 1,800 秒 evaluator-process 上限对齐 EnvBench 执行边界；180 秒
模型请求和容器创建上限属于基础设施控制，单独报告。

## 预算前沿

1. 不改变现有上限，完成当前 outcome-blind Dev-5 资格实验；
2. 重建所有 audit-valid 资源轨迹，Fail 与 Unknown 均保留；
3. 将 EnvSolve 视为 anytime solver，固定报告 `K in {1, 3, 5}`；这些点在 held-out 执行前
   确定，不依据 development 或 held-out 成功率挑选；
4. 只运行一个最大 `K=5` 的因果有序 episode，其不可变前缀定义低预算状态：若第 `j` 次尝试
   达到 official Pass，则所有 `K >= j` 都成功；到 `K` 尚无 accepted candidate 则为 Fail；
   若第 `j` 次发生基础设施删失，则所有 `K >= j` 为 Unknown。官方评测仍然只在终局调用一次；
5. 在打开 Canary-20 或 Official-Test 前把 `K=5` 指定为排行榜配置，但论文报告完整前沿，
   不宣称 5 是天然最优常数。

每个 candidate 前最多允许连续两次可恢复 proposal failure，因此模型调用上限由控制流推导为
`3K`，不再沿用当前宽松的 30；provider transport retry 单独计数。

最终 token 与美元保险上限只由 audit-valid development 消耗决定：取 `K=5` 下最大观测消耗的
125%，分别向上取整到 10,000 tokens 与 0.01 美元。它们用于阻止失控，不被描述为自然常数。

episode wall limit 取基础设施最大值与 `K=5` 顺序执行推导上界中的较小者。每个 ledger 必须
finalize，确保终止 command 的时间被计入。

## 报告方式

主表报告冻结 `K={1,3,5}` 前沿上的 Official Pass@1，并单独标明 `K=5` 是排行榜配置；成本分析
对所有 Pass、Fail、Unknown 报告 fresh environment、模型调用、tokens、美元和 wall time。
任何预算都不能通过最大化 held-out 分数来选择。
