# EnvSolve-Pro V2 目标状态重放 Bad-6 结果

状态：开发期失败富集压力测试完成

## 研究问题

当自由 Agent 在构造环境后，可以把**完整 bootstrap** 放进目标镜像和新 checkout 中重放，并把失败原样
返回同一个活跃 session 时，能否修复普通构造环境没有暴露的问题？

本实验不是 held-out 测试。6 个 case 只来自实验前已有的 gpt-5.5 Codex Official 失败清单；case、顺序、
模型、provider、seed、镜像、prompt、限制和分析均在执行前固定。结果只能指导下一轮算法设计，不能用于
声称总体成功率、显著性、泛化、榜单或 SOTA。

## 方法

- **A-F：**同一 DeepSeek Flash Agent session 中自由执行、观察和试错，最后提交完整 bootstrap。
- **B-FCsR：**与 A 相同，但 Agent 可反复调用目标状态重放；每次从目标初始状态执行完整 bootstrap，失败
  回到同一 session，只有重放通过的程序才能交付。
- **minimal-H：**两组共享的 evaluator 和仓库完整性边界，只是实验 harness，不是部署算法。

两组都只在 episode 结束后调用一次 EnvBench Official evaluator，绝不把 Official 结果用于在线修复。

## 主结果

端到端成功要求“形成候选且 Official Pass”。Agent 没有提交是部署失败，不是统计删失。

| Case | A-F | B-FCsR | 关键机制 |
|---|---:|---:|---|
| quacc | Fail | Fail | A 遇到下载超时；B 在候选前搜索膨胀 |
| ajenti | Fail | Fail | 两组都达到 0 missing imports，却没有及时提交 |
| clarity | Pass | Pass | B 第一次重放通过，无反馈修复 |
| HA-Battery-Notes | Pass | Pass | B 通过 Fail→Pass 修复 build isolation |
| hark | Fail | Pass | B 通过 Fail→Pass 修复 fresh checkout 的 Git ownership |
| micropy-cli | Fail | Pass | B 形成候选并通过 Fail→Pass 修复依赖冲突 |

A 为 `2/6`，B 为 `4/6`；2 对都通过，2 对只有 B 通过，没有只有 A 通过的 pair，2 对都失败。精确双侧
McNemar 为 `p=0.5`。方向值得继续，但样本太小，不能称为显著增益。

两组形成候选的数量都是 `4/6`。B 的 4 个候选全部进入重放，共完成 7 次：1 个第一次通过，3 个经历
Fail→Pass；最终重放和 Official 在 `4/4` 上一致。

## 三层错误分析

### 观测层：目标环境暴露了什么？

普通构造环境可能掩盖 fresh target state 才出现的事实。HARK 的 A 在本地构造时没有发现问题，直到
Official fresh checkout 才因 Git ownership 失败；B 的第一次内部重放提前暴露了完全相同的错误。
HA-Battery-Notes 的重放暴露 build isolation 无法获取 Cython；micropy-cli 暴露固定依赖之间的 resolver
冲突。

quacc 说明观测仍有歧义：A 的程序最终因为 Pyright wheel 下载和解压在 30 秒网络超时后退出。Official
按规则记 Fail，但失败更接近网络获取鲁棒性，不能被误写成 LAPACK 或包版本冲突。

### 约束层：当前真正缺什么？

最干净的可执行约束来自 HARK：在 fresh checkout 安装前，当前仓库必须被 Git 接纳为 safe directory。
B 在同一个 session 中把该反例转成一个环境前置条件，并只增加一行操作后再次重放。

HA-Battery-Notes 和 micropy-cli 也产生了局部、可执行的约束：前者需要让 Cython 在非隔离构建中可见；
后者需要解除 `cachier==2.3.0` 与 `setuptools==65.5.1` 的依赖冲突。核心方法不把这些 case 特定结论写成
跨仓库硬规则；它们只存在于当前活跃 session 的推理中。

### 操作层：为什么仍然失败？

当前主要未解问题发生在重放之前。quacc B 在 optional scientific packages、native builds 和多个环境
之间搜索到第 120 次请求，始终没有形成候选，所以重放从未进入闭环。

ajenti 更关键：A 在请求 103-104 已达到 `reportMissingImports=0`，B 在请求 100 达到同一目标；两者随后
为了更完整的 runtime import 继续重建环境，最终都在请求 120 结束而未提交。micropy-cli A 也在后半段
多次得到 0 missing imports，却没有交付候选。

这不是“还缺一条 package 规则”，而是**成功候选的保留和停止决策**失败：Agent 把 Official 目标和更广的
部署完整性混在一起，一旦继续探索，就可能丢掉已经足够通过的路径。

## 因果案例

HARK 是本轮最干净的机制证据：

1. A 提交的程序在 Official fresh checkout 因 `dubious ownership` 失败。
2. B 的第一次内部目标重放复现同一错误。
3. 同一活跃 session 增加 `git config --global --add safe.directory "$REPO_ROOT"`。
4. 第二次目标重放通过，随后 Official 通过。

这支持一个窄而真实的结论：**目标状态反例可以让 Agent 修复构造环境看不到的完整程序缺陷。** 它尚不证明
该机制能解决候选形成，也不证明期望总体成功率。

## 路径质量

micropy-cli 的 B 程序通过了预注册 minimal-H 和 Official，因此主结果必须记 Pass，不能事后改标签。
但它还创建了未跟踪的 `micropy/cli.py`，将真实 `micropy.app.app` 重新导出为 `cli`，并创建空的
MicroPython `.pyi` stub。前者不是空模块造假，后者也没有修改 evaluator；不过它们说明 Official success、
环境纯度和部署完整性是不同评价轴。

同理，quacc A 使用了合成 `torch` import stub。论文应保留 Official Pass@1 为主指标，同时单独报告源码
改动、stub、可执行完整性和路径成本，不能偷偷把这些轴压成一个后验 gate。

## 资源

| 指标 | A-F | B-FCsR | B 相对 A |
|---|---:|---:|---:|
| 模型请求 | 416 | 448 | +7.7% |
| Provider attempts | 438 | 464 | +5.9% |
| Token | 16,127,687 | 17,066,670 | +5.8% |
| Tool results | 450 | 446 | -0.9% |
| 端到端时间 | 19,138 秒 | 21,124 秒 | +10.4% |

B 在本批次提高了成功数，但没有降低总体资源。Token、时间和命令都是结果指标，不是成功的硬阈值；当前
不能声称效率增益。

## 结论与下一假设

最小目标状态重放应保留：它对**候选形成之后**的隐藏目标状态错误有效，HARK 给出了直接因果证据。
但当前主要矛盾已经前移到候选形成和停止决策。

下一算法假设应保持简单：Agent 一旦得到一个可执行的 Official-equivalent 候选，就先保存并进入目标状态
重放；之后仍可探索更完整或更便宜的路径，但不能丢失已有成功候选。部署成功、完整性和资源成本分别
评价。该假设必须先讨论和设计，再在新的固定 development batch 上验证，不能用本 Bad-6 回调 package
规则。

机器可读结果位于
`experiments/validations/envsolve_pro_v2_target_state_replay_screened_bad6_v1_result.json`。
