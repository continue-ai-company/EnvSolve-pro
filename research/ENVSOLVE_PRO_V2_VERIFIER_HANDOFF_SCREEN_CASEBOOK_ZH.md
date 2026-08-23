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
