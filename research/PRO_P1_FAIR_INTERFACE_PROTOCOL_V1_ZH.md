# EnvSolve-pro P1 公平接口协议 v1

## 研究问题

能否在不使用封闭命令词表改变行为的前提下，把部署方法在原生环境中的成功
等价地传递到终局评测器，同时守住任务安全与仓库完整性边界？

P0 暴露了两类不能混为一谈的问题：

1. **表示损失：** 一个原生成功的操作，仅仅因为事后 parser 不认识其 shell
   写法而被拒绝或删除。
2. **状态不一致：** 生成环境或内部验证环境缺少评测器在 bootstrap 前创建的
   工作区产物，导致候选在更容易的前置条件下通过。

P1 先修复测量接口，此阶段不主张算法效果更强。

## 接口定义

### 开放候选程序

提交物是完整 Bash 程序，而不是封闭动作语法中的序列。某种 shell 写法不再
自动构成无效证据。程序从项目根目录被 `source`，与 EnvBench 一致。安全边界
由脚本大小、执行时间、全新容器，以及不挂载宿主凭据和宿主控制接口共同保证。

### 全新执行与效果审计

每个 EnvSolve 候选都在新的 checkout 和容器中执行。接受候选必须同时满足固定
可执行后置条件和事后效果审计：目标 revision 不变、tracked 仓库文件不变、
不注入 untracked 可导入文件或依赖配置文件、adapter 声明的前置产物仍然存在。
命令 schema 可以用于总结效果和定位失败，但 schema 是否覆盖某条命令不再是
正确性条件。

### Adapter 声明前置条件

benchmark adapter 声明 bootstrap 前已经存在、但不包含评测结果的工作区状态。
EnvBench Python v1 包含 `build_output/`，因为官方 build 脚本会先创建它，再
`source` 候选。内部验证必须物化相同状态。官方 evaluator 仍然只能在 episode
结束后调用一次。

### Baseline 轨迹传递

EnvBench raw ReAct 遵循上游规则：按原顺序保留成功命令，注释或省略失败命令，
只迁移原生项目根路径。Repo2Run 还需要编译其显式 sandbox 控制动作，并捕获其
文档中声明的 Python 3.10 初始运行时。只读探测和 shell 复合命令不会因为不在
replay schema 中就被删除。

## 冻结预测

已经消耗的 P0 case 仅作诊断，可以在不增加模型调用的情况下重放。

1. Raw ReAct 的 `marimo` 和 `futaba` 不再仅仅因为 `mkdir`、复合环境替换、
   父目录探测或成功 Python probe 被 wrapper 拒绝。
2. Repo2Run 的 `futaba` 会保留其原生 Poetry 安装成功时使用的 Python 3.10；
   终局 Pyright 仍可能因为独立原因失败。
3. Raw ReAct 的 `importlib_metadata` 仍可能重放失败，因为它的原生 loop 没有
   观察到 EnvBench bootstrap 前的 `build_output/`。这支持状态不一致，而不是
   parser 损失。
4. 旧内部验证器接受的 frozen EnvSolve `importlib_metadata` 候选，在先物化
   `build_output/` 后不应再被接受。
5. 修改 tracked 源码、注入可导入文件或删除 adapter 前置产物的无仓库 fixture
   必须被效果审计拒绝；正常生成的环境产物应继续允许。

## 通过条件

只有当合成测试建立安全边界，并且已消耗 P0 轨迹按预测区分表示损失和状态
不一致时，P1 才通过。结果允许为 Pass、Fail 或 Unknown，基础设施失败单独
censor。在实现、测试、prompt 和本协议全部冻结到 Git 之前，不打开新的 Dev
仓库。

P1 通过只说明执行接口公平，不说明 EnvSolve-pro 已经超过 baseline。
