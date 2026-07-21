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
