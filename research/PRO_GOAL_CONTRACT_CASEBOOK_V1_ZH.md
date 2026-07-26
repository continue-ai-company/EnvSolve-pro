# EnvSolve-Pro Goal Contract Casebook v1（中文）

## 范围

本文档记录 goal-contract 系列在已消费开发 case 上的机制证据，只用于资格验证和调试，不是 held-out
效果估计，也不能并入榜单结论。

## 1. `jaraco/irc`（`c2`）

- `EnvSolve-Pro goal-contract-v1` 完成了生成与终局评测。
- Official Pass 为 true，bootstrap 退出码为零，计分 issue 为零。
- 该 run 证明通用 goal runtime、EnvBench adapter、候选释放和终局评测能够端到端兼容。
- 详细轨迹仍保存在 Spark；SSH 服务恢复后必须继续审计。在此之前，该 case 不能说明是否发生了失败后
  修复。

## 2. `censys/censys-python`（`c10`）

### 第一条机制轨迹

第一个候选执行 `poetry install` 并激活对应环境。公开可执行目标随后返回唯一 Fail finding：
`docs/conf.py` 中缺少 `sphinx_rtd_theme`。约束层接收了带 provenance 的 module requirement 与 negative
fact。第二次模型调用生成新的完整程序，额外安装 `sphinx_rtd_theme`；新的 fresh environment 同时通过
内部目标与 Official evaluation，计分 issue 为零。

这条轨迹闭合了预期的 case 内链条：

```text
候选 -> 可执行目标 Fail -> typed obligation
-> 修订后的完整程序 -> 可执行目标 Pass -> Official Pass
```

### 状态一致性修复

事后审计发现，目标已经 satisfied，但历史 requirement 在快照中仍标记为 active。它没有影响候选选择和
Official 结果，但违反算法状态契约，也会污染未来轨迹学习。现在 goal evidence 带有 contract-specific
evidence scope；Pass 只退休同一 scope 的约束，其他 verifier 证据保持不变。该修复通过全量回归，并在
新的 c10 运行中确认旧 requirement 与 fact 最终均为 `superseded`。

### 同模型受控配对

`envsolve-pro-goal-aware-raw` 与实验组使用相同模型、公开目标、verifier、开放程序接口、fresh
environment、候选保留和执行限制，但不向模型展示 `constraint_conflicts`、active requirement 或 causal
frontier；模型只看到原始候选和 goal report。

两个方法都在第一轮失败、第二轮安装 `sphinx_rtd_theme`，并获得 Official Pass。单次随机配对结果为：

| 方法 | 尝试数 | Official Pass | 总 token | Wall-clock |
|---|---:|---:|---:|---:|
| goal-aware raw history | 2 | 是 | 15,314 | 223.5 秒 |
| explicit goal constraints | 2 | 是 | 17,494 | 361.1 秒 |

显式状态组还额外安装了不必要的 `attrs`。这些数值只作描述，不构成效率结论。

## 3. 决策

1. c10 支持可执行目标可见性与迭代修复机制。
2. c10 **不支持** typed constraint 可见性的额外增益；强模型仅凭原始 goal report 也能完成修复。
3. raw-history baseline 必须看到完整的有界 goal report，不能让 finding 淹没在安装日志中。verifier 现已
   保留原始报告，并为其分配更大的模型可见空间。
4. 下一组已消费配对必须检验多 finding、跨轮持久化或反馈压缩；下两个机制 case 为
   `astropy/extension-helpers`（`c15`）和 `nonebot/nonebot2`（`c16`）。

## 4. `astropy/extension-helpers`（`c15`）

### 无效诊断配对

两个方法第一轮都观测到四个 missing-import finding：`pkg_resources`、`numpy`、
`helpers_test_package` 和 `helpers_test_package.compiler_version`。显式状态组的第二个候选已经解决其中
三个，下一次可执行报告只剩 `pkg_resources`；但约束状态仍把已经消失的三个 requirement 标成
violated。原实现只会在整体 Pass 后退休一个 contract scope，没有区分穷举式 Fail 快照与部分证据。

这是状态机缺陷，不能用来支持或反对显式约束。raw-history 组也尝试了多个无效方案，包括过旧的
`setuptools` pin；发现缺陷后已中断这组配对。两个 run 均标记为 `invalid-for-comparison`，禁止进入
效果表。

### 最小修复

goal report 现在声明 `finding_set_complete`。完整报告可以退休同一 scope 中没有再次出现的旧约束；
部分报告只能增加或细化证据，不能用“未出现”证明问题已经解决。EnvBench 的完整 Pyright 扫描返回
complete finding set，能力缺失导致的提前结束返回 partial set。合成测试覆盖两种状态转移；全量测试为
517 passed、2 skipped、75 subtests passed。

### 完整性事故与 protocol v2

状态修复后的第一条 explicit-state 轨迹在第五个候选获得了 Official Pass，但最终程序在 `/tmp`
中直接创建空的 `helpers_test_package` 模块，再通过 `PYTHONPATH` 暴露它们。这违反了禁止伪模块的
完整性规则，因此该结果只能诊断，不能用于效果比较。确认完整性缺口后，对应 raw-history run 已中断。

protocol v1 的边界不一致：文本笼统禁止路径注入，开放程序 validator 却允许合法的仓库与安装路径配置。
protocol v2 改为允许真实环境路径配置，同时禁止合成导入产物和对可执行目标的 shadow。新的小型、
benchmark-independent 准入守卫会拒绝 shell 直接创建或复制 `.py`、`.pyi`、`.pth`、`.so` 等可导入
产物，但保留正常的 package/build 工具以及临时 `setup.py` 构建驱动。旧作弊候选已被新守卫准确拒绝，
定向与全量回归均通过。

### 约束路由的源码证据与保留锚点

通过完整性检查的重跑又暴露了两个问题。第一，目标 finding 只指出缺少哪个模块，却没有暴露解释该模块
应如何产生的仓库局部代码。第二，后续候选可能解决新出现的 finding，同时忘掉早期候选已经满足的依赖。
这两个问题来自部分可观测性，而不是 shell 操作空间不足。

`goal-contract-evidence-anchor-v1` 增加了两个小型状态机制：

1. 对每个 active finding，把其精确源码位置和相关 subject 出现位置的有界只读视图路由到约束层；
2. 把当前最好的、完整执行且通过完整性检查的候选保留为显式锚点，要求操作层在合并后续修复时保留
   该锚点已经成立的设置。

操作空间仍然是开放 Bash 程序。源码证据由当前可执行 finding 定向选择，不是无边界浏览工具；锚点是
有执行证据支持的状态，而不是手写部署配方。

### 有效机制结果

`pro-goal-contract-evidence-anchor-v1-c15-mechanism1` 同时通过内部目标和 Official evaluation，计分
issue 为零。关键轨迹如下：

- candidate 4 建立了包含四个 finding 的有效基线；
- candidate 5 解决 `numpy` 并成为保留锚点；
- candidate 6--8 尝试受保护配置或合成导入产物，被完整性边界拒绝；
- 约束路由的源码证据让 candidate 9 找到项目真实的 `_extension_test_package` 构建 helper；
- candidate 10 修正该构建路径，把完整 finding 集缩减为 `pkg_resources` 和 `numpy`；
- candidate 11 将有效构建修复与锚点中的依赖合并，在全新环境达到零 finding。

该 run 使用 11 个候选、13 次模型请求和 261,722 tokens。这些只是开发阶段描述量，不是效率结论。
它证明源码路由与状态锚点能够在不伪造模块、不抑制目标的前提下闭合这个困难机制 case。由于 c15
直接参与了两个机制的设计，它仍是已消费开发证据，不能用于估计泛化效果。

下一组受控配对使用已消费的 `nonebot/nonebot2`（`c16`），在保持公开目标、源码证据、保留锚点、
操作接口、模型和限制相同时，对比显式约束与 raw history。

## 5. `nonebot/nonebot2`（`c16`）

### 基础设施删失

第一次显式状态尝试完成一个候选后，第二次 OpenRouter 请求在 TLS 读取中停留超过 20 分钟。同期
OpenRouter 健康接口可正常响应，账本没有记录 response 或 request error，也没有产生第二个候选。
该进程被中断，本次 run 标记为 `infrastructure-censored`，不算算法失败；重跑使用新的 run id。

### 受控配对

两个方法都使用 `deepseek/deepseek-v4-pro`、protocol v2、相同的可执行目标、约束路由源码证据、
保留 admissible 锚点、开放 Bash 接口、fresh environment 和仅终局可见的 Official evaluation。
唯一预期差异是模型可见状态：显式 active constraints 对比有界 raw goal history。

显式状态重跑首先在 Poetry 配置阶段失败。第二个候选改用 pip，暴露 35 个 finding，但它们只对应
`pytest`、`nonebug` 和 `tomli`。candidate 3 安装仓库内的本地 test package 和剩余依赖后通过。

raw-history 的第一个部分完成的 Poetry 配置暴露 51 个 finding。candidate 2 将其减少为 18 个 optional
driver finding。随后一次模型响应违反候选输出 schema，在执行前被拒绝；下一次响应把剩余 driver 与
本地 test package 合并到 candidate 3，并获得通过。

| 方法 | 执行候选数 | 模型请求数 | Official Pass | 总 token | Wall-clock |
|---|---:|---:|---:|---:|---:|
| explicit goal constraints | 3 | 3 | 是 | 40,438 | 482.6 秒 |
| goal-aware raw history | 3 | 4 | 是 | 90,748 | 651.7 秒 |

两个终局程序都通过完整性审计和 Official evaluation，计分 issue 为零。这组配对没有显示成功率或
执行候选数优势；它只支持一个更窄的假设：显式状态可能让强模型更容易消费多 finding 修复轨迹，
本次少用 1 次请求和 50,310 tokens。单个随机且已消费的配对不能确立效率效应，仍需在 repository-
disjoint qualification 上重复验证。

## 6. 五 Case Evidence-Anchor Qualification

冻结的 River、LitGPT、ILAMB、Flask-Security 与 Starsim 日程记录在
`PRO_GOAL_CONTRACT_QUALIFICATION_V1_RESULTS_ZH.md`。ILAMB 与 Flask-Security 在显式状态和 raw
history 下均获得 Official Pass。River 两种方法都没有进入 Official evaluation；LitGPT 显式状态在
Official evaluation 前被删失，raw history 则剩 2 个 issue 而 Official Fail。

Starsim 两种方法表面上都 Official Pass，但必须排除：终局程序通过 symlink 把 `stisim` 或 `hivsim`
名字指向 `starsim`，并没有提供真实模块。另一个 raw 候选安装 `hpvsim` 时通过依赖解析改写了被测
仓库，已被 effect audit 正确拒绝。这说明 source ownership 已被保护，但 import-alias 的语义完整性
仍有缺口。

在两个双方完成且 integrity-valid 的配对上，显式状态使用 8 个候选和 139,982 tokens，raw history
使用 9 个候选和 152,281 tokens。它只能作为机制证据。资格实验后的 integrity v2 已在执行前与两条
verifier 的 runtime 层拒绝该 alias；完成 provider-attempt 测量修复后，再进行双方共享的
verified-prefix branching 实验。不允许增加 case-specific 依赖规则。

## 7. River 外部 Codex 观测

在同一个已消费 River revision 上运行了原生 Codex CLI 与 `gpt-5.5`，机器可读记录为
`experiments/validations/pro_goal_contract_external_codex_river_v1_results.json`。首个 artifact
被 wrapper 删失，因为 repository-integrity v4 把声明构建后端生成的原生扩展误判为注入。
integrity v5 只放行仓库明确 ignore 的编译扩展和标准构建目录，同时要求 Codex 提交通过与 EnvSolve
相同的 open-program policy。随后在不再次调用模型、不改变脚本的前提下完成 re-finalization。

Codex 用 26 条容器命令和 1,153.4 秒生成时间进入 Official evaluation，最终留下 16 个
`reportMissingImports` finding。Official finding 不会反馈给 River。轨迹本身暴露了四个通用机制：

1. 环境命令超时后，其后置状态仍可能已经满足。
2. 旧原生 binding 可能隐含未声明的编译工具链约束。
3. 项目内环境路径会改变 verifier 的发现域。
4. 已验证状态可以迁移或局部修复，无需重放全部历史。

第四点进一步收紧了下一版操作层假设：EnvSolve-Pro 应保留已验证状态前缀，并对它执行状态变换；
最终只进行一次全新容器完整重放用于认证。它不是 River 配方，只能在 repository-disjoint case 上
验证。

## 8. LitGPT 外部 Codex 观测

我们也在已消费的 LitGPT revision 上运行了原生 Codex CLI 与 `gpt-5.5`，机器可读记录为
`experiments/validations/pro_goal_contract_external_codex_litgpt_v1_results.json`。该 run 通过
artifact、repository-integrity 和 candidate-program 审计，共执行 27 条容器命令，生成耗时
1,978.1 秒。终局程序在全新环境完成重放，但留下 38 个 Official scoring finding；这些 finding
已经冻结，不会驱动新的 LitGPT candidate。

该轨迹独立复现了 River 中“命令结果不等于结果状态”的区别，同时补充了一个重要限制。一次 all-extra
安装超时后留下了大量 package 状态，但立即重放又暴露缺失的生成入口，因此这个状态既有用又不一致。
在直接检查后置条件后，同一安装只用 66.9 秒完成。随后 Codex 把环境从 Python 3.13 迁移到 Python
3.11，并以一个很小的 suffix update 修复 `setuptools` 兼容问题。

所以跨 case 机制不能简化为“缓存每个成功命令”。无论退出码如何，状态转换都可能有用、受损或仍然
未知。下一版操作层应在持久 construction state 中搜索，只通过可执行后置条件准入状态复用，执行最小
修复，并只在终局用全新环境认证合成出的完整程序。
