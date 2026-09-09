# EnvSolve-Pro M0 Census Closeout / M0 普查收口

Date / 日期: 2026-09-09

Machine-readable evidence / 机器可读证据: `experiments/analyses/envsolve_pro_m0_census_closeout_20260909.json`

## 中文

### 结论

固定的单主机 census 已按原计划完成 positions 5-24，没有换样本或因结果提前停止。20 个位置中，15 个 Official Pass、2 个 Official Fail、3 个明确的基础设施 censor；在 17 个获得 Official 判定的 case 中通过率为 15/17（88.2%）。18 个 case 形成了可执行部署程序。

当前主要矛盾不是强 Agent 普遍无法解出依赖，而是**第一次探索很贵，已经解出的项目没有把足够清晰、可验证的求解进度留给下一次部署**。18 个提交程序的 Agent session 总计 30,995.70 秒（8.61 小时），而相同最终程序的独立 qualification bootstrap 总计 4,112.24 秒（1.14 小时），前者是后者的 7.54 倍。中位数分别是 20.93 分钟和 3.39 分钟。

这只是“可重用进度可能有价值”的证据，不是 EnvSolve-Pro 已经有效的证据。普通脚本复用本身就可能获得大部分收益；强 Agent 读取完整历史也可能自动提炼出同样的信息。显式状态只有在与这两个强对照比较后仍能保持成功并减少新的模型推理，才值得进入核心算法。

### 最强证据与反证

最强支持证据是成本结构和 `mpmath` 轨迹。总体上，探索成本远高于最终程序重放；`mpmath` 的干净重放又真实暴露了 Git ownership、非 fail-fast 假成功和包索引超时，同一活跃 Agent 根据执行反例完成了修复。这说明可执行反馈能够把“看似完成”变成可复现程序。

最强反证是自由强 Agent 本身已经达到 15/17 Official Pass，并且大量 case 主动使用了干净重放。两个 Official Fail（`lnldb` 和 `sphinx-scylladb-theme`）都发生在 Agent 可见重放与独立 qualification 已通过之后，失败点分别是 GitHub clone TLS 中断和 Rust bootstrap 下载 SSL EOF。因此，当前失败也可能主要是外部获取的随机可靠性，而不是缺少显式求解状态。一次干净重放成功不能证明之后必然成功。

当前裁决是 **retain，不 promote**：保留最小显式项目状态作为 M1 challenger，但不把它写入核心算法结论。Live frontier 仍然被 kill，只保留作诊断或负向消融。

### M1 预先选择

在查看任何 M1 outcome 之前固定四个 consumed/Dev 项目：

| Position | Project | 选择理由 | D0 -> D2 |
|---|---|---|---|
| 10 | `ceph/ceph-ansible` | 最终重放短，但首次发现 provider 与仓库内 Ansible 路径耗时明显 | Python 3.11 -> 3.10 |
| 17 | `mpmath/mpmath` | 干净重放连续暴露并修复 ownership、假成功和网络问题 | Python 3.13 -> 3.12 |
| 22 | `fonttools/fontbakery` | legacy native build，成功路径完整但较重 | Python 3.10 -> 3.11 |
| 23 | `astropy/reproject` | all-extras 首次成功并编译 native extension，适合检验显式状态是否胜过普通复用 | Python 3.13 -> 3.12 |

D2 只改变到仓库明确支持的相邻 Python 版本。它是受控开发实验，不是 EnvBench leaderboard 结果；成功要求目标解释器实际生效且 public missing-import goal 通过。

三条实验 arm 保持相同强模型、工具、历史可用范围和目标环境：

1. `R0`：复用已有程序；失败后由强 Agent 修复并保存新程序。
2. `R1`：给强 Agent 完整历史和相同工具，明确要求改进部署。
3. `P`：给 Agent 最小的、由执行证据支持的项目求解状态，只聚焦当前条件变化或失败所影响的步骤。

D0 使用现有成功条件；D1 是同条件的新鲜执行；D2 是上述单一 Python 变化。状态版本都在相同的 Q 上 probe，probe 不反向更新状态。Official 只在 episode 结束后运行；D2 仅作受控条件验证。主要共同指标是终局成功与本次新消耗的模型用量，模型用量拆分为 input、cached input 和 output，同时记录真实执行时间、更新成本、验证成本和失败恢复成本。

`P` 的最小状态只保存：已成功的有序程序、它被验证过的条件、观察到的失败与成功修复 delta、仍未解决的风险。不加入跨项目经验、包规则、搜索图、checkpoint 图或新的安全 gate。若 `R0` 或 `R1` 与 `P` 相当，或状态维护成本抵消收益，就否定显式结构的必要性。

## English

### Judgment

The fixed single-host census completed positions 5-24 without replacement or outcome-driven stopping. The 20 positions contain 15 Official Passes, two Official Failures, and three explicit infrastructure censors. Among 17 Official-adjudicated cases, 15 passed (88.2%); 18 cases produced executable deployment programs.

The main bottleneck is not broad failure to solve dependencies. It is that first exploration is expensive while a solved project leaves insufficiently explicit, executable progress for a later deployment. Across 18 submitted programs, Agent sessions consumed 30,995.70 seconds (8.61 hours), versus 4,112.24 seconds (1.14 hours) for independent qualification bootstrap of the final programs, a 7.54x ratio. Medians were 20.93 and 3.39 minutes.

This motivates a state-reuse test; it does not validate EnvSolve-Pro. Ordinary program reuse may capture most of the gain, and a strong Agent with full history may infer the same information. Explicit state belongs in the core method only if it preserves terminal success and reduces newly required model inference against both controls.

The strongest supporting evidence is the cost decomposition and the `mpmath` trajectory: clean replay exposed Git ownership, non-fail-fast false success, and a transient index failure, after which the same active Agent repaired the complete program. The strongest counterevidence is that the free strong Agent already achieved 15/17 Official Pass and often chose clean replay itself. Both Official failures occurred after Agent-visible replay and independent qualification had passed, through external Git or Rust-bootstrap downloads. Replay reliability, rather than missing symbolic structure, is a competing explanation.

Decision: **retain, not promote**, the minimal explicit project-state challenger for M1. Live frontier remains killed.

### M1 Screen

Before observing any M1 outcome, select positions 10 (`ceph-ansible`), 17 (`mpmath`), 22 (`fontbakery`), and 23 (`reproject`). They are Official-successful, cover provider/path resolution, replay counterexamples, legacy native builds, and broad optional/native installation, and retain enough evidence for paired comparisons. Exclude position 5 because its source compatibility copy confounds clean project state, position 11 because CUDA/runtime completeness is unresolved, and position 24 because it lacks an Official-successful D0 artifact.

Compare `R0` ordinary program reuse plus strong-Agent repair, `R1` a strong Agent with full history explicitly asked to improve, and `P` minimal evidence-backed project solving state. Run existing D0, fresh same-condition D1, and one repository-supported adjacent-Python D2 per project. D2 is a controlled development condition, not a leaderboard result. Terminal success and newly required model usage are co-primary; split input, cached input, and output tokens, and report execution, state-update, validation, and failed-recovery costs separately.

The minimal `P` state contains only the successful ordered program, conditions under which it was executed, observed failure-to-repair deltas, and unresolved risks. It adds no cross-project experience, package rules, search graph, checkpoint graph, hash, frozen contract, or safety gate. If `R0` or `R1` matches `P`, or state-update cost cancels the gain, explicit structure is unsupported.
