# EnvSolve-Pro Dev Bad-Case Census V1 案例簿

状态：持续更新的 A-only census 记录，2026-08-10

本文档保存冻结的 209-case Dev census 中最有研究价值的反例。Official 结果是主指标，advisory qualification 单独记录；被基础设施故障截断的尝试不算算法失败。

## 暴露集更正（2026-08-24）

此前的 pending 状态只检查了 A-only census，没有覆盖完整研究历史，因此并不可靠。对本地
artifact、历史 artifact、已提交结果记录和 Spark artifact 做跨存储审计后发现：pending-census
文件的 205 个 case 中，203 个已经存在执行证据。仅 `fonttools/fontbakery`（位置 70）和
`vertica/verticapy`（位置 196）没有发现执行证据；二者保留，不能用于 ROL 机制开发。

最近恢复的 4 个 A case 在 ROL 之前都已经暴露，只能作为开发证据。BayBE、PortingDB 和
pywal16 均通过 Official。Reddit2telegram 首次 Official 被包索引 DNS 故障截断；同一脚本只重跑
evaluation 后通过 Official。更新后的 A 快照为 54 个终局 episode：43 个非基础设施截断的
Official-primary 结果中 32 个 Pass、11 个 Fail，另有 6 个终局基础设施截断和 5 个 Official 前
算法失败。本更正取代下文已经过时的“等待裁决”和“当前 census 快照”，但不改写历史记录。
机器可读证据位于
`experiments/validations/envsolve_pro_v2_case_exposure_audit_20260824.json`。

## 已确认的 Official 失败

| Case | 终端机制 | 当前分类假设 | 研究价值 |
|---|---|---|---|
| `Quantum-Accelerators/quacc` | `tblite` 元数据或构建失败，Linux ARM 环境中没有可用的 LAPACK 配置 | 操作层：原生或系统依赖落地 | Agent 从早期网络超时中恢复了，但最终停在确定性的架构相关构建义务上。 |
| `ajenti/ajenti` | 构建隔离环境无法解析所需的 setuptools 环境 | 约束层：构建后端与隔离环境兼容性 | 安装项目依赖还不够，隔离构建环境可能拥有不同的依赖边界。 |
| `andrew-codechimp/HA-Battery-Notes` | `ulid-transform` 的隔离构建无法解析 Cython | 约束层：传递性的构建期依赖 | Agent 的运行时依赖推理没有覆盖源码包的传递构建义务。 |
| `basxsoftwareassociation/basxconnect` | Official 新容器中，`setuptools_scm` 因 Git dubious ownership 失败 | 观测层/操作层：干净重放时的所有权漂移 | 构建容器中能够成功，但提交脚本没有处理新环境中发生变化的部署事实。 |
| `bradenm/micropy-cli` | bootstrap 完成，但 Official Pyright 仍有 1 个指向仓库内不存在的 `micropy.cli` 模块的 `reportMissingImports` | 约束层/操作层：已知约束缺少合法落地动作 | Agent 在提交前已经观察到同一个缺失导入，并验证过临时 synthetic stub 可以消除它；但该源树产物不合法，Agent 正确删除后仍在没有合法替代动作的情况下提交。另 310 个 Pyright error 只是非计分诊断。 |
| `castagnait/plugin.video.netflix` | 首次被基础设施截断后，终局 Official bootstrap 因 pip 返回空的 `setuptools` 版本集合而失败 | 因果归因未决；很可能是上游索引解析 | 冻结的 Official 规则将其计为 Fail，但该包确定存在，且首次尝试曾拿到其 metadata。它进入 Official 失败分母，但不能用于提出新的算法规则。 |
| `claritychallenge/clarity` | Official 新 checkout 中，`setuptools_scm` 在 Pyright 运行前因 Git dubious ownership 失败 | 观测层/操作层：干净重放时的所有权漂移 | 这是对 `basxconnect` 机制的独立重复。Advisory replay 因 checkout 所有权语义不同而通过，暴露了当前 replay 工具的具体保真度缺口。 |
| `cvxgrp/cvxportfolio` | 隔离构建环境在 Pyright 之前返回“没有可用的 `setuptools` 版本” | 因果归因未决；很可能是上游索引解析 | 因为没有命中冻结的基础设施签名，Official 规则必须把它计为 Fail；但 construction 已安装过同一项目，所以它重复了 `plugin.video.netflix` 的归因歧义。在确定性复现前不能据此提出算法规则。 |
| `datamol-io/graphium` | editable install 在 Official 新 checkout 中因 `setuptools_scm` 遇到 Git dubious ownership 而失败 | 观测层/操作层：干净重放时的所有权漂移 | 这是 `basxconnect`/`clarity` 机制的第三次独立出现。提交路径还仅仅把 PopTorch 源码暴露成静态 namespace，没有安装可执行 SDK，因此 replay 正确性和部署完整性都失败。 |
| `econ-ark/hark` | editable metadata 生成在 Official 新 checkout 中因 `setuptools_scm` 遇到 Git dubious ownership 而失败 | 观测层/操作层：干净重放时的所有权漂移 | Construction 和 advisory fresh replay 都通过，但两者都没有复现 Official checkout 的 ownership。这是该机制的第 4 个 primary Official 失败；计入 Bigbang counterfactual 后是第 5 次独立复现。 |
| `emi-group/evox` | 同一脚本刚通过 advisory fresh replay，Official build isolation 却返回找不到任何 `setuptools>=61.0` 版本 | 因果归因未决；很可能是上游索引解析 | 冻结规则将其计为 Fail，但它重复了 `plugin.video.netflix` 和 `cvxportfolio` 的间歇性空 setuptools candidate set。在确定性复现前不能据此提出算法规则。 |

## 已确认的 Official 前系统失败

| Case | 终端机制 | 当前分类假设 | 研究价值 |
|---|---|---|---|
| `datactive/bigbang` | 强 Agent 完成 31 次命令并返回 bootstrap，但冻结的 candidate policy v5 拒绝了写入由 `mktemp -d` 变量指向目录的 `pyproject.toml` 和 `setup.cfg` | 操作层：保守 candidate boundary 的假阳性 | 这是结构化安全约束会压制强 Agent 的直接证据。同一程序的 counterfactual 也因 fresh-checkout Git dubious ownership 失败，所以该假阳性在这个 case 上没有损失一个榜单 Pass。 |
| `dbiir/uer-py` | Agent 返回的程序把 TensorFlow 已安装的 `python/keras` 目录链接成 `tensorflow/keras`；冻结 candidate policy 拒绝 Python import path 内的符号链接 | 操作层：拒绝第三方 import 布局改写 | 被拒绝的同一程序随后在 fresh、非计分 Official 诊断中以 0 issues 通过。按预注册规则 A 仍为 Fail，但这证明 v5 的类别式硬边界删除了一条能通过榜单的路径。 |
| `ellmetha/django-machina` | Agent 在真实依赖安装后创建空的 `tests/settings_local.py`；冻结 candidate policy 以“直接生成 importable artifact”为由拒绝 | 操作层：拒绝项目本地配置产物 | 被拒绝的同一程序随后在 fresh、非计分 Official 诊断中以 0 issues 通过。按预注册规则 A 仍为 Fail，但这是类别式执行前拒绝造成的第 2 个已证实榜单 Pass 损失。 |
| `dfki-ric/phobos` | Agent 安装了大量真实依赖，并生成两个本地 `.pyi`-only distribution；冻结 candidate policy 拒绝直接生成可导入类型桩 | 操作层：拒绝生成的类型桩产物 | 同一程序的诊断更早因 fresh-checkout Git dubious ownership 失败，因此无法证明边界是否损失 Official Pass。该路径还独立暴露部署完整性问题，并构成第 6 次 ownership 复现。 |
| `dtmilano/androidviewclient` | Agent 把空的 Python 2 GUI 兼容模块和没有行为的 Android MonkeyRunner 类封装成本地 wheel；冻结 candidate policy 拒绝直接生成可导入产物 | 操作层：拒绝 synthetic legacy-import wheel | 被拒绝的同一程序在 fresh、非计分 Official 中以 0 issues 通过。这是类别式拒绝损失的第 3 个已证实榜单 Pass，同时也是明显不完整的部署路径。 |

## 已确认通过且有诊断价值的 case

| Case | Official 结果 | 诊断价值 |
|---|---|---|
| `adamchainz/django-mysql` | Pass | Linux ARM 上较直接的强 Agent 成功案例。 |
| `ansible/molecule` | Pass | advisory qualification 失败但 Official 通过，证明本地资格检查不能替代榜单指标。 |
| `astropy/reproject` | Pass | 复杂科学计算依赖栈通过 Official，尽管 advisory 对安装产物有异议。 |
| `alteryx/featuretools` | 同一脚本网络重试后 Pass | 首次 `files.pythonhosted.org` 超时是基础设施截断，不是算法失败。 |
| `automl/neps` | Pass | 37 步连续 Agent 轨迹和 clean replay 均成功，它更适合研究路径成本与最小化，而不是成功率修复。 |
| `beeware/briefcase` | Pass | 12 步 Agent 轨迹和两行提交脚本通过 clean replay 与 Official，提供了相对高效的成功路径。 |
| `benthayer/git-gud` | Pass | advisory qualification 拒绝了一个安装产物，但冻结脚本以 0 issues 通过 Official。这说明审计边界还需校准，并不说明算法失败；148 个 Pyright error 均为非计分诊断。 |
| `brainglobe/brainrender` | Pass | advisory qualification 认为候选没有正常交还控制，但同一冻结程序通过了 Official。这是第二个 qualification 假阴性，也是校准边界的高价值案例。 |
| `bottlecapdave/homeassistant-octopusenergy` | Pass | Agent generation 和 clean replay 均通过；Official 也通过，但仍有 1,299 个非计分 Pyright error，再次说明总错误数不是榜单目标。 |
| `cantools/cantools` | Pass；部署完整性有红旗 | 程序创建了空的 `site-packages/StringIO` namespace，而没有安装可执行的 `StringIO` 行为。它满足 Official missing-import 目标，但被保留为“指标对齐、环境不完整”的反例。 |
| `bradyajohnston/molecularnodes` | Pass；部署完整性有红旗 | 30 次命令、149 万 input tokens 的路径把 cp37 `pyopenvdb` wheel 改成 py3-any，并使用 `fake-bpy`。Official missing import 为 0，但运行时兼容性没有得到证明。 |
| `censys/censys-python` | Pass | 9 次命令、约 21.3 万 input tokens 的路径使用普通 editable install，clean replay 为 42 秒，Official 为 31 秒，是高效且相对完整的成功路径。 |
| `cherrypy/cheroot` | Pass | Advisory clean replay 因临时的 docs extra 解析失败仍有 32 个 missing imports，但同一冻结脚本通过 Official。这是第 7 个假阴性，说明 replay 证据应先分类再返回 Agent，而不能成为硬提交门。 |
| `calliope-project/calliope` | Pass | 程序安装 GLPK、创建 Python 3.10 venv、安装项目和开发依赖，并同时通过 clean replay 与 Official，是相对完整的系统依赖加 Python 依赖成功路径。 |
| `cda-tum/mqt-bench` | Pass | 22 步轨迹用显式 pin 解决了历史 `pytket`/`pytket-qiskit` 冲突，164 秒通过 clean replay，并以 0 missing import 通过 Official；其余 114 个 Pyright error 不计分。 |
| `ceph/ceph-ansible` | Pass；部署完整性有红旗 | 程序把仓库内受 Git 跟踪的 `module_utils/ca_common.py` 重新封装成未声明的 inline wheel，并安装到 Ansible namespace。Official 接受了 0 missing import 环境，但 advisory provenance 拒绝该路径；这是指标成功，不是完整 Ceph-Ansible runtime 部署证据。 |
| `cityofzion/neo3-boa` | Pass；部署完整性有红旗 | 程序为旧的负例测试 import 安装了一个空的 synthetic `boa3-stubs` wheel。Advisory 与 Official 都得到 0 missing import，但 Official 仍有 5,796 个不计分 error。由于 wheel 声明的 top-level token 不是合法 Python 标识符，审计没有发现它；这是指标成功，不是完整 runtime 部署。 |
| `conan-io/conan-package-tools` | Pass；部署完整性有红旗 | 25 步路径先安装 Conan 1.6.1，再叠加 Conan 1.66.0，使旧内部模块与新文件共存。Fresh replay 和 Official 都通过，但 runtime 版本一致性没有得到证明。 |
| `couchbase/cbmonitor` | Pass；部署完整性有红旗 | 12 步短路径把旧依赖替换成包括 Django 6.1 在内的当前软件包。Official 以 0 missing import 通过，advisory replay 是假阴性；老应用的兼容性没有测试。 |
| `de7vid/klingon-assistant-data` | Pass | 10 步、约 15.3 万 input tokens 的路径使用普通 venv，安装声明依赖和两个额外 import 包，同时通过 clean replay 与 Official，是一个有用的高效路径对照。 |
| `democracyclub/uk-polling-stations` | Pass | 程序安装全部文档化 requirements 和构建中发现的额外 import，按受 Git 跟踪的模板生成被忽略的本地设置，并同时通过 fresh replay 与 Official。Official 在 733 个文件中仍保留 2,620 个不计分 error，是榜单目标非常狭窄的强例证。 |
| `democracyclub/everyelection` | Pass | 27 步路径安装较完整的 Django、CDK 和测试依赖，并安装两个固定版本的 DemocracyClub 包，再按受 Git 跟踪的示例生成本地设置，同时通过 clean replay 与 Official。它是相对完整的成功路径，但运行时服务仍未测试。 |
| `diefenbach/django-lfs` | Pass；部署完整性有红旗 | 程序编译 CPython 2.7，并把其 hotshot 源码和 cStringIO 扩展暴露到 Python 3.13 PYTHONPATH。Official 接受了 0 missing import，但仍有 1,284 个不计分 error；这是指标成功，并不能证明跨运行时可执行。Advisory replay 是网络假阴性。 |
| `dnarayanan/powderday` | Pass；部署完整性有红旗 | 66 步、274 万 input tokens 的路径安装大型科学计算栈，随后为空缺的旧 import 创建空 namespace 目录。Clean replay 和 Official 都通过，但这些空路径使它成为“指标成功”和“可执行部署”分离的强反例。 |
| `eastsidepreparatoryschool/epschedule` | Pass；部署完整性有红旗 | 25 步轨迹用 `--no-deps` 安装具备目标 import 的发行包，52 秒通过 clean replay，19 秒通过 Official。missing-import 目标已满足，但传递运行时依赖是否完整没有得到证明。 |
| `dj-stripe/dj-stripe` | Pass | 常规本地 venv 和 editable project install 同时通过 clean replay 与 Official。轨迹中没有发现完整性红旗，但运行时服务仍未测试。 |
| `ecds/readux` | 同一脚本网络重试后 Pass | 首次 Official 被 `files.pythonhosted.org` read timeout 截断；不改脚本的重试以 0 missing imports 通过。Advisory provenance 把 requirements 声明的 editable dependency checkout 错判为未声明本地分发。 |
| `facebookresearch/hydra` | Pass；部署策略边界有红旗 | 52 步、262 万 input tokens 的路径构建 Python 3.10 环境并安装大量真实依赖，还把两个受 Git 跟踪的 ANTLR 生成文件从 `typing.io` 改为 `typing`。Official 通过，advisory repository-effect policy 因 tracked changes 拒绝；这把 generated-source compatibility repair 与普通环境安装区分开了。 |

## 终局为基础设施 censored 的 case

| Case | 证据 | 统计处理 |
|---|---|---|
| `ai4co/rl4co` | 两次 Official 都以 `files.pythonhosted.org` 读取超时结束 | 不进入 pass 分子，也不进入算法失败分母；不再允许替换性重试。 |
| `astropy/regions` | 首次为 Conda 包读取超时，重试为 `CondaHTTPError: HTTP 000 CONNECTION FAILED` | 不进入 pass 分子，也不进入算法失败分母；不再允许替换性重试。 |
| `cclib/cclib` | 首次 Conda 包下载出现 `ReadTimeoutError`/`IncompleteRead`；同一脚本重试以 `CondaHTTPError: HTTP 000 CONNECTION FAILED` 结束，两次都发生在 Pyright 之前 | 不进入 pass 分子，也不进入算法失败分母；不再重试。该轨迹仍用于部署完整性分析，因为它把 Python 2 时代的 PyQuante 文件复制进了 Python 3.13 环境。 |
| `convexengineering/gpkit` | 首次收到哈希不匹配的包字节；唯一一次同脚本重试收到被截断的 PyPI JSON，两次都发生在 Pyright 之前 | 不进入 pass 分子，也不进入算法失败分母；不再重试。该轨迹仍有价值：新版 Pyright 找到一个 `distutils.core` 缺失导入后，Agent 改装 `pyright==1.1.320` 将指标降为零，暴露了“改变 verifier 身份”这一独立测量风险。 |
| `columnflow/columnflow` | 首次 Official 以 Conda HTTP 000 连接失败结束；唯一一次原脚本重试在 clone cmsdb 时出现 GnuTLS 接收错误、意外断连、early EOF 和 invalid index-pack output | 不进入 pass 分子，也不进入算法失败分母；不再重试。未固定的运行时 clone 和 `root_base --no-deps` 仍是独立的鲁棒性与部署完整性问题。 |
| `eggpi/citationhunt` | 两次 exact-script Official 都在获取 defaults/conda-forge repodata 时出现 Conda HTTP 000，发生在项目安装和 Pyright 之前 | 不进入 pass 分子，也不进入算法失败分母；不再重试。Advisory fresh replay 达到 0 missing imports，但还把 conda-forge build-origin metadata 错判为本地 provenance。 |

## 等待裁决

- 当前没有活跃 A episode。`emdgroup/baybe` 和 `fedora-python/portingdb` 已分别冻结为 lane 1、lane 2 的下一个 outcome-blind case，但尚未启动。Hydra、CitationHunt 和 Readux 都已得到终局结果。此前通用 runner 错误启动的记录已撤销，不计为 A episode。
- `commaai/comma10k` 尚未进入 Agent session：其唯一 shallow-fetch 工作状态已增长到约 14 GB，在 600 秒 SSH 获取超时后仍在 Spark 后台继续。没有启动重复 fetch；等待原获取完成并写入不可变源码缓存后再裁决。

## 当前研究信号

当前最强的重复确定性失败机制仍是 clean-replay 所有权漂移：`basxconnect`、`clarity`、`graphium` 和 `hark` 都在各自主 Official 中失败，非计分的 Bigbang 和 Phobos counterfactual 又独立复现了同一机制。6 次独立复现说明当前 advisory replay 的 checkout 语义系统性偏弱。第二条矛盾现在有 3 个独立因果例子：UER-Py、django-machina 和 AndroidViewClient 被拒绝的同一程序都能通过 Official，证明类别式操作层硬规则会在第三方布局修复、项目本地配置和 synthetic compatibility packaging 上压制强 Agent 的有效路径。AndroidViewClient 也说明不能简单取消全部检查：它通过 Official 的路径几乎没有提供可执行的遗留行为。Phobos 的因果结论仍未确定，因为 ownership 在被拒绝的类型桩生效前就截断了 counterfactual。两类证据共同支持“session 内 Official 等价重放，加执行后的 provenance/effect 检查”，同时把榜单成功与部署完整性分开报告。A-only census 仍会在 treatment 选择前继续完成。

## 当前 census 快照

现在共有 50 个 A episode 得到终局结果。39 个非基础设施截断的 Official-primary 结果中，28 个 Pass、11 个 Fail；另有 6 个 case 最终被基础设施截断，Bigbang、UER-Py、django-machina、Phobos 和 AndroidViewClient 是五个由冻结 candidate boundary 导致的 Official 前算法失败。此前 29 条轨迹的资源快照中，Agent 命令数中位数为 24、范围为 6-77，输入 token 中位数为 685,007、范围为 141,263-4,435,262；本批次已关闭，可以原子重算资源统计。这些都是评估指标，不是停止阈值。四次通用 runner 启动错误已由 remote-runner invocation correction 显式排除。

Advisory clean replay 不能替代 Official：在 38 个同时具有二元 advisory 结果的非截断 Official 结果中，它有 16 个 true positive、6 个 true negative、12 个 false negative 和 4 个 false positive，与 Official 的一致率为 22/38；`cvxportfolio` 因控制面传输超时而没有 advisory replay，不进入该一致率计算。Official 前 boundary failure 及其非计分 counterfactual 都不进入该矩阵。因此 replay 证据应先分类再作为观测返回 Agent，但 Official 仍必须是主结果；advisory qualification 不应成为阻止提交的硬门槛。重复的 ownership、provenance 和 repository-effect mismatch 还说明：replay 只有在复现目标语义并把路径质量问题与榜单失败分开时才有价值。

## 暂定的三层失败矩阵

| Case | 观测层 | 约束层 | 操作层 | 提交时证据 |
|---|---|---|---|---|
| `quacc` | 轨迹看到了源码构建和架构相关软件包。 | `tblite` 需要可用的 LAPACK provider。 | 程序安装了编译器和 CMake，却没有安装 LAPACK。 | 没有证据表明精确提交程序完整执行通过。 |
| `ajenti` | 累积构建环境成功，但 fresh replay 进入了隔离构建环境。 | 隔离环境需要独立解析 setuptools。 | 程序只升级了父 venv 的 setuptools，没有控制 build isolation。 | fresh replay 失败发生在 Agent session 结束后，也没有返回给 Agent。 |
| `HA-Battery-Notes` | 构建环境报告 missing import 为 0；fresh replay 重新构建 `ulid-transform`。 | 隔离源码构建环境独立需要 Cython。 | 程序按常规方式安装 requirements，没有让构建依赖可复现。 | fresh replay 失败发生在 Agent session 结束后，也没有返回给 Agent。 |
| `basxconnect` | construction 与 Official replay 的 checkout owner 不同。 | Git 版本推断要求信任新的 checkout。 | 程序安装了项目，但没有规范化 Git safe-directory 状态。 | Agent 只验证了累积 construction state。 |
| `micropy-cli` | Agent 直接观察到仍缺少仓库中不存在的 `micropy.cli`。 | 在 admissibility boundary 下目标仍未满足。 | synthetic stub 有效但被禁止，Agent 没找到合法替代动作。 | Agent 明确提交了一个已知未满足的约束。 |
| `clarity` | Advisory replay 与 Official 使用了不同的 checkout 所有权语义。 | `setuptools_scm` 要求 Git 信任 Official checkout。 | 提交程序没有规范化 `safe.directory`。 | Agent 等价流程看到的唯一 exact-program replay 是 Pass，因此没有观察到 Official 中变化的事实。 |
| `graphium` | Construction 看到的是 root-owned checkout，Official 则在不同所有权语义的新 checkout 中评估。 | editable build metadata 需要 Git provenance，因此要求 checkout 被信任。 | 程序安装了依赖并暴露 PopTorch 源码，但没有规范化 `safe.directory`。 | Post-session advisory 拒绝的是另一个安装完整性问题，而且没有返回 Agent；Official 的 ownership 失败仍未被观察。 |

因此目前共享的假设是**提交时缺少重放证明**，而不是某一条共同的包管理规则。最小候选 treatment 是：在活跃 session 内提供一个工具，用 fresh environment 执行精确候选程序，返回最后一个确定性未满足约束，并让同一个 Agent 继续修订。它现在只作为未来对照的冻结假设；A-only census 仍按 outcome-blind 顺序继续，之后才能决定是否采用。
