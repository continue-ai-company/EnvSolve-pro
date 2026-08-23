# EnvSolve-Pro V2 Verifier-Handoff Screen 高价值案例

## 范围

本文档记录预注册 20-case 开发集 screen 中具有研究价值的失败，用于失败分类和算法诊断，
不作为未见测试集效果结论。任何 counterfactual 评测都不能覆盖原始 Pass@1 结果。

## Case VH-001：`platformio/platformio-core@7cf8d1d`

**Screen 结果：** Agent 未完成，Official Pass@1 = 0。

**Counterfactual 结果：** 不重新调用模型，直接评测同一个已认证 replay 程序，EnvBench
Official Pass。该结果只用于解释失败原因，不能把 screen 结果改写为成功。

### 发生了什么

Agent 已安装项目和依赖，将 Pyright missing imports 降到 0，并生成 bootstrap 程序。随后它清理
当前构建环境：

1. 第 35 条命令删除当前项目内正在使用的 `venv312`；
2. 第 36 条命令显式删除 `build_output`；
3. 第 37、38 条命令写入并检查最终 bootstrap；
4. 下一次固定观测仍尝试调用 `/data/project/venv312/bin/python`。

由于解释器已被删除，观测层无法执行 trusted goal。随后外层 minimal-integrity 审计认为
harness-owned 的 `build_output` 必须存在，直接终止 generation，Official evaluator 没有运行。

### 为什么不是部署程序本身失败

screen 已经保存 `minimal-b-replay-0001.sh`。这个 827 字符的程序在独立 fresh checkout 中：

- bootstrap 成功完成；
- trusted-goal report 完整；
- missing imports 为 0；
- repository-effect audit 通过；
- 获得 clean-replay certificate。

随后我们没有重新调用模型，只把这个已认证程序交给 EnvBench Official。Official 完整执行，
`issues_count=0` 并 Pass；其余 944 个 Pyright error 是非计分诊断。

### 三层诊断

**观测层：** 系统没有在清理动作之前暴露 construction ownership 和当前解释器路径。下一次观测
仍使用旧路径，而且反馈到达得太晚，Agent 没有修复机会。

**约束层：** shared boundary 把一个可变的构建期产物必须保留，错误地当成部署正确性的硬约束。
clean replay 和 Official evaluator 都不需要该约束，因此它是最早的因果瓶颈。

**操作层：** 在下一次观测前删除当前解释器确实是高风险状态变换，但最终 replay 程序不包含该清理
动作，而且足以通过 Official。因此对最终部署方案而言，操作本身不是最早的反事实瓶颈。

建议的新 subtype 是 `constraint / construction-state-ownership-conflict`。此前冻结的 taxonomy
v1.0.1 没有该类型，因此在旧 taxonomy 下仍映射为
`unresolved / novel-mechanism-held-for-taxonomy-v2`，不事后修改旧定义。

### 对实验的影响

该 episode 仍是科学有效的 screen Fail，必须进入完整 bad-case 集；不能重跑或替换，Official
counterfactual 也不能计为 screen Pass。后续 fresh control 与 verifier-handoff treatment 继续使用
runner 0.6.1。由于两臂共享同一 boundary，这个 case 将检验 shared boundary 是否支配两臂；即使
handoff transition 本身预计无法修复它，也不能把它从配对实验中删除。

机器可读证据：
`experiments/validations/envsolve_pro_v2_verifier_handoff_v1_screen20_platformio_boundary_adjudication.json`。

## Case VH-002：`lichess4545/heltour@1d5fd89`

**Screen 结果：** EnvBench Official Pass。

**研究用途：** 机制激活和效率候选证据；它不是 bad case，也不是 treatment 的因果结果。

### 发生了什么

第 16 次请求后的固定验证首次完整 Pass，初始 77 个 missing-import 约束已全部解决。但控制组
Agent 没有提交，而是继续修改和探查环境；第 32 次请求的观测回退为 12 个缺失约束。Agent 在
第 48 次请求恢复为 Pass，随后进入交付：

1. 第一次 clean replay 失败；
2. 同一个活跃模型 session 修复 bootstrap 程序；
3. 第二次 clean replay 通过；
4. EnvBench Official 最终以 0 个计分 issue 通过。

完整控制组 episode 使用 52 次模型请求、1,401,571 个 Token、49 次 shell 操作和两次 clean
replay，generation 约耗时 27 分钟。

### 三层诊断

**观测层：** 可执行验证器在第 16 次请求已经暴露充分状态，随后也观察到了回退，所需信号实际
存在。

**约束层：** 完整的零约束报告已经足以作为 handoff 条件，不需要继续增加跨候选约束。

**操作层：** 控制策略在已经验证充分后仍继续改变环境，没有切换到“生成程序并在新环境重放”，
因此产生额外工作并一度破坏已满足状态。

### 对实验的影响

Heltour 仍是 screen success，不进入预注册的 failure-only 配对集。第 16 到第 52 次请求之间的
差距说明 treatment 存在潜在作用空间，但它只能算上界：在第 16 次请求强制 handoff 后，clean
replay 仍可能失败并需要修复。只有 fresh paired episode 才能声称节省请求、Token 或时间。该
case 将留给与主要 Pass@1 实验分离的“成功条件下效率分析”。

## Case VH-003：`transientskp/tkp@8a19cd23`

**Screen 结果：** EnvBench Official Pass。

**研究用途：** 独立复现 handoff 的潜在作用空间，并暴露部署质量问题；它不是 bad case，也不是
treatment 的因果结果。

### 发生了什么

初始观测和第 16 次请求观测都在基础解释器下报告 38 个缺失约束。Agent 虽然创建了
`/data/venv`，但没有在持久 construction session 中激活。随后它切换到
`/opt/conda/envs/testenv/bin/python`，第 32 次请求观测立即变为完整 Pass、0 个缺失约束。

控制组 Agent 又继续了 9 次请求，才在第 41 次请求进行第一次 clean replay；该 replay 失败。
同一 session 修复后，第 45 次请求的第二次 replay 通过，第 46 次请求提交程序，EnvBench
Official Pass。整个 generation 使用 46 次模型请求、1,263,597 个 Token、43 次 shell 操作和
两次 clean replay，约耗时 18 分钟。

### 三层诊断

**观测层：** 验证器正确区分了“已经安装但未激活的环境”和持久 session 真正使用的解释器；
激活后，它立即暴露充分状态。

**约束层：** 零约束报告再次足以触发 handoff，不需要项目特定依赖规则。

**操作层：** Agent 先遗漏环境激活，Pass 后又延迟生成可重放程序，最后修复 replay 失败；执行
反馈循环依次纠正了这三个状态变换。

### 部署质量警告

认证程序为无法安装的 `casacore`、`ndimage` 和旧式 `exceptions` import 创建了本地模块。该
方案满足 Official missing-import 指标，并通过当前 minimal boundary，但不能证明与真实依赖
具有完整运行语义。Official 结果仍然有效；部署完整性应作为独立评价轴，而不能事后加入项目
特定硬约束。

### 对实验的影响

TKP 不进入预注册的 failure-only 配对集。它与 Heltour 共同证明，验证充分状态可能比最终交付
早很多模型步骤。第 32 到第 46 次请求之间的差距只能算 treatment 的潜在作用空间，不能当作
因果节省量。stub 路径将保留给后续完整性分析。

## Case VH-004：`getsentry/sentry-python@ec7172e1`

**Screen 结果：** EnvBench Official Pass。

**研究用途：** 版本兼容收敛和较小 handoff 作用空间证据；它不是 bad case，也不是 treatment
的因果结果。

### 发生了什么

基础解释器最初暴露 215 个 missing-import 约束。Agent 创建 Python 3.11 虚拟环境、安装大量
integration extras，并在持久 session 中激活该环境。固定观测记录到以下收敛序列：

`215 -> 215 -> 215 -> 19 -> 9 -> 1 -> 0`。

基础包覆盖后，剩余约束主要是旧式或版本敏感的模块路径。Agent 读取仓库 `tox.ini`，选择兼容
依赖版本，并处理最后的 `pytest_chalice.handlers` 路径。第 74 次请求首次完整 Pass；第 77 次
请求进行第一次 clean replay 并通过，第 78 次请求提交程序，EnvBench Official Pass。

generation 使用 78 次模型请求、4,258,047 个 Token、98 次 shell 操作和一次成功 clean replay，
约耗时 65 分钟；包含 Official evaluation 的完整 case 约耗时 76 分钟。

### 三层诊断

**观测层：** 可执行观测区分了解释器激活和依赖安装，并暴露持续缩小的残余约束。

**约束层：** 模块路径约束保持稳定，但原因从包缺失变成版本/API 不兼容；不需要项目特定包规则。

**操作层：** Agent 利用仓库证据选择版本、解决残余约束，并在第一次 replay 就生成可重放程序。

### 对实验的影响

Sentry 不进入 failure-only 配对集。与 Heltour、TKP 不同，它从首次 Pass 到提交程序只相差 4 次
请求。这说明 handoff 的激活空间和潜在效率收益在不同 case 间高度异质；必须报告配对结果的
总体与分布，不能只展示最大节省案例。

## Case VH-005：`injectivelabs/sdk-python@a93aab12`

**Screen 结果：** EnvBench Official Pass。

**研究用途：** 观测语义导致的假回退证据，以及新的部署质量警告；它不是 bad case，也不是
treatment 的因果结果。

### 发生了什么

初始和第 10 次请求的固定观测都在 `/data/project` 下使用 `/opt/conda/bin/python`，报告 19 个
missing-import 约束。Agent 为检查历史包 wheel，把持久 shell 的当前目录切到 `/tmp/inj`。第 21
次请求的观测随即报告 183 个约束，并把状态标为回退；但解释器和已安装环境并未改变。Agent 立刻
回到 `/data/project` 执行同一个目标，又得到原来的 19 个约束。

随后 Agent 解决了真实兼容问题：第 34 次请求的观测降至 5 个约束，第 45 次请求降至 0。第一次
clean replay 通过，第 46 次请求提交程序，EnvBench Official 以 0 个计分 issue 通过。generation
使用 46 次模型请求、2,001,524 个 Token、63 次 shell 操作和一次成功 replay；replay bootstrap
约耗时 63 秒。

### 三层诊断

**观测层：** trusted goal 虽然接收项目根目录的绝对路径，但实际仍从 Agent shell 的当前目录
执行。Pyright 的配置与模块解析因此受到无关临时 `cd` 的影响。183 个约束是假观测回退，不是
部署环境真的退化。

**约束层：** 真实约束始终是缺失模块路径，不需要新增依赖规则；错误 delta 来自前后观测上下文
不一致。

**操作层：** Agent 切换目录检查文件是合法的自由探索操作。禁止 Agent 离开项目根目录会不必要
地限制强模型能力。正确修复是让 verifier 始终从项目根目录运行公开目标，同时保留当前激活的
解释器和环境。

### 部署质量警告

Agent 选择的旧版 `injective-py` 能让 Pyright 静态解析模块，但其生成的 protobuf 模块与已安装的
protobuf runtime 不兼容。Agent 已实际观察到运行时 import 失败，并正确指出它不属于 EnvBench
的 `reportMissingImports` 目标。Official Pass 完全有效，但不能证明部署具有完整运行语义。与
TKP 一样，完整性应作为独立报告轴，不能事后增加项目特定 gate。

### 对实验的影响

SDK Python 不进入预注册的 failure-only 配对集。当前 screen 和 pair 继续冻结 runner 0.6.1。
配对实验完成后，下一版 runner 应固定从 `/data/project` 执行观测目标，并增加“Agent 临时切换
目录、环境不变”的回归测试。这是观测语义修正，不是新的部署约束。

机器可读证据：
`experiments/validations/envsolve_pro_v2_verifier_handoff_v1_screen20_sdk_python_cwd_adjudication.json`。

## Case VH-006：`marimo-team/marimo@537b2309`

**Screen 结果：** Agent 未完成，Official Pass@1 = 0。

**研究用途：** 科学有效 bad case，暴露 clean replay 可行性、操作顺序和过晚交付三类问题。

### 发生了什么

初始 trusted goal 报告 91 个 missing-import 约束。Agent 构建 Python 3.12 环境，并在第 64 次请求
首次让 construction state 完整 Pass；控制组在第 69 次请求主动进行第一次 clean replay。连续三份
程序都在 bootstrap 阶段约 1800 秒超时，没有进入 replay 环境中的 trusted goal。

Agent 随后直接测量冷安装。宽依赖命令耗时 1870 秒，并产生 7.5 GB 环境：`langchain`、`pymde`
等传递依赖把 Torch 升级为 CUDA build，额外拉入约 2.9 GB NVIDIA 库。第 116 次请求证明 pip
constraint 可以保留 `torch==2.13.0+cpu`；最终 construction 命令完成，第 120 次请求在该环境中
得到 0 个 missing import。但这份最终程序没有经过 clean replay，也没有提交。Generation 以
`Agent exhausted the request safety cap without submission` 终止。

整个 episode 使用 120 次模型请求、7,256,220 个 Token、117 次 shell 操作和三次 Unknown replay，
约耗时 4 小时 38 分钟；没有 provider error。

### 三层诊断

**观测层：** clean replay 忠实暴露了暖 construction cache 隐藏的事实：累计程序无法在固定命令
窗口内完成。后续固定观测确实受到临时 cwd 和 PATH 变化污染并产生假回退，但它不是最早决定性原因，
因为真实 replay 超时已经先出现。

**约束层：** 公开目标约束一直清楚；replay 反例又增加了部署可行性条件：用无约束 CUDA 依赖闭包
满足全部 import，无法在目标环境中重放。Harness 没有加入项目特定包规则，Agent 最终从执行证据推断
出 CPU 兼容条件。

**操作层：** 累计程序先安装宽依赖集合，之后才试图保留 CPU Torch；多次重复近似相同的冷安装闭包
耗掉大部分 episode。Agent 直到最后才找到可能的顺序和版本修复，又把最后一次请求用于验证当前环境，
没有重放并提交最终程序。因此主 subtype 为 `operation / replay-feasibility-and-late-delivery`。

### 对实验的影响

Marimo 必须进入完整预注册 bad-case 集。120-request 上限是各组匹配的实验安全条件，不代表 Token 或
请求数定义了部署问题。最后的 CPU-constrained 程序只属于诊断证据：没有 clean replay，不能事后把
失败改成成功。Verifier handoff 会在第 64 次请求触发，而控制组第 69 次请求才首次 replay；提前 5 次
请求和更早获得反例能否改变终局仍未知，必须由 fresh paired episode 回答。

这个 case 可以启发后续研究“在构造操作序列时持续维护 replay 可行性”，但单个 case 尚不足以加入包
规则、自动依赖最小化器或新 gate；必须等待冻结 bad-case 集中的重复证据。

机器可读证据：
`experiments/validations/envsolve_pro_v2_verifier_handoff_v1_screen20_marimo_adjudication.json`。

## Case VH-007：`rubisco-sfa/ilamb@c0aecd5e`

**Screen 结果：** clean replay Pass，EnvBench Official Fail。

**研究用途：** 科学有效 bad case，暴露交付操作序列中的 provider 失败掩盖和后置条件执行不完整。

### 发生了什么

初始 trusted goal 报告 28 个约束。Agent 安装 ILAMB 科学计算栈，发现 Linux ARM 上 `cf_units`
需要 UDUNITS2 XML 数据库，并在第 23 次请求让 construction obligations 降至 0。第一次 clean
replay 在 217 秒内通过，第 25 次请求提交，generation 正常完成。

Official 执行同一程序，却在 Pyright 之前失败。相关逻辑是：

```bash
conda install -y -n base -c conda-forge udunits2 >/dev/null 2>&1 || true
export UDUNITS2_XML_PATH="$PPREFIX/share/udunits/udunits2.xml"
[ -f "$UDUNITS2_XML_PATH" ] || \
  export UDUNITS2_XML_PATH=/opt/conda/share/udunits/udunits2.xml
```

Official 容器中的 provider 操作没有产生 UDUNITS2，但程序吞掉失败，也没有检查 fallback 文件是否
真实存在。随后构建 `cf_units` 报错 `Can't open UDUNITS2_XML_PATH file`，Official bootstrap exit
code 为 1。`issues_count=0` 不能算 Pass，因为 Pyright 根本没有运行。

该 episode 使用 25 次模型请求、504,687 个 Token、32 次 shell 操作和一次成功 clean replay。
Generation 约 16 分钟，Official 约 6 分钟后失败；没有模型 provider error。

### 三层诊断

**观测层：** replay 与 Official 执行同一程序，但 provider-dependent 操作产生了不同结果。一次成功
replay 只证明一条执行路径，不代表程序强制保证所有必需后置条件。这是执行覆盖部分可观测，不是目标
镜像或 goal 不一致的证据。

**约束层：** 必要条件其实已经明确：构建 `cf_units` 前必须存在真实 UDUNITS2 XML 文件。最终程序
只保存了两个候选路径，没有把“文件存在”保留成必须执行检查的后置条件。

**操作层：** `|| true` 把必需 provider 操作变成未检查的可选动作；fallback 只改变字符串，并没有
创建所需文件。因此最早决定性原因是 `operation / masked-required-provider-failure`。

### 对实验的影响

ILAMB 保留为 Official Pass@1 Fail，进入完整 bad-case 集。该 episode 已有科学有效 Agent 结果，不满足
预注册的基础设施重试条件；即使之后同一脚本在更好网络下通过，也只能是 counterfactual，不能替换结果。

Verifier handoff 会在第 23 次请求触发，控制组第 24 次请求已经 replay，几乎没有提前空间。Fresh pair
仍必须运行，但仅仅把同一次 replay 提前一个请求不太可能解决该失败。更一般的假设是 replay 反馈应暴露
并保留必需操作的后置条件；单个 case 不足以引入禁止 shell failure handling 的硬语法规则。

机器可读证据：
`experiments/validations/envsolve_pro_v2_verifier_handoff_v1_screen20_ilamb_adjudication.json`。
