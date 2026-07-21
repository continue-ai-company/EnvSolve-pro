# EnvSolve-pro P0 高价值 Case 记录 v1

## 范围

本文档记录能够暴露通用算法失败模式的开发观察。它不是效果榜，也不能把已选择的 P0 case 变成定向优化
目标。任何修复都必须先表述为通用机制，在合成 fixture 或已消费 case 上测试并冻结，然后才能在 untouched
case 上评估。

## Case P0-001：`wpi-lnl/lnldb@6384c05`

**状态：** 四种原生方法均已终止。只有 Codex 进入官方 evaluator，因此本 case 可以用于错误分析，但不能
形成完整效果对比。

### 为什么这个 Case 有价值

`lnldb` 是一个较老的 Django 应用，声明 Python 3.7.7，使用嵌套 requirements、受限包版本和 editable
Git 依赖。它能把四种容易混为一谈的能力拆开：

1. 读取仓库证据；
2. 将证据连同来源保留为约束；
3. 提出满足约束的操作；
4. 判断语义成功，而不只是 shell 命令成功。

### 仓库证据

- `runtime.txt`：`python-3.7.7`
- `requirements.txt` 递归包含 `requirements_base.txt`，并固定生产环境依赖，例如
  `boto3==1.14.47` 和 `psycopg2==2.7.1`。
- `requirements_base.txt` 要求 `Django>=2.2.13,<3.2`，并包含多个固定 revision 或 branch 的
  editable Git 依赖。

### 原生方法观察

| 方法 | 已观察终局或当前状态 | 诊断价值 |
|---|---|---|
| Repo2Run reproduced | 16 次成功模型响应后，原生 generation 失败，未进入官方 evaluator。构建出的环境仍保留现代 Django，上游 agent 随后因索引空 agent 结果而崩溃。 | 长命令 loop 仍可能遗漏决定性版本约束；baseline 自身鲁棒性必须与环境正确性分开。 |
| Codex CLI | 构建 Python 3.8 环境，安装 `requirements_debug.txt`，并运行 Django check/test。官方评估完成但失败，共 1,629 个 error；两个 missing-import 是 `django.conf.settings` 和 `django.core.urlresolvers`。 | 强自由 Agent 能从网络超时中自适应并选择合理的旧 runtime，但本地检查目标与官方目标没有对齐。 |
| 冻结 EnvSolve v1 | 五候选耗尽后原生失败，未进入官方 evaluator；共 5 次成功模型响应、4 个执行环境、68,063 total token、2,316 秒。 | 该轨迹直接检验结构化状态是在帮助强模型，还是在限制强模型。 |
| EnvBench raw ReAct | 达到原生 30 次迭代上限后仍未完成；最终 ledger 记录 31 次响应、806,340 token、1,447 秒。随后 Replay IR 拒绝三种成功 shell 形式，未进入官方 evaluator。 | 自由推理恢复了关键证据和多类失败，但上下文增长、迭代消耗与事后轨迹解析共同遮蔽了官方终局。 |

### 冻结 EnvSolve v1 候选轨迹

| 候选 | 观察与操作 | 结果 | 通用失败模式 |
|---|---|---|---|
| 1 | 使用默认 Python，安装约 70 个无版本包名。 | `psycopg2` 构建失败，缺少 `pg_config`。 | 第一轮操作没有落实仓库约束。 |
| 2 | 将 `psycopg2` 替换为 `psycopg2-binary`，其余依赖仍取最新版。 | 命令退出码为 0，但安装了违反仓库边界的 Django 6.0.7。 | shell 成功被当成有效进展，环境仍然语义不一致。 |
| 3 | 恢复大量精确版本，包括 Django 2.2.28。 | 聚合解析器报告找不到 `boto3==1.14.47`；候选 5 随后证明单独安装可以成功。 | loop 把 resolver 症状当成单包事实，没有保留复合冲突上下文。 |
| 4 | 正确判断现代 Python 是根因，并提出通过 `pyenv` 安装 Python 3.8.13。 | 执行前被拒绝，退出码 252；操作守卫不认识用于获取 `pyenv` 的 `git clone`。 | 封闭的文本动作词表拦截了方向正确的强模型修复。 |
| 5 | 把失败的聚合安装拆成多条命令，同时继续使用默认 runtime。 | 单独安装 `boto3==1.14.47` 成功；后续安装又把 Django 恢复为 6.0.7，并在 `natural-duration==0.1.0` 失败，而仓库实际使用 Git 来源声明该依赖。 | 拆分能隔离 resolver 冲突，但丢失 VCS provenance 且缺少全环境后置条件，仍无法收敛。 |

### Raw ReAct 轨迹

raw Agent 在安装前读取了 `runtime.txt`、全部递归 requirements、README 和 Travis 配置。随后它：

1. 遇到 Conda HTTP 失败后切换 provider；
2. 通过 `pyenv` 安装并激活仓库声明的 Python 3.7.7；
3. 遇到 pip read timeout 后提高超时并恢复；
4. 固定 `python-bidi`、补充 `libpq-dev`、隔离 `docutils`/`botocore` 冲突，并替换不兼容的
   `psycopg2` build；
5. 推进到 Django 应用初始化，随后访问 Microsoft OpenID 配置时发生 SSL 连接错误。

到达迭代边界时，模型明确表示还需要更多步骤。冻结 Replay IR 随后拒绝了只读 `pyenv` 管道、临时
constraints 文件创建和 `pip uninstall`。因此该 episode 记为“原生轨迹未完成 + wrapper 导致官方结果
Unknown”，不进行选择性重跑。

### 三层诊断

**观测层：发生了什么？**

- 高价值仓库证据包括 runtime 声明、递归 requirements、版本范围、editable/VCS 来源和 evaluator
  finding。
- 数百条包存在与 import 事实的价值低于少量真正决定兼容性的事实。
- 网络事件必须作为独立观察。用户报告本批次期间热点曾中断，但当前 EnvSolve episode 没有模型请求错误，
  下载也持续推进，因此不符合选择性重启条件。

**约束层：现在缺什么、冲突在哪里？**

- 约束必须保留完整 requirement 语义和 provenance，不能只保留规范化包名。
- 失败应保留 runtime、provider 与 requirements 之间的上下文化冲突或 unsatisfied core，不能把字面错误
  信息直接当事实，也不能只把某条命令字符串拉黑。
- 约束需要压缩和分级。数千条包/import 事实不应掩盖 runtime 与框架的兼容边界。

**操作层：怎样改变环境来解除冲突？**

- 操作空间必须有足够表达力，让强 Agent 能获取固定目录未预见的 runtime 或 provider。
- 安全边界应建立在 typed intent、provenance、前置条件和可验证效果上，而不是穷举 shell 文本白名单。
- 可重放操作应在工具执行时记录为 typed event；事后 shell parser 不应抹掉一条已有完整执行信息的轨迹。
- 每个候选使用新环境可以保留因果可审计性；同时可以缓存确定性基础层，避免重复下载系统包，而不共享候选
  的可变状态。

### 可检验假设

- **H1：证据保真。** 保留 runtime、递归 requirement 和 VCS provenance，能减少不兼容的第一候选，
  同时不压缩有效动作空间。
- **H2：语义 no-good。** 上下文化冲突记录比精确命令黑名单更能减少等价失败重复。
- **H3：开放但可验证的操作。** 相比封闭动作词表，typed acquisition fallback 能提高成功率，同时不增加
  不安全或不可审计执行。
- **H4：约束优先级。** 紧凑的 compatibility frontier 比所有低层事实等权暴露更容易产生正确候选。
- **H5：效果保真的轨迹。** 相比事后 shell 蒸馏，在执行时捕获 typed action 能减少 wrapper-induced
  Unknown。

### 防过拟合 Gate

任何修复都不能特判 `lnldb`、Django、`boto3`、`psycopg2` 或 `pyenv`。修复必须作用于通用的
runtime、requirement、provider、conflict 或 acquisition 类型；通过不包含本仓库的单元 fixture；并在打开
下一个 untouched development case 前冻结。

### 证据锚点

- Case 选择与顺序：`experiments/validations/pro_p0_external_baselines_v1_schedule.json`
- 冻结 EnvSolve run ID：`pro-p0-v1-c01-envsolve-v1-frozen`
- Codex run ID：`pro-p0-v1-c01-codex-cli-native`
- Repo2Run run ID：`pro-p0-v1-c01-repo2run-reproduced`
- Raw ReAct run ID：`pro-p0-v1-c01-envbench-raw-react`

## Case P0-002：`columnflow/columnflow@ad04770`

**状态：** Repo2Run reproduced、冻结 EnvSolve v1 与 raw ReAct 均已原生 generation 失败。Codex CLI
因冻结二进制被 App 自动更新替换而没有启动，该位置记为 Unknown。当前不能得出跨方法效果结论。

### 为什么这条部分轨迹有价值

该仓库把核心安装与可选执行环境分开。`setup.py` 只安装 `sandboxes/cf.txt`，而本 case 的测试还需要
`sandboxes/columnar.txt` 中声明的包。项目会把缺失的可选模块表示为可调用的 mock 对象，因此 import
表面上可以成功，直到测试真正调用模块时才暴露环境在语义上不完整。

### Repo2Run 观察

Repo2Run 完成 20 次模型响应，没有 provider 或网络错误，共使用 286,631 total token 和 552 秒。它进入
Python 3.10 容器，以 editable 方式安装项目，随后补装 `law` 和 `order`，并反复设置项目环境变量。测试
收集仍失败，因为 `awkward` 还是 mock module。仓库在 agent 已读取的 `sandboxes/columnar.txt` 中明确声明了
`awkward==2.4.6`，但 agent 没有执行该安装。

上游进程随后索引一个不存在的最终 agent 响应并触发 `TypeError`，因此 generation 没有产生可重放候选，
也没有进入官方 evaluator。这是有效的原生 baseline 失败，不属于基础设施重试：模型响应与 118 条 inner
command 记录都存在。

### 冻结 EnvSolve v1 观察

冻结 EnvSolve 在五个全新候选上耗尽预算，没有进入官方 evaluator。它完成 5 次模型响应，没有请求错误，
使用 44,916 total token 和 543 秒，并同时触及 candidate、command 与 environment 上限。

repository profiler 把 `setup.py` 和截断后的 README 交给了模型，但结构化 declaration observer 没有接纳
任何仓库证据：0 个文件、0 条 runtime requirement、0 source byte。因此初始约束状态只有 base Python
3.13.2 事实。随后每个新环境只暴露一层 compatibility frontier：

| 候选 | 新操作或推断 | 终局观察 |
|---|---|---|
| 1 | 用 base Python 3.13.2 创建 venv，并 editable 安装项目。 | 被 `python_requires >=3.7, <=3.11` 拒绝。 |
| 2 | 通过 `pyenv` 获取 Python 3.11.11。 | PEP 440 的 `<=3.11` 不包含 `3.11.11`，再次被拒绝。 |
| 3 | 正确切换到 Python 3.10.11。 | 项目安装和 `pip check` 通过，但内部 verifier 缺少 `pytest`。 |
| 4 | 增加 `pytest`。 | test collection 暴露安装时未包含的 `law` 模块。 |
| 5 | 增加 `law` 和 `pytest`。 | collection 推进到 setup 变量未解析；`law.cfg` 把 `$CF_WLCG_USE_CACHE` 当成非布尔字面量。 |

这条轨迹持续取得真实进展，但每个新候选都会重复 runtime 获取，并且只能解除刚刚显露的下一项 obligation。
这并不说明 fresh isolation 是错的，而是说明：在消耗下一个环境前，上一环境学到的观察必须被归纳为足够
完整的 compatibility frontier。

### Codex CLI 基础设施偏差

预注册二进制是 `codex-cli 0.145.0-alpha.18`，SHA-256 为
`f0b214b476e04175bee104fe441caea874baeef3efc3828bfb79e972266156a9`。该位置开始前，桌面 App 自动把它
替换为 `0.145.0-alpha.27`。OpenAI 官方 Release 和最接近的官方历史桌面包都能提供
`0.145.0-alpha.18`，但二进制哈希均不同。版本号相同不等于字节级边界相同，因此没有悄悄替换，也没有执行
任何 Codex 模型调用或容器命令。该计划位置记为 Unknown，不在改变外部边界后选择性重跑。

### Raw ReAct 观察

Raw ReAct 达到原生 30 轮上限后停止。在线 ledger 记录 31 次响应、719,190 total token、270 秒，且没有
provider 错误。它检查了 `setup.py`、`setup.sh`、所有具名 sandbox requirement 文件和 submodule 声明；选择
Python 3.10.13；安装项目与开发依赖；初始化并安装仓库固定的 `law`、`order` 子模块。最后一次语义检查到达
与冻结 EnvSolve 相同的 `$CF_WLCG_USE_CACHE` 配置 frontier，随后以“还需要更多步骤”结束。

Replay IR v9 保留了 11 个 typed action，但把已成功执行的
`git submodule update --init --recursive` 判为 unknown，因此官方 evaluator 没有运行。这条 episode 有两个
应分开记录的终局事实：原生 Agent 没有在迭代设置内完成；wrapper 又无法表示 Agent 已成功执行的、由仓库声明
的 source acquisition。

### 三层诊断

**观测层：** 包声明带条件并分散在具名环境文件中。若项目会用 mock 替代缺失模块，import 成功只是弱证据，
第一次语义调用的失败更有信息量。结构化 observer 还遗漏了 repository profile 已经可见的声明，导致 runtime
与 setup obligation 只能通过失败执行被逐项重新发现。

**约束层：** solver 需要把当前测试面与能满足它的环境专属声明连接起来。平铺安装全部可选环境会过度安装，
只使用 `install_requires` 又会遗漏必要约束。新的执行反馈应更新一个紧凑 frontier，区分 runtime 兼容性、
verifier 前置依赖、项目 extra 与配置 obligation；否则固定 candidate 数就等价于固定的串行发现次数。

**操作层：** mock-module 失败后，有效操作不应是无边界猜包，而应根据 provenance 激活或安装能够提供该模块的
最小已声明可选环境。fresh container 应重放修订后的完整计划；确定性的 runtime 获取可以缓存，但不能共享
候选的可变状态。仓库固定的 submodule 初始化属于 typed source-acquisition operation，不是任意 shell escape。

### 候选通用假设

- **H6：测试条件化的声明可达性。** 把观测到的 test/import obligation 与仓库声明的可选环境关联，应能同时
  减少可选依赖缺失和无差别安装。任何 EnvSolve 改动前，必须先在与该仓库无关的 fixture 上检验该假设，
  再用 untouched case 评估。
- **H7：观测状态完整性。** 接纳 profile 文件中已存在的兼容声明，应能减少串行重发现，同时不引入仓库特判。
- **H8：frontier 保真的重规划。** 相比只追加最新错误，用每次 verifier 失败更新同一个 typed compatibility
  frontier，应能让每个 fresh candidate 一次解决更多 obligation。
- **H9：provenance 支持的来源扩展。** 把仓库声明的 submodule 获取表示为 typed operation，应能减少
  wrapper-induced Unknown，同时不开放无限制的 source mutation。

### 防过拟合 Gate

任何修复都不能特判 `columnflow`、`law`、`order`、`awkward`、WLCG 或任何 `CF_*` 变量。观测与操作改动
必须作用于通用的 declaration、optional-environment、submodule 或 configuration 类型；通过与仓库无关的
fixture；并在打开下一个 untouched case 前冻结。

### 证据锚点

- Repo2Run run ID：`pro-p0-v1-c02-repo2run-reproduced-r2`
- 原生用量：20 次响应、286,631 total token、552 秒
- 已保存原始轨迹：`generation/repo2run_raw/inner_commands.json`
- 原始轨迹 SHA-256：`fc4325962623cac1e3a567394ffba462857f710d9e6a1a96e7956a6807c26ae8`
- 冻结 EnvSolve run ID：`pro-p0-v1-c02-envsolve-v1-frozen`
- 冻结 EnvSolve 用量：5 次响应、44,916 total token、543 秒
- Codex 计划 run ID：`pro-p0-v1-c02-codex-cli-native`（未启动；Unknown）
- Raw ReAct run ID：`pro-p0-v1-c02-envbench-raw-react`
- Raw ReAct 用量：31 次 ledger 响应、719,190 total token、270 秒
- Raw ReAct distillation：保留 11 个 action，1 条成功命令不受支持
- Raw ReAct 原生轨迹 SHA-256：
  `cbf6771459347acd61c09bce056c56c8940cb679ef2c956c8b7435ea029dedd8`
- runtime 偏差记录：
  `experiments/validations/pro_p0_external_baselines_v1_runtime_deviations.json`

## Case P0-003：`marimo-team/marimo@537b230`

**状态：** 所有可运行的计划方法均已终止。Repo2Run 的原生 verifier 通过，但 replay wrapper 拒绝轨迹；
raw ReAct 原生未完成，随后又被不区分 artifact 的完整性审计拒绝；冻结 EnvSolve 沿错误的 optional
dependency 分支搜索，5 个候选耗尽。计划中的 Codex 因无法恢复精确预注册二进制而记为 Unknown。没有运行
官方 evaluator。

### 为什么这条部分轨迹有价值

这个 case 把包安装与简单的文件系统后置条件分开。项目声明的 test extra 能提供 Python 依赖，但 test
collection 还要求一个生成式前端 asset 目录存在。因此，即使 package graph 一致，缺少必要的空目录仍可能让
测试在执行前失败。

### Repo2Run 观察

Repo2Run 完成 8 次模型响应，使用 77,503 total token 和 377 秒，没有请求错误。它读取
`pyproject.toml`，安装仓库声明的 `.[testcore]` extra，观察到 collection 因
`marimo/_static/assets` 不存在而失败，创建该目录后重新运行原生 `runtest`。最终原生 verifier 返回 0，并
收集 1,085 个测试。

冻结 Repo2Run replay 层只保留了包安装动作，拒绝成功执行的
`mkdir -p /repo/marimo/_static/assets` 操作。因此 generation 被标记为不可重放，官方 EnvBench evaluator
没有运行。本结果应记为“Repo2Run 自身 verifier 下原生成功 + wrapper 导致官方结果 Unknown”，不能写成
EnvBench success。

### Raw ReAct 观察

Raw ReAct 完成 20 次模型响应，使用 344,440 total token 和 561 秒，没有 provider 错误。它沿着仓库的
完整 source-build 路径推进：安装 pnpm、执行 `make fe`、按文档提高 Node heap 后重新构建 frontend，随后
执行 `make py`。Python 安装在 base Python 3.13 下遇到 `pyarrow` 构建问题。Agent 选择 Python 3.12 并
修正 `PATH`，但还没有重新安装或运行测试，就以空的 terminal response 结束。因此原生轨迹未完成。

wrapper 随后报告 7,865 个 repository-integrity violation，但 tracked change 与 changed source file 都是
0：其中 7,854 个 symlink、10 个 Python 文件和 1 个 requirements 文件全部位于 package-manager 生成的
`node_modules` 树中。审计没有考虑 generated-root provenance，把依赖安装产物归类为 source injection，
因此又叠加了一次独立的 wrapper failure。该 episode 不重跑。

### 冻结 EnvSolve 观察

第一次冻结 EnvSolve episode 在候选 3 遭遇已分类的 TLS dependency-acquisition failure 后停止。随后严格按
预注册 infrastructure-retry 规则重跑一次，冻结代码、模型、协议和 case 均未变化。有效重试完成 5 次模型
响应和 5 个 fresh-container candidate，使用 56,916 total token 与 478 秒，没有模型请求错误。

候选 1 安装项目，暴露 verifier 缺少 `pytest`。候选 2 增补 `pytest`，collection 到达 893 个测试后，
`starlette.testclient` 又要求 HTTP 测试依赖。候选 3 选择较宽的 `testoptional` extra，间接在 base Python
3.13 下拉入旧版 `pyarrow`，并在 wheel preparation 阶段失败。候选 4、5 继续沿该分支增加构建工具并固定
`pyarrow==15.0.2`，仍无法安装不兼容的 source build。episode 最终耗尽 5 个候选。

这是算法失败，不是基础设施或 evaluator 结果。初始仓库观察从 `pyproject.toml` 接纳了 14 个 runtime
requirement，却没有暴露 optional dependency group 的语义。因此 solver 虽有足够操作自由，却缺少结构化
证据去优先选择 Repo2Run 通过阅读声明找到的较窄 `testcore` group。重复的 `pyarrow` 构建失败也一直停留在
package-install failure，没有提升为能够重定向搜索的 runtime compatibility conflict。

### 初步三层诊断

**观测层：** 即使不需要生成任何文件内容，缺失路径本身也可以是部署观察。test collection 提供了比 package
graph 更强的证据。build artifact、dependency tree 与 source edit 也必须被观察为不同 path class，不能
只根据文件扩展名推断。optional dependency group 及其与 verifier 的相关性也是 repository evidence；只
展开 base requirement 会丢失决定性的选择边界。

**约束层：** 环境状态还包含 `directory_exists(project-relative-path)` 这类 typed filesystem
postcondition，不只有 runtime、package、import 与环境变量。在声明 runtime 下重复发生的 native-build
failure，还应能从局部命令错误提升为 runtime-package compatibility conflict。

**操作层：** 创建 project-relative 空目录是边界明确且效果可验证的操作。把所有文件系统变化都当成无法表示的
shell escape，会不必要地抹掉强 Agent 已成功完成的轨迹。反过来，宽泛的 repository integrity scan 必须
理解 operation 产生的 artifact root，否则标准 package-manager 语义会变成虚假的 tampering evidence。

### 候选通用假设

- **H10：typed filesystem postcondition。** 在明确 path scope 并验证效果的条件下表示 project-relative
  目录创建，应能减少 wrapper-induced Unknown，同时不允许任意 source edit。
- **H11：provenance-scoped integrity。** 根据产生 untracked path 的 typed operation 与 generated root
  分类，应能在保护 tracked source 的同时，避免标准 package-manager layout 触发误报。
- **H12：verifier-conditioned optional dependencies。** 把具名 optional dependency group 保留为结构化
  repository evidence，再根据 active verifier 缺失的 import 排序，应能在不硬编码 package 或 repo 名的
  前提下避免选择过宽 extra。
- **H13：compatibility-conflict promotion。** 按 package、runtime 与 failure phase 聚合重复 build failure，
  应能让约束层关闭无效安装分支，改为提出兼容 runtime 或更窄 dependency set。

### 防过拟合 Gate

任何修复都不能特判 `marimo`、frontend asset、`_static` 或本次路径，也不能硬编码 `testcore`、
`testoptional`、`pyarrow` 或 Python 版本。操作变化必须使用通用 filesystem intent，拒绝路径穿越与
protected path，验证执行效果，通过与仓库无关的 fixture，并在打开 untouched case 前冻结。dependency
group 与 compatibility 变化必须来自声明和执行证据，并在使用不同名称的 synthetic repo 上验证。

### 证据锚点

- Repo2Run run ID：`pro-p0-v1-c03-repo2run-reproduced`
- 原生用量：8 次响应、77,503 total token、377 秒
- 原生 verifier：返回码 0，收集 1,085 个测试
- 已保存原生命令轨迹：`generation/repo2run_raw/inner_commands.json`
- 原生命令轨迹 SHA-256：
  `a825ca90f8b4a38b24a6ccc762e50afc71ee3ede47dd64c63960a7a6b9ee6d71`
- Raw ReAct run ID：`pro-p0-v1-c03-envbench-raw-react`
- Raw ReAct 用量：20 次响应、344,440 total token、561 秒
- Raw ReAct 完整性审计：0 tracked change、7,865 个 generated-path violation
- Raw ReAct 原生轨迹 SHA-256：
  `78af4405d3115f97c99cefba57cb93821e7d93230e75ec8131a7d6e48047f7f7`
- 冻结 EnvSolve 首次 run ID：`pro-p0-v1-c03-envsolve-v1-frozen`
- 冻结 EnvSolve infrastructure retry run ID：
  `pro-p0-v1-c03-envsolve-v1-frozen-network-retry3`
- 冻结 EnvSolve 重试用量：5 次响应/候选、56,916 total token、478 秒、0 个 request error
- 冻结 EnvSolve 结果：candidate budget exhausted；5 次 verifier failure
- 计划 Codex 结果：Unknown，精确预注册 executable 不可获得
