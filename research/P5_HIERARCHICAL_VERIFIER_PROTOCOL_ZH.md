# P5 分层验证器协议

## 目标

P5 将 benchmark 成功与环境的可执行质量分开。它不修改 EnvBench 计分，而是记录
V0-V6 验证曲线，并使用源码与 metadata 证据，把 missing import 区分为当前有效的
repair obligation、非活动平台路径、项目明确排除的 fixture、受保护的可选功能或仍
未解决的 finding。

## 验证层级

| 层级 | 合约 |
| --- | --- |
| V0 | Bootstrap 退出码为 0。 |
| V1 | 声明的 metadata、已安装 distribution 与 resolver 状态一致。 |
| V2 | 未修改的 benchmark missing-import 检查通过。 |
| V3 | package import、entry point 与 CLI smoke probe 通过。 |
| V4 | 项目原生 test collection 或 build 成功。 |
| V5 | 适用的原生测试子集成功。 |
| V6 | 同一环境计划可在全新容器中重放。 |

`Official Pass` 仅按冻结的 benchmark 合约计算。`Robust Pass` 要求 V0-V4 与 V6
均明确成功，未知层级按失败处理；当 V5 适用时，`Native Pass` 还要求 V5 成功。
任何源码分类都不得修改 V2 或官方分数。

## V1 metadata-resolver 合约

V1 要求：具备 provenance 的项目 distribution、来自同一内容寻址 metadata 的精确
`Requires-Dist`、已安装 distribution 集合、显式 PEP 508 marker environment、显式
selected extras，以及断网条件下直接执行 `python -m pip check` 的结果。名称与版本分别
遵循 PEP 503 和 PEP 440。inactive marker 不产生 obligation；optional requirement
仅在对应 extra 被显式选择时生效。

只有每个 active 声明 requirement 恰有一个兼容 installed distribution 时 V1 才通过。
与项目闭包无关的 ambient distribution 即使版本字符串 malformed，也不能让项目失败。
由于裸 `pip check` 检查整个环境，无法归因到项目闭包的非零结果记为 `unknown`，而不是
项目失败。active 项目闭包内部的缺失、不兼容、歧义或 malformed 证据仍然失败。缺
provenance、marker environment 或 resolver evidence 时返回 `unknown`，绝不回退到
host environment。

## Import 证据

每个 `reportMissingImports` finding 都保留 module、仓库相对路径、从 0 开始的诊断
行号、源码哈希和原始诊断。P5 可在不修改仓库的前提下增加以下证据：

- 源码角色：runtime、test、documentation、fixture、build 或 vendored code；
- 捕获 `ImportError` 的外层 `try`；
- 在已观测平台/运行时下可静态判定为不活动的分支；
- 在当前环境中条件为真的测试 skip decorator；
- 默认关闭的可选函数分支；
- 与 fixture 路径匹配的仓库自有工具排除配置；
- 在当前环境中为假的声明式 dependency marker。

源码角色本身仅用于描述，不能让 finding 变为 non-blocking。项目排除规则只适用于
fixture finding，并必须记录产生该规则的工具和配置文件精确哈希。平台与分支结论
必须来自 AST 和已观测环境事实；无法求值的表达式保持 unresolved。默认关闭的可选
分支仅限外层函数声明字面量 `flag=False` 且 import 位于直接 `if flag` 分支中。
`port=None` 等默认值并非已观测调用参数，不得用于求解涉及该参数的比较表达式。

## V3 metadata smoke 合约

V3 只能从内容寻址的 installed-distribution snapshot 生成 probe：`METADATA`、显式
`top_level.txt` 与声明的 console entry point。不得从 distribution 或 repository 名
猜测 import 名。package 与 entry-point import 使用隔离 Python（`-I`），动态值仅通过
argv 传入；每个 console entry point 还必须通过不执行 CLI 的 PATH resolution probe。
V3 不假设任意 CLI 都实现 `--help` 或 `--version`。所有 probe 均不使用 shell、关闭
网络、在空目录中运行，并设置 30 秒超时。

V3 使用三值判定。只有至少规划一个语义 import probe、所有结果均为零退出、所有
console entry point 同时具备 import 与 CLI coverage，且没有 metadata 被拒绝时才
通过。非零退出或超时为失败；缺少 provenance、缺少 outcome、metadata 被拒绝或没有
语义 probe 均为 `unknown`，在 Robust Pass 中按失败处理。

## 修复与计分边界

- 当前有效的 runtime/test obligation 保持为 repair candidate。
- 当 active verifier 扫描到文档 finding 时，它仍是 repair obligation；只有显式声明
  documentation build 适用时，才要求对应 build verifier。
- 非活动平台 finding 不应安装到当前环境。
- 项目明确排除的 fixture finding 属于 benchmark-fidelity 证据，不能据此修改
  benchmark 配置。
- 受保护的 optional finding 必须通过功能专用 probe，才能支持 native capability claim。
- 继续禁止 import stub、源码修改、verifier 配置修改、宽泛 ignore 和
  repository-specific package map。

## Round 1 范围

Round 1 只读分析已经消耗的 Dev-5 产物，不调用模型，也不执行新的 benchmark case。
合成反例必须证明：仅凭路径名、未知平台表达式、没有 provenance 的 exclusion，以及
缺少 V3/V4/V6 的 Official Pass 都会 fail closed。

Canary-20 与 Official-Test-100 保持未检查。

## 截至 Round 9 的开发记录

- Round 1 对三个 open Dev-5 case 的 45 条保留 finding 做分类，并暴露出把任意函数
  默认参数当作运行时实参的不可靠规则。
- 预注册 Round 2 只把 Reticulum 中受 `port != None` 影响的 3 条 finding 从 inactive
  恢复为 active；active repair obligation 从 17 增至 20，finding identity 与官方
  outcome 均未变化。
- Round 3 用 14 个定向合成检查冻结 metadata 驱动的 V3 合约；EnvSolve 与 harness
  全量测试均通过。
- Round 4 在冻结 EnvBench image 中执行 5 个 clean source archive。3 个 bootstrap
  成功；Poetry 在 Docker 断网后通过 entry-point import 与 CLI probe。gpkit 和
  Reticulum 因 legacy editable install 不含 PEP 610 direct URL 而保持 V3-unknown。
  Inflect 与 pytest-xdist 因 Python wheel 下载 read timeout 在 bootstrap 阶段 blocked。
  本轮没有观测到 V3 fail，也没有执行官方 verifier。
- Round 5 预注册并合成验证保守的 legacy editable provenance：必须同时存在指向项目
  的 `egg-link` 与 canonical name 唯一匹配的项目自有 `.egg-info`；仍优先使用 PEP 610。
  真实验证与仅针对基础设施失败的重试尚未完成。
- Round 6 在显式网络切换确认后执行。Inflect 恢复并通过 V3，Poetry 保持为未改变的
  PEP 610 对照。legacy provenance 成功匹配 gpkit 与 Reticulum，随后暴露其
  `PKG-INFO` metadata 格式；xdist 越过此前下载 timeout 后，证明 Git archive 缺失
  setuptools-scm 所需 VCS 状态。
- Round 7 用 9 个定向合成检查冻结 V1 metadata-resolver 合约；本轮不宣称任何真实仓库
  V1 Pass，容器证据采集仍需后续 round 验证。
- Round 8 加入内容寻址的 `PKG-INFO` 支持，同时保持现代 `METADATA` 的精确哈希行为；
  缺失 installed metadata 时输出结构化 unknown，而不是中断 runner。
- Round 9 把 archive materialization 替换为干净的本地 detached Git checkout，在不读取
  脏 worktree 或 fetch 的前提下保留 `.git`。Dev-5 达到 5/5 bootstrap Pass；Docker
  断网后执行 24 个 metadata-derived probe，得到 5/5 V3 Pass，且 fail、unknown、
  collection error 均为 0。这仅是 V3 证据，不是 Official Pass。

## Round 10 设计审计修复

在继续优化更多开发 case 前，Round 10 先修复完整代码审计发现的方法与 verifier 缺陷。
约束引擎现在会拒绝互斥的有序 PEP 440 范围，并在所有路径一致排除 superseded fact；
context observation 按事件顺序选择最新事实，并显式执行 `pyenv root`，不再猜可执行文件
布局。V3 在部分 distribution 收集失败时 fail closed，以 entry-point resolution 替代
CLI `--help` 执行；V1 只在 active 项目闭包内判定 malformed version。核心 shell-trace
integration 不再 import EnvBench harness；V3 host runner 不再假设 `/private/tmp`，也不再
创建 EnvBench result artifact。事件重放已缓存并增量 apply，但完整 snapshot 物化仍是
已量化的扩展性优化目标。

EnvSolve 与 harness 全套测试目前为 181 tests passed。Round 9 的 24-probe V3 结果只保留
为旧 CLI convention 合约的历史证据，不能静默复用为 Round 10 新合约证据。

预注册的 Round 10 新合约回放得到 3/5 bootstrap Pass 与 3/5 V3 Pass。实际执行的
21 个 probe 全部通过，probe failure 和 collection error 均为 0。Inflect 在安装前停止，
原因是冻结 bootstrap 依赖一个外部 `build_output` 目录，而解耦后的 runner 不再隐式创建
它；Poetry 则在安装 build requirement 时连续两次遇到 `files.pythonhosted.org` read
timeout。二者分别记录为实验夹具不匹配和基础设施阻塞，既不算方法失败，也不算通过。

host runner 现在只通过预注册输入接受安全、检查路径冲突的 pre-bootstrap 目录，不包含
repository-name 分支，也不创建 benchmark result artifact。用户确认切换网络后，冻结的
Round 11 回放恢复了声明式 `build_output` 夹具，且没有修改 verifier policy。五个
bootstrap 全部通过；随后在 Docker 所有网络均断开的状态下执行 24 个 metadata-derived
probe，得到 5/5 V3 Pass，probe failure 与 collection error 均为 0。Round 10 的三个
pass 保持不变，Inflect 与 Poetry 分别从预注册的夹具 unknown 和基础设施 unknown 转为
V3 Pass。

Round 11 只关闭了新合约下的 V3 Dev-5 回放要求，不代表 Official Pass 或 held-out
泛化结论。真实 V1、V4、V6 证据仍未补齐，因此 P5 尚未冻结；Canary-20 与
Official-Test-100 继续保持未检查。

## Round 12 V1 证据设计

在观察任何真实 V1 结果前，容器采集器固定复用 revised V3 的项目 distribution
provenance 与网络隔离策略。它从同一份内容寻址的 installed metadata 读取精确
`Requires-Dist`，记录完整 installed name/version 观测集合与容器 marker environment，
并在 host 强制断网后从空目录直接执行 `python -m pip check`。selected extras 是绑定到
冻结 bootstrap 哈希的显式环境计划输入；collector 不解析 repository 名，也不猜 extra。

Round 7 中“任意 environment-wide `pip check` 非零直接使 V1 Fail”的旧表述，被前文已
明确的项目归因规则取代。判定先检查 active 项目闭包：已经证明的缺失、不兼容、歧义
或 malformed 闭包 requirement，即使 `pip check` 非零也应 Fail；若项目闭包本身一致，
无法归因的裸 resolver 非零仍为 Unknown。Round 12 前已用合成反例固定该判定顺序。

预注册的 Round 12 回放得到 4/5 bootstrap Pass 与 4/5 V1 Pass，没有 V1 Fail。gpkit、
Inflect、Reticulum 与 pytest-xdist 共检查 23 个 active requirement，并与完整 installed
name/version 观测核对。四次直接 resolver check 均在 Docker 断网后 exit 0，没有 timeout
或 collection error。显式 extras 依次为空、`test`、为空，以及
`psutil`/`setproctitle`/`testing`，与冻结 bootstrap 哈希绑定的输入完全一致。这为 PEP 610
和 legacy editable provenance 都提供了真实 V1 证据。

Poetry 在采集任何 V1 证据前，于 bootstrap 下载 `files.pythonhosted.org` 的 `keyring`
时失败，因此保持 V1 Unknown 和基础设施阻塞。Round 13 只能在用户确认切换网络后执行
一次完全相同的重放；不允许修改 V1 policy、bootstrap、源码、timeout 或 extras。

用户确认后，Round 13 消耗了这一次重试。原有四个 V1 Pass 被完整复现：项目 metadata
哈希、resolver 输出哈希、selected extras、active-requirement 数量与决策均和 Round 12
一致。Poetry 再次在 V1 采集前停止；这次 rapidfuzz build system 所需 `cmake` 下载不完整，
产生 `IncompleteRead`、`ProtocolError` 与 `ChunkedEncodingError`。重试预算已经耗尽。当前
真实 Dev-5 V1 coverage 保持 4/5，Poetry 仍是基础设施阻塞的 Unknown。后续应进入预注册的
服务器 artifact/cache 可靠性协议，而不是继续本地重试或修改 V1 policy。

## Round 14 V4 原生证据设计

在观察任何真实 V4 outcome 前，V4 planner 仅允许两类项目显式声明、benchmark-independent
的入口。根目录存在 `pytest.ini`、`[tool.pytest.ini_options]` table 或 `[tool:pytest]`
section 时，规划直接 argv `python -m pytest --collect-only -q -p no:cacheprovider`；否则，
存在 `pyproject.toml` 或 `setup.py` 时，规划直接 argv `python -m pip wheel --no-deps
--no-build-isolation`，且输出仅进入临时目录。planner 不使用测试路径名、repository identity、
dependency 名、tox command string 或模型输出，也绝不执行项目提供的任意 shell command。

两类 probe 都从干净的临时项目 checkout 运行，并且必须先由 host 强制断开 Docker 网络；
同时设置 `PIP_NO_INDEX=1`、关闭 bytecode 与 pip version check、不使用 shell，timeout 固定为
300 秒。配置文件内容寻址，输出流保存哈希及有界诊断尾部。pytest exit 0 表示 collection
Pass；exit 5 因未观测到适用测试而是 Unknown；其他非零与 timeout 为 Fail。wheel build
只有 exit 0 且实际产生至少一个内容寻址 wheel artifact 才 Pass。没有支持的声明或缺失
outcome 均为 Unknown。Round 14 前已用合成测试固定该三值合约；全套测试为 195 passed，
尚未使用任何真实 V4 结果调参。

预注册的 Round 14 回放完成五个 bootstrap，并得到 5/5 V4 Pass。gpkit 与 Reticulum 在
断网状态构建出内容寻址 wheel；Inflect、pytest-xdist 与 Poetry 分别收集 284、207、
1668 个测试，Poetry 另有 27 个 deselected。所有实际 probe kind、配置路径与配置哈希均
匹配预注册 planner expectation；没有 probe timeout 或非零退出，也没有执行项目任意
command。这关闭了两模式合约下的 Dev-5 V4 证据，但不代表 test body 执行、V5、V6、
Official Pass 或 held-out 泛化。

## Round 15 V6 fresh replay 等价设计

在观察 paired replay outcome 前，V6 被定义为：同一冻结 identity 下，两次独立 bootstrap
的 fresh-container 环境 snapshot 必须完全等价。identity 包含 image ID/digest、platform、
repository revision/Git tree、bootstrap 哈希与 preregistration 哈希。每次 replay 使用不同
detached checkout、container writable layer、control directory 与临时状态，不共享任何可写
volume。只有 host 断开全部 Docker 网络且容器证明没有 default route 后才开始 snapshot。

规范化 snapshot 包含 Python implementation、version、executable、prefix、base prefix，
完整 PEP 508 marker environment，所有 installed distribution 的 canonical-name/raw-version
多重集，以及所有 provenance-matched 项目 distribution 的 name、version、内容寻址
metadata、provenance kind 与 provenance hash。排序被规范化但重复项保留。container ID、
耗时、日志、runtime prefix 之外的临时路径和 verifier 输出 artifact 被排除。snapshot 声明
SHA-256，并由 pair runner 独立重算。

只有两个完整 snapshot 哈希相同且没有结构化 component delta 时 V6 才 Pass；状态差异为
V6 Fail。bootstrap/snapshot 缺失、collection error、source/network 证据无效、container
identity 被复用或冻结 replay identity 不一致均为 Unknown。单个 snapshot 永远不能宣称
V6 Pass。等价、漂移、篡改、identity 与隔离合成反例均通过；全套测试为 204 tests。
尚未观察或使用任何真实 paired V6 outcome 调参。

冻结的 Round 15 command 在 argument parsing 和 Docker 启动前失败：直接执行的 pair runner
在把 workspace root 加入 `sys.path` 前就 import `envsolve`。它没有创建 output root，启动
container 数为 0，网络请求为 0，也没有观察任何 V6 outcome。该失败作为 preflight artifact
保留。runner 现已在 import 前初始化 package path，并增加 direct-file `--help` 回归测试；
snapshot 与 comparison policy 均未改变。全套测试为 205 passed。必须生成新哈希的
Round 16 预注册，不能静默重跑 Round 15。
