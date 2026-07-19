# Typed Replay IR v7 与 Complete Candidate v4

## 目的

本次修订在任何确认性实验前关闭两个通用 candidate-language 缺口。它只改变可执行命令覆盖与
runtime 绑定，不改变约束求解器、verifier、模型、预算或 benchmark evaluator。

Replay policy 标识：`typed-replay-ir-v7`。

Complete-candidate policy 标识：
`complete-candidate-v4+typed-replay-ir-v7`。

## 相对 v6 的变化

第一，受限的 PDM 依赖变更被接纳为 Python package-install action。允许形式是
`pdm install`、`pdm sync` 及其 `python -m pdm` 变体。任意 PDM script、发布、dry run、
未知子命令、shell substitution 和控制流仍被拒绝。

第二，candidate validation 为项目虚拟环境赋予语义身份。创建与激活都必须解析到项目根目录的
`.venv` 或 `venv`，并且激活必须发生在创建之后。类似
`cd tools && python -m venv .venv` 的命令不能只因为字符串同样以 `.venv` 结尾，就与项目根目录
激活错误匹配。

## 泛化边界

规则只检查命令语义，不包含仓库、package、module、benchmark split 或 evaluator outcome。PDM
支持来自公开 package-manager 接口，虚拟环境绑定来自有效路径身份。已消费的 Q5 Giskard 轨迹
只用于只读验证：此前被拒绝的 PDM candidate 现在能进入可执行语言；轨迹不会重跑，也不提供
effectiveness estimate。

## 验证

完整 v6 corpus 继续生效，v7 delta 增加 PDM install/sync 正例以及 run、publish、dry-run 负例。
Candidate 测试覆盖创建/激活顺序、路径错配、工作目录 alias，以及绑定项目环境内的 PDM 安装。
冻结时全量测试为 `343 passed, 1 skipped`，真实 fresh-container Docker integration 单独通过。
