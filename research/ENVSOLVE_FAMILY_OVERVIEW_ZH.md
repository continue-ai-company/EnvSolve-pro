# EnvSolve 系列工作通俗总览

## 一句话概括

EnvSolve 系列研究的共同目标，是让 AI 能够可靠地复现和部署真实软件项目。

- **EnvSolve**：第一代可执行原型，验证三层闭环是否成立。
- **EnvSolve-Pro**：当前刷榜和投稿的核心算法。
- **Auto-EnvSolve**：未来自动发现并修复 harness 自身的问题。
- **EnvSolve-RL**：未来利用可执行轨迹把部署策略训练进模型。

当前研发只集中在 EnvSolve-Pro。后两项只维护数据接口和研究边界，不分散核心实验资源。

## 共同的三层架构

```text
观测层：环境里发生了什么？
    ↓
约束层：现在缺什么，冲突在哪里？
    ↓
操作层：怎样改变环境来解除冲突？
    ↓
在新容器中执行和验证
    ↓
形成下一轮观测
```

### 观测层

观测层记录可执行事实，包括命令输出、退出码、Python 与平台状态、容器身份、项目状态和公开验证器结果。
它不负责猜测解决办法。

### 约束层

约束层把分散的执行反馈整理为当前状态：哪些目标还没有满足，哪些条件互相冲突，哪些结论仍然未知。
它帮助模型记住问题，但不应替强模型规定具体命令。

### 操作层

操作层生成真正改变环境的部署程序，例如安装依赖、选择运行时、构建项目或配置环境。EnvSolve-Pro
保留完整 Bash 操作空间，让强模型能够使用新工具和新策略。

## EnvSolve：第一代原型

EnvSolve 首次把“观察、约束、操作、验证”的循环落成了可执行代码。它证明环境部署可以被建模为
状态化约束求解，而不只是 LLM 的自由命令试错。

第一代系统包含较多早期规则、结构化动作和实验设施。部分设计有助于可审计性，但也可能限制强模型，
或把表面错误误当成根因。因此它已经封存，主要承担两个角色：

1. 作为研究历史和可复现的旧基线；
2. 帮助判断 EnvSolve-Pro 的收益究竟来自哪里。

## EnvSolve-Pro：当前核心算法

EnvSolve-Pro 保留三层闭环，但对第一代系统做减法：

- 强模型仍然输出完整 Bash 程序；
- harness 保证反馈真实、状态可追踪、验证可执行；
- 约束表示负责整理目标和冲突，不把动作写死；
- 每个候选在 fresh container 中验证；
- 官方 evaluator 只在 episode 结束后运行，不能进入在线求解状态；
- 成功率是首要指标，token、时间和价格是描述性指标。

可以把 EnvSolve-Pro 理解为：**给强模型配置一个可靠的部署思考回路，而不是替模型写一套固定部署
专家系统。**

当前 execution-feedback-v3 又做了一次减法。失败的 bootstrap taxonomy 不再参与决策，只保留已经
有效的目标约束前沿，并解决两个由真实轨迹证明的问题：

1. 安装和构建命令不能把失败日志重定向到 `/dev/null`；
2. 候选已经执行完成，但其环境副作用导致公开目标进程崩溃时，应把这次失败反馈给下一轮，而不是直接
   终止整个 episode。

这两个机制都不规定模型应该安装哪个包，也不关闭 Bash 操作空间。

## Auto-EnvSolve：自动改进 harness

EnvSolve-Pro 解决“当前项目怎样部署”。Auto-EnvSolve 解决另一个层次的问题：

> 跑过大量项目后，能否自动发现 EnvSolve-Pro 自身的机制缺口，并产生经过验证的新 harness 版本？

它对应目前由研究者完成的外循环：

```text
冻结一批跨仓库轨迹
-> 统计主要失败机制
-> 提出一个最小通用修改
-> 生成反例和回归测试
-> 在未见 case 上比较新旧版本
-> 晋级或淘汰
```

Auto-EnvSolve 优化的是 observation parser、constraint transition、operation interface 和通用 verifier，
不是给某个仓库记住一条特例。它不能修改正在运行的正式评测，也不能根据单个 case 直接发布全局规则。

## EnvSolve-RL：把部署策略训练进模型

EnvSolve-RL 不负责修改 harness。它在一个冻结的 harness 中，使用 EnvSolve-Pro 积累的轨迹学习部署
策略。

每条训练 transition 至少包含：

```text
操作前状态与约束
模型实际看到的信息投影
候选部署程序
fresh-container 执行反馈
公开验证器结果
操作后状态
最终成功标签
token、时间和环境使用量
```

最终成功是主要 reward。finding 数量下降等中间信号只有在观测完整、作用域一致时才能作为 shaping
signal；网络失败和 provider 超时必须标记为外部删失，不能错误惩罚部署动作。

## 四项工作的边界

| 工作 | 主要优化对象 | 是否修改 harness | 是否学习模型 | 当前状态 |
|---|---|---:|---:|---|
| EnvSolve | 第一代部署闭环 | 是 | 否 | 已封存基线 |
| EnvSolve-Pro | 单个项目的部署求解算法 | 是 | 否 | 当前核心工作 |
| Auto-EnvSolve | 跨项目的 harness 版本演化 | 是 | 可选 | 后续研究 |
| EnvSolve-RL | 冻结 harness 内的部署策略 | 否 | 是 | 后续研究 |

## 数据如何复用

EnvSolve-Pro 不只保存最终 pass/fail，还保存不可变 raw event 和版本化 derived view：

- harness、policy、goal contract 和 projection 版本；
- 候选原始程序、规范化程序及修改记录；
- candidate lineage 和前后状态哈希；
- stdout、stderr、退出码和 fresh-container receipt；
- 约束变化、hypothesis、effect audit 和终止原因；
- 模型请求、token、时间和环境账本；
- 与在线状态隔离的官方最终标签。

同一份数据可以支持两类后续研究：

- Auto-EnvSolve 统计哪些 harness 机制在跨仓库轨迹上有效或有害；
- EnvSolve-RL 构造可审计的 state-action-observation-reward 数据。

## 最终关系

```text
EnvSolve-Pro 生成高质量、可执行、可审计的部署轨迹
        |
        +--> Auto-EnvSolve：改进 harness
        |
        +--> EnvSolve-RL：训练部署模型
```

长期目标是形成一套自进化环境对齐系统。但第一篇工作的判断标准很朴素：EnvSolve-Pro 必须先在
EnvBench 等真实项目复现任务上稳定超过强基线，并用严格的数据隔离和可执行实验说明为什么有效。
