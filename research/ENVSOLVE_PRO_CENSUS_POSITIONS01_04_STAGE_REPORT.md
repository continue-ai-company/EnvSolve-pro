# EnvSolve-Pro Census Positions 1-4 Stage Report / 普查位置 1-4 阶段报告

## 1. 主要矛盾 / Primary Contradiction

当前测到的不是一个干净的“自由 Agent 对自动 replay”问题。自由 Agent 在三个成功提交程序的位置都主动创建了新环境，并在失败后修改整份程序再次重放；与此同时，Agent 可见 replay 在 Spark，而 Official 在 Mac Docker。系统因此混合了三件事：Agent 自带的 loop、跨主机网络与缓存差异，以及 EnvBench 只检查 missing import 的代理目标。

The current protocol does not isolate free Agent versus automatic replay. In all three positions with a submitted program, the free Agent voluntarily created fresh environments and revised the complete program after failures. Agent-visible replay ran on Spark while Official ran through Mac Docker. The observations therefore mix the Agent's own loop, cross-host network/cache differences, and EnvBench's missing-import proxy.

## 2. 最强证据 / Strongest Evidence

| 阶段 | 位置 1-4 的实际位置 | 定点证据 |
| --- | --- | --- |
| Codex session 与调度 | Mac arm64 | 每个 `generation/result.json` 的 Codex 命令和 `agent_host_role=control-only` |
| 构建、Agent 可见验证、自愿 fresh replay | Spark，Linux aarch64，NVIDIA GB10，GPU 全部暴露 | 每个 `generation/result.json` 的 `execution_backend.ssh_target`；`environment-lifecycle.jsonl`；各 `environment-*-commands.jsonl` |
| episode 后资格程序执行 | Spark remote Docker；位置 2 未进入 | `generation/submission-qualification/result.json` 与 `execution_backend=codex-qualified-ssh-remote-docker-v1` |
| runtime alias check | Spark 资格容器 | 资格结果 `bootstrap.stdout` 中的 `ENVSOLVE_IMPORT_ALIAS_AUDIT_V1` |
| effect scan | Spark 状态同步回 Mac 后，在本地 checkout 上扫描 | `RemoteDockerCommandAdapter` 在 `docker exec` 后 `sync_from_remote`，随后 verifier 调用 `inspect_repository` |
| Official | 位置 1、3、4 由 Mac-local EnvBench 启动；位置 2 未运行 | `envsolve_harness/adapters/envbench_executor.py` 直接本地调用 `uv run ... evaluation/main.py`；位置 4 当场观测 Docker context 为 `desktop-linux` |

Spark 与 Mac Docker 都是 `linux-aarch64`，并使用同一镜像 digest `sha256:7bcf...c3d4`。但网络出口、源代码缓存、包缓存和 GPU 暴露不同。位置 1 的 Official GnuTLS 失败发生在 Mac 路径，不能据此断言 Spark replay 本身漏检了一个同主机可复现错误。位置 1、3 的历史 Docker context 没有记录，只能确认它们经过 Mac-local evaluator 的当时 context；位置 4 已现场确认是 Mac Docker Desktop。

位置 4 进一步证明代理目标与真实部署不同：第二次自愿 clean replay 和 Official 都得到 0 missing import，但唯一一次真实 import 检查在 `CommonMark 0.5.4` 上因 `HTMLParser.unescape` 缺失而失败，并暴露多组冲突依赖。`scripts/generated.sh` 与 `scripts/bootstrap.sh` 字节相同，SHA-256 均为 `30a963...4d06`；Official 日志也嵌入同一程序。Agent session 在 Official 启动前结束，任何资格或 Official 输出都没有返回 Agent。

位置 4 的精确证据根目录是 `runs/envsolve-pro-free-agent-census-v1/mac-controller/free-agent-census24-v1-04-A/envbench-python-getnikola__plugins__b4a4cd1332d4c149bef9c0b884e8f7045327cbf1/`。其中 Agent 命令与 runtime failure 在 `generation/container-commands.jsonl`，环境生命周期在 `generation/environment-lifecycle.jsonl`，资格结果在 `generation/submission-qualification/result.json`，Official 原始结果在 `evaluation/json/results.jsonl`，提交程序分别在 `scripts/generated.sh` 和 `scripts/bootstrap.sh`。

哈希勘误：资格记录的 `6937f06f...` 是 2,344-byte canonical 文本的哈希；资格程序文件与两个 Official 脚本均为同一文本加一个末尾 LF，共 2,345 bytes，文件哈希为 `30a96355...`。运行 manifest 固定 harness revision `d829f55...` 且 `dirty=false`；该版本的 verifier 直接执行 canonical 文本。故这里没有第二份程序，但此前把两种哈希都称为“程序 SHA-256”不够精确。完整证据见 `experiments/validations/envsolve_pro_free_agent_census24_v1_position04_program_hash_correction.json`。

The phase map above is supported by the same artifacts. Spark and Mac Docker are both `linux-aarch64` and use the same image digest, but they differ in network egress, source/package caches, and GPU exposure. Position 1's Official GnuTLS failure occurred on the Mac path and cannot establish that a same-host Spark replay missed the failure. Historical Docker contexts for positions 1 and 3 were not recorded; position 4 was observed as Mac Docker Desktop.

Position 4 also separates proxy success from deployment validity. Its second voluntary clean replay and Official both reached zero missing imports, but the only runtime import check failed in `CommonMark 0.5.4` because `HTMLParser.unescape` is absent and exposed incompatible dependency requirements. `scripts/generated.sh` and `scripts/bootstrap.sh` are byte-identical with SHA-256 `30a963...4d06`, and the Official log embeds the same program. The Agent session ended before qualification and Official, so neither output was returned to it.

## 3. 最强反证或替代解释 / Strongest Counterevidence Or Alternative

位置 4 的 `.envsolve-legacy` 没有被 Git 跟踪，也没有修改 tracked project source；它是提交程序创建、加入 `PYTHONPATH` 的本地执行环境，并含有来自 PyPI、CPython 2.7 和 `creole` 上游源码的真实实现。当前 effect audit 仅因这些 726 个可导入文件位于 checkout 下就全部拒绝，无法区分环境与伪 provider。资格 alias audit 还把项目原有的 tracked symlink `site/v7`、`site/v8` 误判为未声明别名。因此 audit fail 本身不能证明作弊。

反过来，真实上游源码也不自动等于可用环境：位置 4 没有通过运行时验证，已知 `CommonMark` import 会失败。位置 3 的 Official pass 也来自语义错误的同名 `js` 包。于是当前最强替代解释是：自由 Agent 很擅长优化 missing-import 代理目标，但这四例尚未证明它完成了真实部署；同样也没有证据证明自动 replay 比它自身的 loop 更强。

In position 4, `.envsolve-legacy` is untracked, does not modify tracked project source, and is an execution environment created by the submitted program and added to `PYTHONPATH`. It contains real upstream implementations from PyPI, CPython 2.7, and `creole`. The effect audit rejected all 726 importable files solely because they were below the checkout, while the alias audit rejected pre-existing tracked symlinks `site/v7` and `site/v8`. The audit failure alone is therefore not evidence of cheating.

Real upstream source is not automatically a working environment, however: position 4 failed its runtime check, and position 3 passed Official using a semantically unrelated same-name `js` package. The strongest alternative explanation is that the free Agent effectively optimizes the missing-import proxy without completing a real deployment. There is still no evidence that automatic replay is stronger than the Agent's native loop.

## 4. 建议裁决 / Recommended Decision

`Live frontier` 继续保持 kill，只作诊断。最小 B 保持 challenger，不进入核心算法：四个位置里没有一例满足“自由 Agent 终局失败，而最小 B 在同资源下 Official Pass”。当前 Official 数值可以保留为榜单观测；位置 1-4 只能解释为已发现双主机协议下的强 Agent 行为，不能进入未来 A/B 因果比较。位置 5 暂停，等待是否终止或修订本批的监督裁决。

边界建议先不实施：硬边界只保护 evaluator、目标配置和 Git tracked project source；不再按目录名或 `.py/.pyi` 存放位置阻断完整程序进入 Official。provider 合法性改为 episode 后行为判定：必须来自可追溯实现，并至少通过项目相关的真实 import 或 smoke path；仅让静态名字可解析不算部署成功。这一定义能统一处理位置 1 的类型占位、位置 2 的功能兼容包、位置 3 的同名错包和位置 4 的本地兼容环境，不需要 case 特例。

Keep `Live frontier` killed except as a diagnostic. Retain minimal B only as a challenger: none of the four positions demonstrates free-Agent terminal failure followed by same-resource minimal-B Official success. Official scores remain benchmark observations; positions 1-4 describe behavior under the discovered dual-host protocol and must not enter future causal A/B comparisons. Position 5 remains paused pending supervision.

Do not yet implement the proposed boundary. The hard boundary should protect only the evaluator, goal configuration, and Git-tracked project source; it should not block complete programs based on directory names or `.py/.pyi` location. Provider legitimacy should be decided postepisode by behavior: a traceable implementation must pass at least one project-relevant real import or smoke path, while static name resolution alone is insufficient. This single rule covers positions 1-4 without case-specific exceptions.

## 5. 下一项最高信息增益实验 / Highest-Information Next Experiment

先修正为单主机 target-state 路径并做一个 consumed calibration：同一台 Spark 上完成构建、Agent 可见 clean replay、资格重放和 Official，记录 Docker context、镜像、架构、GPU、缓存和网络路径；Agent 仍不得看到 Official。calibration 只验证程序身份与主机一致性，不验证算法收益。通过后，再从未用于本轮选择的 consumed Dev 中预先固定真实 Official bad case，运行唯一差异为“同一活跃 session 是否自动收到完整程序 clean replay 反馈”的 A/B。核心成功证据仍是 A 直到请求上限失败、B 提交合法程序并 Official Pass。

AgentHub 不应插入当前位置 1-4 批次。释放至少约 30 GiB 后，它可承担单独预注册的 CPU block，但每个 case 的构建、两臂 replay、资格和 Official 都必须留在 AgentHub；Spark承担另一个固定 GPU block。这样第二实验机提供并发吞吐，而不制造主机混杂。

First repair the target-state path to one execution host and run one consumed calibration: construction, Agent-visible clean replay, post-session qualification, and Official all run on Spark, while recording Docker context, image, architecture, GPU, cache, and network path. Official remains hidden from the Agent. The calibration tests program identity and topology only, not algorithmic gain. Then preregister genuine Official bad cases from consumed Dev and run A/B where the sole difference is whether the same active session automatically receives complete-program clean-replay feedback. Decisive evidence remains A failing through its request allowance while B submits a legitimate program and Official passes.

Do not insert AgentHub into positions 1-4. After freeing at least about 30 GiB, use it for a separately preregistered CPU block where construction, both arms, replay, qualification, and Official remain on AgentHub. Keep a separate fixed GPU block on Spark. This adds throughput without host confounding.
