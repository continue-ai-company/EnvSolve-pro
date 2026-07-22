# P5 因果约束前沿配对 V1：诊断结果

## 结论

P5-v1 不是一个有效的效果实验。三个 pair 都没有得到两条测量合格的终局结果，因此无法识别 flat 与
causal 的成功率、根因闭合或效率差异。预注册继续门槛未通过，6 个 episode 全部不能进入后续成功率表。

这批数据仍然有价值，因为它在消耗新 Dev case 前证伪了三条测量假设：3 个 episode 因依赖获取
read-timeout 被网络删失；2 个因宿主审计跟随只在容器内有效的虚拟环境解释器链接而结束；1 个候选通过
shell 控制流让 import probe 没有运行。

## 三层诊断

**观测层。** 网络失败必须删失，不能记作算法失败。shell exit code 为 0 不等于固定后置检查真实运行。
repository effect audit 必须识别容器创建的 symlink，而不能在宿主文件系统中解析其目标。

**约束层。** V1 会在下一候选没有重复同一错误时移除 runtime root。对于部分可观测系统，“沉默”不是
反证；只有相关 verifier 通道更新鲜的事实证明约束满足，根因才能退出前沿。V1 还没有保存模型当时实际
看到的前沿，因此事后无法精确归因。

**操作层。** 动作空间继续保持开放，但候选必须把控制权交还 verifier。它是执行契约，不是封闭操作
词表。

## 机制信号

信号值得继续验证，但不能计分。LangGraph 的 flat 条件先围绕 Rust 和 maturin 修补，直到候选 5 才达到
经 verifier 观察的兼容 Python runtime。causal 条件的候选 1 暴露 PyO3 前沿后，候选 2 明确指出
Python 3.13 超过 PyO3 的 3.12 上限并选择 Python 3.12。Nonebot2 在另一个仓库独立复现了这一响应，
候选 2 选择 Python 3.12 conda 环境。两条 treatment 随后都被测量问题或网络截断，所以它们只证明强
模型能够消费这种表示，不证明成功率或闭合更好。

## V2 边界

V2 只修改最小通用测量语义：根因持久化、候选完成标记、宿主安全的虚拟环境审计，以及模型可见前沿的
精确哈希。模型、verifier 目标、开放程序接口、候选保留、case 集合与 terminal-only Official evaluator
边界保持不变。V1 与 V2 结果永远不能合并。

机器可读记录位于
`experiments/validations/pro_p5_causal_frontier_paired_v1_results.json`。
