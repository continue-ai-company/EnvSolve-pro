# Post-v7 Evidence Proposal / v7 后续证据实验提案

Status: Experiment 1 completed all 15 executions on 2026-09-04. Experiment 2 has completed positions 1-8 and position 9 is next. EnvBench Official Pass@1 is decisive; path-quality observations are descriptive tags only. This is an experiment memo, not an ICLR draft.
状态：实验 1 已于 2026-09-04 完成全部十五次执行。实验 2 已完成位置 1-8，下一项为位置 9。EnvBench Official Pass@1 是唯一主裁决；部署路径质量观测只作为描述性标签。本文是实验备忘录，不是 ICLR 稿件。
Result / 结果：`research/envsolve_pro_post_v7_repeatability_report.md`。

## 中文

### 当前判断

主要矛盾不是规则不足，而是尚未确认强 Agent 的可修复终局失败有多普遍，且同一程序的执行结果会波动。
历史 v7 的固定 8 个位置中，5 个 P0 首次执行通过，1 个重试通过，1 个基础设施未解决，1 个源码不可得；语义修复机会为 0。
python-control 的同字节程序却出现在线通过、终评缺失导入和另一分支通过。这支持研究执行稳定性，但不支持反馈算法增益。
因此保留最小 replay 假设为未证实候选，不晋升 v7；Live frontier 维持 kill。

v7 在线返回 Official 路径结果，并使用已结束 P0 的无工具子会话。它不能充当当前“同一活跃 session 中的独立 target-state replay”的资格证据。
以后 Official 只用于 episode 结束后的最终评估，不把输出传给任何在线 Agent。

### 实验 1：同程序重复执行

- 问题：固定仓库、revision、完整脚本、镜像和执行器时，终局评分是否一致？
- 对象：已消费的 python-control、qtconsole、yapf 三个 P0 原脚本。前者和后者已有不一致，qtconsole 作为对照。这个选择是诊断性选样，不能估计全体 Dev 的稳定率。
- 数量：每个脚本 5 次新执行，共 15 次。按三个项目轮换顺序执行 5 轮，避免把项目与时间段完全混淆。
- 条件：同一 Spark；沿用已记录镜像身份与执行器版本；每次独立干净目录和容器；复用只读源码，不新增跨执行可写依赖缓存。记录实际解析出的依赖版本，不声称未固定的包索引是恒定的。
- 终点：每次记录原始 bootstrap exit、报告是否存在、官方 issuesCount、缺失导入集合以及外部故障证据。模糊的 versions:none 或解析回溯保留为原因未决，不能自动叫作网络失败。
- 停止规则：完成预定 15 次尝试即停止；不追加“直到通过”的重试，不替换项目。传输观测超时先检查原进程，不能重复启动。主机不可用则保留未完成状态，恢复后继续同一计划。
- 裁决：一次无外部故障解释的同字节语义差异即可否定本配置的确定性假设；5 次一致只能给出有限稳定证据。只观察到外部删失时，报告可用性不足，而不是证明程序不稳定或稳定。
- 本实验没有在线 Agent、没有 treatment，也没有模型调用。它只检验评分可重复性。

执行记录：Spark tmux `post-v7-repeatability-20260904`；输出 `/home/avdpro/work/envsolve-pro-post-v7-repeatability-20260904`。
使用原执行器目录 `EnvSolve-pro-v7-6bc8230` 和已记录的原 Docker image ID，不拉取新的 latest。
一次性脚本 `experiments/tools/run_post_v7_repeatability.py` 排列全部十五次；普通单测验证交错顺序、失败不追加重试及只读采样。
因 EnvBench 在结束时删除仓库目录，本次每两秒只读采样挂载目录中的 dist-info 名称和已知争议文件 `control/_version.py`；这只是归因证据，不更改候选、评分器或其输入。采样不是最终环境清单，缺采样不能证明文件不存在。

### 实验 2：强 Agent 首次程序的 Dev 普查

- 问题：不按弱基线输赢挑样本，强 Agent 形成完整程序后真实失败的比例是多少？失败中有多少能给 replay 提供反例？
- 抽样：先确定当前授权的显式 Dev 名单，不读取 Protected Canary/Test；按 case ID 排序后，用 Python Random(20260904) 不放回抽取 24 个。抽样不读取任何基线胜负或新 treatment 结果，公开记录与历史样本的重叠。授权池不足 24 个时先修订方案，不静默缩样。
- 已核对的候选总体：`experiments/cases/dev_pro_bad_case_census_v1_209.jsonl`，209 个唯一 ID，内容集合等于 `dev5.jsonl` 与 `train_rest204.jsonl` 的并集。依据既有 `pro_dev_bad_case_census_v1_preregistration.json` 的开发总体定义；此次未读取 protected case 文件、未抽样，也不重新声称独立核验了 protected 集合交集。建议审定这个完整开发总体，而非按旧基线表现筛选的子集。
- 样本量理由：24 是快速估计机会率的 pilot，不是方法有效性检验。若 24 个独立有效样本均无失败，失败率的一侧 95% 二项上界仍约 11.7%，不能宣称强 Agent 已刷满；有删失时该界不能直接用于全样本。
- 方法：Mac 统一控制同版本强 Agent，Spark 承担远程构造与 episode 结束后的串行 Official；全部位置统一暴露 Spark GPU。模型、工具、公开目标和初始条件在执行前记录，过程不限制自由 Agent 的操作策略。启动前发现 AgentHub 仅余 5.9 GiB 且没有位置 1 的缓存，而 Spark 有 2.1 TiB 空闲和 exact-revision cache，因此在读取新结果前选择 Spark；后续 treatment 必须匹配该主机和 GPU 条件。
- 终点：首先按全部 24 个抽样位置报告程序提交和 Official Pass@1；另列未提交、bootstrap 失败、缺失导入失败、源码不可得、明确基础设施故障和原因未决。源码兼容修改、provider 语义和运行时完整性只作描述性标签，不覆盖 Official 结果。
- 停止规则：只跑固定 24 个位置，不因看到失败或成功提前停止、不替换删失位置、不启动 F/N/A2。未完成进程按原身份恢复。时间、token、费用只报告；保留公共安全超时并单列触发情况。
- 解释：同时报告完整样本成功下界、把未决位置视为可能成功的上界，以及有效执行条件下的描述性机会率。该样本代表授权 Dev，不自动代表 EnvBench 全榜。
- 只有确认真实的强 Agent 终局失败后，才提出下一版独立 target-state replay 对照。失败若发生在完整程序形成之前，明确列为 replay 当前无法直接解决的边界。

实际配置：模型 `gpt-5.6-sol`、推理档 `xhigh`，启动前实测 Codex CLI 为 `0.153.4`。历史 P0 只有 `envsolve_container.envbench_shell`，可在持久构建容器中读写、安装、测试，并运行公开的 Pyright 目标；没有在线 Official 结果，也没有暴露专门的新容器 replay 工具。该接口不能直接声称等同于不受限制的 Codex。
普查允许自由 Agent 通过通用执行工具自主创建干净容器并运行自己的完整程序，而不预装 EnvSolve 的自动 replay 反馈策略。此能力应在后续两臂中同等保留。不能把历史 P0 的能力缺口当作制造算法机会的手段。

该前置条件现已满足。`research/envsolve_pro_free_agent_environment_capability_v1_report.md` 记录了 Spark、AgentHub 后端探针，以及真实 Codex 在普通 consumed case 中自主创建 fresh environment、运行后来提交的完整程序、读取公开目标结果并主动关闭环境的轨迹。固定样本见 `experiments/schedules/envsolve_pro_free_agent_census24_v1.json`；24/24 均有既往方法暴露，因此本实验只作 consumed Dev 普查。

位置 1 `cclib` 已完成。自由 Agent 提交了程序，并在三个自愿创建的干净环境中进行过重放；最后一次重放的公开目标为零缺失导入。但独立 Official 在 `requirements-dev.txt` 的 `pyquante2` Git 获取发生 GnuTLS 失败后以 bootstrap exit 1 结束，未产生 Pyright 报告，因此全样本成功记为 false。提交还生成了只供静态检查使用、没有对应运行时模块的 `PyQuante`/`pybel` 类型接口，不满足预登记的合法部署边界。该位置证明真实终局失败存在，但没有证明自动 clean replay 有增益，因为自由 Agent 已经自行重放并观察到通过。原始记录见 `experiments/validations/envsolve_pro_free_agent_census24_v1_position01_result.json`。

位置 2 `django-lfs` 的 Agent 已生成完整程序，并在一个自愿创建的干净环境中重放后观察到公开目标通过，但旧 V6 验证器把外部 `mktemp -d` 目录中的功能性兼容包 `setup.py` 误判成项目配置写入，导致轨迹在 Official 前终止。该位置固定记为 `boundary-censored`、保留在 24 个位置的分母中且不重跑。修订只允许明确根植于未重绑定 `mktemp -d` 变量的外部配置目标进入原有执行与审计，同时显式拒绝位置 1 式 `.pyi` 类型 provider；从位置 3 使用 V6.1。旧候选在新静态规则下离线可接受只作敏感性分析，不改变主结果。协议说明见 `research/ENVSOLVE_PRO_FREE_AGENT_CENSUS_BOUNDARY_AMENDMENT_V1.md`，机器记录见 `experiments/validations/envsolve_pro_free_agent_census24_v1_position02_boundary_censoring.json`。

位置 3 `lark` 的 Official 指标通过（0 个 missing import；另有 662 个非目标 Pyright error），但合法部署记为 false。Agent 安装了 PyPI `js==1.0`；其包归档和依赖表明它是 Fanstatic 的根包，而项目源码明确从 `js` 获取 Pyodide 浏览器运行时的 `window` 和 `eval`。这属于“同名包使代理指标归零、却没有提供预期语义”，不是算法成功。Agent 已在两个自建干净环境中重放完整程序并观察到公开目标通过，所以该位置也不支持自动 replay 增益。episode 后的辅助审计另有独立误报：它把 checkout 中已有的 mode `160000` Gitlink `tests/test_nearley/nearley` 当成合成空包；该误报未阻止 Official，不在 census 中途修规则。机器记录见 `experiments/validations/envsolve_pro_free_agent_census24_v1_position03_result.json`。

位置 4 `getnikola/plugins` 的 Official 指标通过（0 个 missing import；另有 777 个非目标 Pyright error），但合法部署仍记为 false。自由 Agent 两次主动 clean replay，修复第一次的网络与 fail-fast 问题后在第二次观察到公开目标通过。唯一真实 import 检查却已证明 `CommonMark 0.5.4` 在 Python 3.12 因 `HTMLParser.unescape` 缺失而失败，且没有后续 runtime pass。资格审计还错误拒绝了 tracked symlink 和项目内功能性环境目录；这些误报不改变已知 runtime failure，也未阻止 Official。机器记录见 `experiments/validations/envsolve_pro_free_agent_census24_v1_position04_result.json`。

执行拓扑勘误：此前“Spark 承担 Official”的文字不正确。位置 1-4 的构建、Agent 可见验证和资格重放在 Spark；Official 由 Mac-local EnvBench 通过当时的本地 Docker context 启动，位置 4 已现场确认是 `desktop-linux`，位置 1/3 的 context 未记录。两端镜像 digest 和 `linux-aarch64` 架构相同，但网络、缓存与 GPU 暴露不同。原始记录不覆写，显式勘误见 `experiments/validations/envsolve_pro_free_agent_census24_v1_positions01_04_topology_correction.json`，阶段裁决见 `research/ENVSOLVE_PRO_CENSUS_POSITIONS01_04_STAGE_REPORT.md`。

本批 24 个位置在位置 4 后暂停，不再把 AgentHub 插入已开始的批次。已完成位置采用实际发现的双主机路径：Spark 负责构建与 replay，Mac-local EnvBench 负责 Official。AgentHub 当前只有约 5 GiB 空闲盘。下一轮方法比较将在运行前按是否需要 GPU 分层：CPU block 固定到 AgentHub，GPU block 固定到 Spark；同一 case 的全部方法保持同机和同资源条件。AgentHub 上约 17 GiB 的旧 construction checkout/replay 是启用该 CPU lane 前需要迁移或清理的容量障碍。

负责人于 2026-09-08 明确裁决：本普查的一切主结论均以 EnvBench Official Pass@1 为准。源码修改、兼容模块、provider 语义和运行时完整性继续保留为路径质量标签，但不能推翻 Official。因此，位置 3 和 4 按 Official success 计数，历史机器记录不覆写。

位置 5 `meshio` 在 Spark 上通过 Official。自由 Agent 已主动在干净环境中重放完整程序，独立 post-session qualification 也通过。程序把 checkout 中的 `_vtk_common.py` 复制为 `src/meshio/vtk_io.py`；该操作标记为源码兼容路径，但不影响 Official Pass。本位置不提供自动 replay 增益证据。

位置 6 `mashumaro` 在 Spark 上通过 Official。自由 Agent 主动重放了同序安装操作，最终提交只是用 `&&` 将这些操作串成 fail-fast 程序；精确最终程序随后通过独立 qualification 和 Official。本位置同样不提供自动 replay 增益证据。

位置 7 `lnldb` 是 Official Fail@1。相同提交程序此前通过了 Agent 主动重放和独立 qualification，但 Official 在克隆声明的 `jsmin` Git 依赖时遭遇 GnuTLS 连接终止，bootstrap exit 1，未产生 Pyright 报告。官方失败是主结果；网络下载失败、Django 兼容模块，以及另行观测到的 `collections.Iterable` 运行时问题仅作标签。由于前两次安装成功且瞬时网络波动是竞争解释，本位置尚不能证明自动 replay 有增益。

位置 8 `pyvespa` 在 Spark 上通过 Official。构建过程中一次 PyPI 下载超时，Agent 自主增加 timeout/retries 后完成安装，并在自建干净环境中重放成功；精确最终程序随后通过独立 qualification 和 Official。该位置是自由 Agent 自修复成功，不提供自动 replay treatment 的增益证据。

位置 9 `neurogym` 在 Spark 上通过 Official。自由 Agent 在自建干净环境中继续完成一次超时的安装，随后用 `numpy<2` 修复 NumPy 2 运行时不兼容；七个核心测试通过且缺失导入为零。精确最终程序通过独立 qualification 和 Official。程序创建了缺失的 `neurogym/utils/test_plotting.py` 功能性兼容模块；该操作只作源码兼容标签，不推翻 Official。构建目录的旧 clean-tree 审计曾拒绝这个未跟踪文件，但同一原定 run 仍按 Official-primary 路径完成，因此该位置不是 boundary-censored，也不提供自动 replay 增益证据。协议说明见 `research/ENVSOLVE_PRO_FREE_AGENT_CENSUS_POSITION09_PROTOCOL_NOTE.md`。

位置 5-9 已完成，固定顺序中的下一项是位置 10。AgentHub 不加入本轮 census。

### 当前授权边界

负责人已接受带偏差说明的历史结项，并在重复执行结果完成后批准实验 2。该授权只覆盖固定 24 个 consumed/Dev 位置的自由 Agent 普查，不授权进入 treatment Phase 2 或受保护数据。
不引入新的 frontier、跨 case 经验、checkpoint 或符号约束框架。

## English

### Judgment

The immediate uncertainty is the prevalence of repairable terminal failures from a strong Agent, compounded by outcome variation for identical programs.
In the fixed historical v7 batch, five initial P0 executions passed the metric, one passed only on retry, one remained infrastructure-unresolved, and one had unavailable source. There were zero semantic repair opportunities.
The identical python-control program nevertheless produced an online pass, a postepisode missing-import failure, and a pass in another arm. This motivates repeatability diagnosis, not a feedback-effect claim.
Retain minimal replay as unproven; do not promote v7. Live frontier remains killed.

Historical v7 returned Official-path results online and continued completed P0 prefixes in tool-free child sessions. It cannot qualify the current mechanism: independent target-state replay inside the same active session. Official must remain postepisode-only in new work.

### Experiment 1: Repeatability

Use the original consumed P0 programs for python-control, qtconsole, and yapf: two observed instability examples and one comparison. This diagnostic selection cannot estimate population-wide stability.
Execute each five times on Spark, in five interleaved rounds, for 15 total executions. Preserve repository revision, program bytes, recorded image identity, executor version, independent clean workspaces, and read-only source reuse. Do not introduce mutable shared dependency caches. Package-index state remains a possible source of variation and is not assumed fixed.

Record every raw exit, report presence, Official issuesCount, missing-import multiset, and external-failure evidence. Empty indexes and resolver backtracking remain unattributed unless corroborated. Stop after the 15 scheduled attempts; no success-seeking retries or replacement projects. Observation timeouts require checking the original process, not launching another execution.

One unexplained semantic disagreement refutes deterministic behavior for this configuration; five agreements provide only limited evidence. External censoring alone establishes neither semantic stability nor instability. This diagnostic has no online Agent, treatment, or model calls.

Experiment 1 execution: Spark tmux `post-v7-repeatability-20260904`, output `/home/avdpro/work/envsolve-pro-post-v7-repeatability-20260904`. The one-off runner uses the existing `EnvSolve-pro-v7-6bc8230` executor and recorded image ID without pulling latest. Read-only two-second samples of mounted distribution-directory names and the disputed `control/_version.py` help attribution before EnvBench deletes the workspace. They are in-flight samples, not certified final inventories; missing samples are not proof of missing files. Neither candidate programs nor evaluator code are changed.

### Experiment 2: P0 Prevalence

Establish the explicitly authorized Dev population without reading protected data. Sort IDs, then sample 24 without replacement using Python Random(20260904), independently of all baseline outcomes and treatment results. Record prior exposure overlap. If the authorized pool is smaller, revise the proposal before execution rather than silently shrinking it.

Proposed population verified locally: `experiments/cases/dev_pro_bad_case_census_v1_209.jsonl` has 209 unique IDs and equals the union of `dev5.jsonl` and `train_rest204.jsonl`, following the existing `pro_dev_bad_case_census_v1_preregistration.json` development-universe definition. No protected case file was read and no sample selected; this check does not independently reverify protected-set disjointness. Review this full development population rather than an outcome-selected subset.

Twenty-four cases are a prevalence pilot, not an efficacy test. With zero failures in 24 independent evaluable cases, the one-sided 95% binomial upper bound is still about 11.7%; censoring prevents directly applying this bound to the full sampled population.

Use a common Mac Agent controller and recorded model/CLI configuration, Spark remote construction with the Spark GPU exposed for every position, and serial postepisode Official scoring on Spark. This host assignment was recorded before model execution because AgentHub had only 5.9 GiB free disk and no position-1 cache while Spark had 2.1 TiB free and the exact-revision cache. Future treatment must match both host and accelerator exposure. Do not constrain the free Agent's action strategy. Report Official Pass@1 over all 24 sampled positions, plus non-submission, bootstrap failure, missing-import failure, source unavailability, explicit infrastructure failures, and unresolved attribution. Source compatibility, provider semantics, and runtime completeness are descriptive tags and do not override Official.

Complete exactly the 24 positions, with no outcome-driven early stopping, replacements, or F/N/A2 continuations. Report tokens, time, and cost rather than using them as success thresholds. Record safety-timeout events separately. Report observed success bounds and conditional opportunity rates; the target population is authorized Dev, not the entire benchmark.

Only after establishing actual strong-Agent terminal failures should a new same-active-session independent-replay contrast be proposed. Failures before a complete program exists remain an explicit boundary of the replay mechanism.

Actual configuration: `gpt-5.6-sol`, `xhigh`, and Codex CLI `0.153.4` as observed immediately before launch. Historical P0 exposed only `envsolve_container.envbench_shell`: a persistent construction shell allowing installation, inspection, testing, and public Pyright-goal execution. It had no online Official feedback and no dedicated fresh-container replay tool. It must not be described as unrestricted Codex.
The census baseline can create fresh containers and test its own complete programs through general-purpose execution, without an EnvSolve automatic replay-feedback policy. Preserve that voluntary ability equally in future arms. The qualification evidence is recorded in `research/envsolve_pro_free_agent_environment_capability_v1_report.md`.

Position 1, `cclib`, is complete. The free Agent submitted a program and performed voluntary replay in three fresh environments; its final replay observed zero missing imports on the public goal. Independent Official later exited during bootstrap when the `requirements-dev.txt` checkout of `pyquante2` encountered repeated GitHub GnuTLS failures, so no Pyright report was produced and whole-sample success is false. The submission also generated type-only `PyQuante` and `pybel` interfaces without corresponding runtime modules, violating the preregistered legitimate-deployment boundary. This establishes a real terminal failure but not an automatic-clean-replay benefit: the free Agent had already replayed and observed a pass. The record is `experiments/validations/envsolve_pro_free_agent_census24_v1_position01_result.json`.

Position 2, `django-lfs`, produced a complete program and voluntarily replayed it in one fresh environment, where it observed a public-goal pass. The old V6 validator then misclassified the functional compatibility package's `setup.py`, rooted under an external `mktemp -d` directory, as a repository configuration write and terminated the run before Official. The position remains `boundary-censored` in the denominator of 24 and will not be rerun. V6.1 solely admits configuration targets explicitly rooted at an unrebound `mktemp -d` variable to the existing execution and audits, while explicitly rejecting position-1-style `.pyi` providers. It applies from position 3. Offline acceptance of the old candidate under the revised static rule is sensitivity analysis only and does not alter the primary record. See `research/ENVSOLVE_PRO_FREE_AGENT_CENSUS_BOUNDARY_AMENDMENT_V1.md` and `experiments/validations/envsolve_pro_free_agent_census24_v1_position02_boundary_censoring.json`.

Position 3, `lark`, passed the Official metric with zero missing imports (and 662 non-goal Pyright errors), but legitimate deployment success is false. The Agent installed PyPI `js==1.0`; its package archive and dependencies identify it as a Fanstatic root package, while the repository explicitly imports Pyodide browser-runtime objects `window` and `eval` from `js`. This is a same-name provider that zeros the proxy metric without supplying the intended semantics, not an algorithmic success. The Agent had already replayed the complete program in two voluntary fresh environments and observed a public-goal pass, so the position does not support automatic-replay gain either. A separate postepisode audit false positive treated the pre-existing mode-`160000` Gitlink `tests/test_nearley/nearley` as a synthetic empty package. It did not block Official and will not trigger a mid-census rule change. The machine record is `experiments/validations/envsolve_pro_free_agent_census24_v1_position03_result.json`.

Position 4, `getnikola/plugins`, passed the Official metric with zero missing imports (and 777 non-goal Pyright errors), but legitimate deployment success remains false. The free Agent performed two voluntary clean replays and repaired the first replay's network and fail-fast problems before observing a public-goal pass in the second. The sole real import check had already shown that `CommonMark 0.5.4` fails on Python 3.12 because `HTMLParser.unescape` is absent, and no later runtime pass occurred. Qualification audits also falsely rejected tracked symlinks and a functional project-local environment directory. Those false positives do not erase the known runtime failure and did not block Official. See `experiments/validations/envsolve_pro_free_agent_census24_v1_position04_result.json`.

Execution-topology correction: prior prose claiming that Spark ran Official was wrong. Construction, Agent-visible validation, and qualification replay for positions 1-4 ran on Spark; Official was launched by the Mac-local EnvBench process through its then-current local Docker context. Position 4 was observed as `desktop-linux`; positions 1 and 3 did not record the context. Both sides used the same image digest and `linux-aarch64`, but network, cache, and GPU exposure differed. Original records remain preserved; see the explicit correction in `experiments/validations/envsolve_pro_free_agent_census24_v1_positions01_04_topology_correction.json` and the stage decision in `research/ENVSOLVE_PRO_CENSUS_POSITIONS01_04_STAGE_REPORT.md`.

The current 24-position batch resumed on the repaired single-host path at position 5, and AgentHub will not be inserted into the already-started batch. Positions 1-4 used the discovered dual-host path: Spark for construction and replay, and Mac-local EnvBench for Official. Positions 5-24 use Spark for construction, replay, qualification, and Official. AgentHub has only about 5 GiB free. Before the next method comparison, cases will be stratified by GPU requirement: a CPU block fixed to AgentHub and a GPU block fixed to Spark, with every method for a case kept on the same host and resource condition. Roughly 22 GiB of old strong-A/B census workspaces on AgentHub must be migrated or removed before that CPU lane is reliable.

Supervisor adjudication on 2026-09-08 makes EnvBench Official Pass@1 the decisive
success outcome for this census. Source edits, compatibility modules, provider semantics,
and runtime completeness remain descriptive path-quality tags and do not override an
Official result. Accordingly, positions 3 and 4 are Official successes despite their
preserved semantic-risk annotations; their historical machine records remain unchanged.

Position 5, `meshio`, is the first completed member of the repaired single-host block.
The free Agent replayed its final complete program in an Agent-visible fresh Spark
environment, post-session qualification independently replayed the same program without
returning feedback, and Spark EnvBench Official passed with zero missing imports. The
program creates `src/meshio/vtk_io.py` by copying the checkout's `_vtk_common.py`; this is
recorded as a source-compatibility tag but does not negate the Official pass. Because the
free Agent already used voluntary complete-program replay and succeeded, this position is
not eligible for failure-conditioned treatment and provides no evidence for promoting an
automatic replay mechanism. The machine record is
`experiments/validations/envsolve_pro_free_agent_census24_v1_position05_result.json`.

Position 6, `mashumaro`, also passed Spark Official with zero missing imports. The
free Agent voluntarily replayed the complete ordered installation sequence in one fresh
environment and observed a public-goal pass. Its final submission expressed the same
operations with fail-fast `&&` chaining, so the voluntary replay was operationally
equivalent but not byte-identical; the exact final program subsequently passed independent
post-session qualification without Agent feedback and then passed Official. This is a
second strong-Agent success and is not eligible for failure-conditioned replay treatment.
See `experiments/validations/envsolve_pro_free_agent_census24_v1_position06_result.json`.

Position 7, `lnldb`, is an Official Fail@1. The submitted program passed both the free
Agent's voluntary complete-program replay and independent post-session qualification on
Spark, but Official bootstrap exited while cloning the declared `jsmin` Git dependency
after a GnuTLS termination and produced no Pyright report. The Official failure is the
primary result. Dependency-download failure, executable Django compatibility modules, and
the separately observed `collections.Iterable` runtime incompatibility are descriptive
tags only. This does not yet demonstrate automatic replay gain because two prior executions
of the same installation succeeded and transient network variation is a competing cause.
See `experiments/validations/envsolve_pro_free_agent_census24_v1_position07_result.json`.

Position 8, `pyvespa`, passed Spark Official with zero missing imports. One initial
construction command encountered a PyPI read timeout; the free Agent added explicit
timeout and retry settings, completed the installation, and voluntarily replayed it in a
fresh environment. The exact final program then passed independent qualification and
Official. This is a free-Agent self-repair success and provides no automatic-replay gain.
See `experiments/validations/envsolve_pro_free_agent_census24_v1_position08_result.json`.

Position 9, `neurogym`, passed Spark Official with zero missing imports. The free Agent
continued an installation after a fresh-environment observation timeout, then repaired a
NumPy 2 runtime incompatibility with `numpy<2`; seven core tests passed and the public goal
reported zero missing imports. The exact final program passed independent qualification
and Official. It creates the missing functional compatibility module
`neurogym/utils/test_plotting.py`; that operation is retained as a source-compatibility tag
and does not override Official. A legacy clean-tree audit rejected the untracked file in
the construction workspace, but the same scheduled run still completed through the
Official-primary path. The position is therefore not boundary-censored and provides no
automatic-replay gain. See
`research/ENVSOLVE_PRO_FREE_AGENT_CENSUS_POSITION09_PROTOCOL_NOTE.md`.

Positions 5-9 are complete and position 10 is next in the unchanged fixed order. AgentHub
remains outside this census. Its Docker
Desktop daemon is available as `linux/aarch64`, but the host has only about 5 GiB free;
approximately 22 GiB is held by two old strong-A/B census workspaces. After separately
approved cleanup, AgentHub can run a preassigned CPU-only lane in the next method
comparison without altering this census topology.

### Review Needed

The supervisor accepted the historical closeout with deviations and subsequently approved Experiment 2 after the repeatability result. The generic free-Agent environment capability is qualified, the fixed sample is recorded in `experiments/schedules/envsolve_pro_free_agent_census24_v1.json`, and position 1 has completed as an Official failure. This does not authorize treatment Phase 2 or release protected data. No frontier, cross-case memory, checkpoint search, or symbolic constraint framework is added.
