# EnvSolve-pro P3 候选保留资格验证 v1

## 目的

在消耗新的 untouched case 前，只验证一个由 P2 推出的最小机制：内部验证是部分证据，不是 terminal
oracle。EnvSolve 现在区分 certified 候选与已完整执行但未认证的 admissible 候选，并在搜索结束时保留
最佳 admissible 候选。

## 冻结诊断样本

对 `uk-polling-stations`、`spelling` 和 `supervision` 成对运行 retention 与 no-retention 条件。这三个 case
已在 P2 被选择和观察，只能验证实现行为，永远不能支持效果声明。两组使用相同提交、模型、seed、5 个
候选上限、open-program 接口、terminal-only evaluator 和 Python verifier v8；唯一开关是候选预算耗尽时
是否输出最佳 admissible candidate。

## 预测与门槛

冻结 P2 中，三个 case 都至少出现一个完整零退出候选，但最终都没有输出脚本。主预测是本轮至少 2/3
到达 terminal evaluation，并且至少比 no-retention 多到达 1 个 case。被保留候选必须标记为
`uncertified`，内部 goal 保持 `blocked`，携带 typed assessment，并通过仓库完整性审计。不预注册
Official Pass 预测。

若未通过门槛，在使用新 Dev case 前否决或修改该机制；若通过，只允许进入预注册的 unseen paired
experiment，不代表 runtime closure 或效果已经得到验证。
