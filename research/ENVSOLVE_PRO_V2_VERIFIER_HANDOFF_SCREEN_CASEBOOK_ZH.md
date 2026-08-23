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
