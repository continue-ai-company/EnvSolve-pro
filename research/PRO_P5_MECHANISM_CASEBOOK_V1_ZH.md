# EnvSolve-pro P5 机制 Casebook v1

## 范围

本文件记录三个已消费 Dev case 对因果约束前沿的机制价值。它不是效果表，也不能支持 held-out、显著性
或榜单结论。任何后续修改必须先抽象成仓库无关机制，通过 synthetic/regression test，并在新的冻结批次
验证；不得把仓库、模块或 provider 名称写成规则。

## 1. `langchain-ai/langgraph`

### 观察

- V2 causal candidate 2 的完整内部 frontier 有 10 个 module root、10,409 个字符，但模型可见状态被替换
  为整体截断包装；冻结分析器因此无法读取 `causal_roots`。
- 新的 root-first 投影在相同历史状态上只需 6,095 个字符，完整保留 10 个 root，omitted count 为 0。
- V2 flat 的独立轨迹多次观察到 Python 3.13 超过 PyO3 3.12 上限，但 8 个不同候选仍围绕 Rust、header、
  maturin 和 package patch 局部搜索，没有切换 runtime。
- V2 causal 最终内部认证，但 Official evaluation 仍有 1,701 个错误：1 个缺失 import 与约 1,700 个 API/
  type mismatch。Import closure 不是 dependency-version closure。

### 三层诊断

- **观测层：** 原始日志包含精确 runtime compatibility，但增长历史不能保证强模型把它当成主矛盾。
- **约束层：** causal compression 只有在模型可见投影保持结构时才存在；事后完整状态不能替代历史输入。
- **操作层：** 即使 import closure 完成，宽泛依赖安装仍可能产生大规模版本错配；这是 verifier 目标的下一
  个独立缺口，不能混入本轮表示修复。

## 2. `nonebot/nonebot2`

### 观察

- V2 causal 在 candidate 2/3 持续显示 `PyO3: Python 3.13 > 3.12`，candidate 3 切换兼容 runtime，随后
  Official Pass；同一历史状态的紧凑投影完整保留该 root。
- V2 flat 的 8 个候选都留在 Python 3.13，虽然日志反复出现同一边界；它不断增加 Rust、headers、maturin
  与环境变量，最终候选预算耗尽。
- 旧 verifier 在 Python 3.13 上把 `if sys.version_info < (3, 11): import tomli` 误判为 active obligation，
  迫使模型安装无必要 package。tuple guard 修复是通用控制流语义，不是 case rule。
- provider 在相同 seed 下并不严格确定；另一条 flat 轨迹曾切换 Python 3.11 后遇到网络超时。

### 三层诊断

- **观测层：** 精确信号已经存在，主要矛盾不是“没有日志”，而是 raw-history 中的注意力分配。
- **约束层：** 持续、短小、可修正的 root 可能帮助强模型退出局部搜索，但单 pair 不能证明因果收益。
- **操作层：** 动作空间保持开放；causal condition 没有强制 runtime operation，模型仍自行生成完整程序。

## 3. `conan-io/conan-package-tools`

### 观察

- 多个表面 import failure 可由运行时 `six.moves` missing name 聚合为一个 root，体现 surface-to-root
  amplification；causal 轨迹仍未在候选上限内关闭该 root。
- V2 flat candidate 8 的 active conflict 明显少于最终保留的 candidate 3，但存在 Unknown，因此按冻结
  admissibility 合同不能被保留。

### 三层诊断

- **观测层：** missing name 比每个失败 import path 更接近可执行原因。
- **约束层：** 正确压缩不等于 root 一定可解；它只减少重复症状并让失败可测。
- **操作层：** Unknown 与 active conflict 的候选排序可能影响 terminal release，但必须作为独立 consumed-
  case replay 消融，不能在本轮顺手改动。

## 4. 跨 Case 结论

1. 当前主要矛盾不是 exact duplicate candidate；V2 retry3 的候选脚本均不同。
2. raw-history 的主要失败是局部搜索与注意力分配：精确兼容边界存在，但没有成为稳定状态变量。
3. 结构化约束对强模型的合理角色是外部、可修正、root-first 的认知状态，不是封闭 planner。
4. 模型输入完整性是效果实验的前置条件；16 个 causal 决策中 1 个整体截断就足以否决 V2。
5. 下一批只检验 compact projection 的完整性；随后用已消费 case 的多 block 配对处理 provider 非确定性。

