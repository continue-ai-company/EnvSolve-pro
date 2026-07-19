# P6 两层 Import Obligation V1

状态：设计预注册；先于代码实现，也先于任何新真实 case 运行。

## 1. 研究问题

一个与 benchmark 解耦的 verifier，能否区分“可执行 import 闭包”和“源码静态可解析性”，
并只把有执行证据支持的失败转化为 EnvSolve loop 的约束？

该设计针对 consumed development 诊断中暴露的目标错位，但不编码任何仓库名、包名、
模块名或官方 evaluator 输出。

## 2. 契约

对于有界扫描得到的、revision-owned runtime/test/build 源码中的每个绝对 import，
verifier 记录两层相互独立的 obligation：

1. **Runtime-semantic obligation**：当当前平台和源码控制流使该 import 生效时，它必须能在
   候选环境中执行。
2. **Static-source obligation**：该 import 名必须能在候选环境搜索路径中静态发现对应的
   module、package、extension、namespace package 或 type stub。

两层是证据，不是两套 repair loop。每个源码 occurrence 最终合成为一个类型化 module finding：

- 任一必需层有确定的 `missing` 观测，则为 `active`；
- 没有 active，但至少一个必需层无法判定，则为 `unknown`；
- 其余情况为 `inactive`。

只有两层都不存在 active 和 unknown finding 时，internal verifier 才能 Pass。

## 3. 分层语义

| 源码上下文 | Runtime-semantic 层 | Static-source 层 |
|---|---|---|
| 活跃的 runtime/test/build import | 必需 | 必需 |
| 被 `ImportError` 保护的 `try` import | 可选 | 必需 |
| `except ImportError` 中的兼容 fallback | 运行时替代分支 | 必需 |
| `if TYPE_CHECKING:` 中的 import | 不活跃 | 必需 |
| 对目标平台可证明不活跃的分支 | 不活跃 | 不活跃 |
| 被冻结 inventory 契约排除的 documentation、fixture、vendored 或 generated scope | 不在范围内 | 不在范围内 |
| 语法或观测存在歧义 | unknown | 除非可独立解析，否则 unknown |

只在执行动态别名后才能 import 的名字，可以满足 runtime 层，但不一定满足 static 层。
反过来，stub-only module 可以满足 static 层，但不能满足活跃的 runtime obligation。

## 4. 静态解析

静态 resolver 不产生 import 副作用。它在候选解释器实际 `sys.path` 中搜索：

- Python module 和 package；
- PEP 420 namespace-package 目录；
- 解释器支持的 extension 和 bytecode 后缀；
- `.pyi` 文件以及 `name-stubs` package 布局；
- 由解释器声明的标准库模块。

它不得 import 目标模块、查询包索引、调用 EnvBench、运行 Pyright、读取官方输出，
也不得使用学习得到的仓库特定映射。对不支持的 archive/import-hook 布局应输出 `unknown`，
而不是 `missing`；但如果普通物理搜索已经证明名称不存在，且 runtime 只通过动态别名解析，
则 static 层可以判为 missing。

## 5. 代码实现前冻结的合成反例

| ID | 构造 | 预期判定 |
|---|---|---|
| S1 | 活跃 import 在 runtime 和 static search 中都不存在 | active；两层 |
| S2 | 活跃 import 有物理实现且可以 import | inactive |
| S3 | optional `try` import 不存在 | active；仅 static 层 |
| S4 | primary 可在 runtime 解析，但 fallback 不存在 | active；仅 static 层 |
| S5 | import 只能通过运行时创建的 alias 得到 | active；仅 static 层 |
| S6 | `TYPE_CHECKING` import 有 `.pyi` stub | inactive |
| S7 | `TYPE_CHECKING` import 不存在 | active；仅 static 层 |
| S8 | import 位于可证明不活跃的平台分支 | inactive |
| S9 | 活跃 import 发生非 missing 执行错误，但物理实现存在 | unknown；runtime 层 |
| S10 | resolver 不支持的布局，且没有确定缺失证据 | unknown |

## 6. 准入标准

只有同时满足以下条件，实现才可准入：

1. S1-S10 都由不使用真实 benchmark case 的聚焦测试覆盖。
2. 既有 import 语义测试、EnvSolve 全量测试、harness 测试、语法检查和冻结的 Docker
   integration test 全部通过。
3. Finding 保留逐层 provenance，且不产生任何 benchmark-owned 在线反馈。
4. 不新增仓库特定 module/distribution 映射。
5. 在选择任何 unseen development qualification batch 前，用新 freeze manifest 哈希实现、
   测试和本协议。

## 7. Freeze 后实验

实现并冻结后，预注册一批新的 unseen development case。在相同模型、预算、candidate DSL、
fresh-container policy 和 terminal-only 官方评测条件下比较 V2 与两层 verifier。报告 internal Pass
校准、官方成功率、按层统计的 active finding、Unknown 比例、候选数、wall time、tokens 和成本。
Consumed case 只能用于诊断，不能升级为 confirmatory evidence。
