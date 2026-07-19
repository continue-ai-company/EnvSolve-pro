# Typed Replay IR v6 中文说明

## 目的

Typed Replay IR 将求解器成功执行过的 shell 轨迹转换成最小、可审计的环境
引导脚本。分类只依据 shell 语义和环境状态效应，不依赖仓库身份、榜单划分或
评测结果。

策略标识：`typed-replay-ir-v6`。

## 语义契约

每条成功的源命令必须得到且只得到一种处理：

1. `action`：表示一个或多个已证明的环境状态变化；
2. `drop`：证明整个表达式对环境重建没有状态影响；
3. `reject`：当语法、效应或控制流无法被安全表示时，关闭式拒绝。

被拒绝的源文本绝不会直接复制进回放脚本。

## 相对 v5 的变化

预注册的 position-2 开发诊断暴露了一个内部表示不一致：v5 允许激活项目根
目录中的虚拟环境，却拒绝通过同一个受限虚拟环境直接执行包变更，例如
`.venv/bin/pip install ...`。

V6 只补齐这项已有抽象。它仅识别以下项目根相对位置中的 `python`、`pip`
及其带版本号变体：

- `.venv/bin/` 和 `venv/bin/`；
- `${PROJECT_ROOT}/.venv/bin/` 和 `${PROJECT_ROOT}/venv/bin/`。

任意路径不会被放行。绝对路径、嵌套虚拟环境、未知可执行文件、命令替换和
未类型化 shell 文本仍然拒绝。被接受的命令保留其受限可执行路径，确保包变更
作用于求解器选择的环境。

## 保持不变的安全约束

- 未分类 shell 文本不能进入回放；
- 每条回放命令都有类型化效应和源命令 provenance；
- 删除观测命令不能掩盖持久文件写入；
- 含歧义的 fallback 或顺序 mutation 控制流仍然拒绝；
- 危险的 import/path 环境变量仍然禁止；
- 项目路径只能从已记录的生成目录映射到新评测目录；
- 仓库完整性与 EnvSolve completion verifier 是 recorded redistillation 的独立
  前置条件。

## 验证与冻结

机器可读语料为 `tests/fixtures/replay_ir_v6_cases.json`，包含完整 v5 语料、
三个项目根虚拟环境正例和两个路径边界负对照。触发本次修改的运行继续作为
不可变开发诊断保留，不获得替代评测。只有聚焦测试、完整 harness 测试、真实
Docker 集成测试和新 freeze 全部通过后，v6 才能进入后续实验。
