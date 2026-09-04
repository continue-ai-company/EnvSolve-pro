# v6 Feedback Attribution / v6 反馈归因更正

2026-09-04. Retrospective analysis only; no new execution, model call, or protocol change.

## 中文

**结论：七个历史 B session 确实收到了同 session 的完整程序重放结果，但没有观察到由语义失败反例驱动的程序修复。**

范围是本地 `runs/envsolve-pro-strong-ab-census83-v6-v1/mac-central-remote` 下七个已保存的 B 轨迹；全部 case ID 已核对属于明确的 209-case Dev 总体。不读取 protected case 文件，不把七个条件性选中的 B 当作总体样本。

| 位置 | 项目 | 重放返回状态 | 完成事件行 / turn 结束行 |
|---|---|---|---|
| 01 | pretalx | pass | 37 / 39 |
| 02 | python-control | pass | 58 / 63 |
| 04 | tortoise-orm | pass | 38 / 41 |
| 06 | flask-security | pass | 44 / 46 |
| 09 | duino-coin | infrastructure_error, pass | 43, 48 / 50 |
| 10 | mflowgen | pass | 34 / 36 |
| 14 | qibo | pass | 109 / 114 |

每个 `trajectory.jsonl` 只有一个 thread.started 身份。表中八个 `submit_and_replay` 完成事件均先于该轨迹的 turn.completed，且返回状态与 `minimal-b/replays.jsonl` 一致。七份 pass 的反例列表均为空；唯一非 pass 在下载超时后没有执行到目标验证。这里只证明工具反馈的时序，不证明与 Official 的目标状态完全一致。

两处旧解释应更正：

- tortoise-orm：第 29 行普通构建 shell 检出 uvicorn.main、astroid.node_classes 缺失；第 32 行 shell 安装兼容依赖并报告缺失数为零；第 38 行才收到唯一一次完整重放的 pass。因此缺失依赖的发现和修复均在重放之前，不能归因于重放反例。
- flask-security：第 37 行普通 shell 检出七处缺失，第 40 行安装 quart、Flask-Mail、twilio 后报告零缺失；第 44 行收到唯一重放的 pass。旧文字称“fresh replay 发现这些缺失后修复”不符合事件顺序。

duino-coin 的两份重放程序确实不同，但逐行差异只有 pip `--timeout 30` 改为 `--timeout 180`；不是新增依赖或语义修复。其余六个 session 各只有一个重放候选。

**裁决建议：retain，仍未证实，不晋升。** 原来记录的最终评分及成对胜负不在本次被改写，但不能由这些胜负反推特定修复机制成立。普通构建诊断、模型采样差异，以及“知道最后需要验证”对前期规划的影响，均是竞争解释；这份回顾也不能证明验证毫无价值。mflowgen 已记录的内部通过而 Official 失败，则仍是目标状态不一致的反证。

下一步优先审议公平强 Agent 普查，找到真实完整程序终局失败；不因这次更正新增约束或工具框架。若未来比较自动重放与自由 Agent，应事先明确后者自主干净验证的能力，不能将其人为关闭后宣称优于完整能力的强 Agent。

## English

Seven saved historical v6 B sessions contain eight completed full-program replay responses, all preceding turn completion in the same recorded session. Seven responses pass; the only failure is a download-timeout event before goal verification. No replay reports a semantic counterexample that is subsequently repaired.

Two previous mechanism narratives overstate the evidence. In tortoise-orm and flask-security, ordinary construction-shell checks found and repaired the missing imports **before** the sole successful replay. The relevant completed event lines are 29/32/38 and 37/40/44 respectively. In duino-coin, the only difference between two replay programs is changing pip's timeout from 30 to 180 seconds. These are not observed semantic-counterexample-driven repairs.

This correction preserves historical outcome records while withdrawing the unsupported mechanism attribution. Operational replay and same-session delivery are supported; target-state equivalence and causal semantic-feedback benefit are not established by those facts. Agent sampling, ordinary diagnosis, and anticipatory effects of a required final verification remain competing explanations. Absence of a repair event does not prove verification has no value.

**Retain as unproven; do not promote.** Review the proposed fair strong-Agent prevalence census before new treatment evaluation. No protected data or new algorithm rule is involved.

## Evidence Paths

Each row maps to `runs/envsolve-pro-strong-ab-census83-v6-v1/mac-central-remote/pro-v6-strong-ab-census83-<position>-B/<case>/generation/trajectory.jsonl` and `generation/minimal-b/replays.jsonl`. Event line numbers are one-based physical JSONL lines, not model step numbers. Original programs are under `generation/minimal-b/programs/`.

The two corrected records are `experiments/validations/envsolve_pro_strong_ab_census83_v6_position4_pair_adjudication.json` and `experiments/validations/envsolve_pro_strong_ab_census83_v6_position6_pair_adjudication.json`. Their added correction fields supersede only the original mechanism interpretations, not the stored scores or raw evidence.
