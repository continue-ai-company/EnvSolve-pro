# Typed Replay IR v5 中文说明

## 目的

Typed Replay IR 将求解器成功执行过的 shell 轨迹转换成最小、可审计的环境
引导脚本。分类只依据 shell 语义和环境状态效应，不依赖仓库身份、榜单划分或
评测结果。

策略标识：`typed-replay-ir-v5`。

## 语义契约

每条成功的源命令必须得到且只得到一种处理：

1. `action`：表示一个或多个已证明的环境状态变化；
2. `drop`：证明整个表达式对环境重建没有状态影响；
3. `reject`：当语法、效应或控制流无法被安全表示时，关闭式拒绝。

被拒绝的源文本绝不会直接复制进回放脚本。

## 相对 v4 的变化

Round2 discovery 在四条相互独立且审计有效的 EnvSolve v0 轨迹中暴露了同一
表示错配：代理使用常规的 `eval "$(pyenv init -)"` 激活 shell，固定验证器
已经通过，但 v4 因不支持任意 `eval` 而拒绝这条成功命令。

V5 只增加一条与 benchmark 无关的语义规范化规则：

- 精确的 `eval "$(pyenv init -)"` 或 `eval "$(pyenv init --path)"`，允许两种
  shell 引号，规范化为 `export PATH="$(pyenv root)/shims:$PATH"`，效应类型为
  `runtime_configure`。

源命令中的 `eval` 不会被回放。规范命令仅在双引号内执行白名单查询
`pyenv root`，再通过 pyenv shim 目录暴露选定运行时。其他 `eval` 表达式、
其他程序、未知的 `pyenv init` 模式以及一般命令替换仍然拒绝。

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

机器可读语料为 `tests/fixtures/replay_ir_v5_cases.json`，包含完整 v4 语料、
pyenv 正例以及任意 `eval` 和未知 pyenv 模式的负对照。v4 产物与 Round2 原始
结果保持不可变。只有聚焦测试、完整 harness 测试和新 freeze 全部通过后，
v5 才能用于单独预注册的反事实回放实验。
