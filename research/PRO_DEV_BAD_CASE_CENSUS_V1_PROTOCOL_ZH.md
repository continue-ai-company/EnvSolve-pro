# EnvSolve-Pro Dev Bad-Case Census v1 实验协议

日期：2026-08-09

## 目的

设计下一版 EnvSolve-Pro 算法前，先完整测量冻结的强 Agent 对照究竟失败在哪里。必须先得到
完整 Dev bad-case 清单，并只根据 A 的轨迹完成失败分类；在此之前不得运行 B/C treatment，
也不得选择核心实验 batch。

这是开发阶段的错误分析实验，只用于发现主要矛盾和设计算法，不能支持 held-out 或榜单结论。

## 数据边界

EnvBench 论文在完整的 329 个 Python `python_baseline_failure` case 上报告主实验，并没有采用
下面的 EnvSolve-Pro 开发划分。我们冻结的上游数据版本还包含一个 100-case 的
`python_baseline_failure_test` 子集；EnvSolve-Pro 将它保护起来，但 EnvBench 论文的主结果仍
是在全部 329 个 case 上计算的。

为了防止研究过程过拟合，EnvSolve-Pro 把 329 个 Python case 额外划分为：

- Dev census：209 个，即冻结的 Dev-5 与 Train-Rest-204 的并集；
- Canary：20 个，在核心算法设计期间保持未触碰；
- Protected test：上游 100-case test 子集，只在确认阶段使用。

三者没有交集。这是我们的科研划分，不是 Repo2Run 的划分，也不是 EnvBench 论文主实验的
划分。

## 冻结对照

A 条件是 `codex-cli-qualified-boundary-v5`：`gpt-5.5`、high reasoning effort、一个连续 Codex
session、一个持久构建环境，Agent 看不到 clean replay。session 结束后的 qualification 和
Official evaluator 反馈都不返回 Agent。

已有 4 个结果与该身份完全一致且 artifact 有效，直接各复用一次；剩余 205 个 case 只运行
A，并按确定性规则分配到两条互不重叠的 Mac lane。模型、边界、公开目标、evaluator 或结果
语义发生变化，都必须停止并另建 census 版本。

本 census 在官方多架构镜像的 `linux/arm64` 路径上执行，测量的是冻结 Agent 在该部署平台上的
表现，而不是与架构无关的固有难度。不能把它直接与未报告架构的论文数字比较；SOTA 主张必须让全部
对比方法运行在同一种架构上。

## 结果与失败分类

每个 case 只能得到一个终局结果：Official Pass、Official Fail、Agent Noncompletion、
Qualification Fail 或 Infrastructure Unknown。Infrastructure Unknown 被 censor，可进行一次
语义完全相同的重试，不计作算法失败；有效的 Agent Noncompletion 是 Pass@1 失败，不能被
后续诊断运行替换。

bad case 只能根据 A 的轨迹证据归入 Observation、Constraint、Operation、Cross-layer 或
Unresolved。除 Unresolved 外，每个标签都必须给出证据锚点。禁止用 B/C 结果、历史 treatment
是否容易修复、预期改进难度、Canary 内容或 protected-test 内容参与分类和选样。

census 过程中不能扩充 taxonomy。新机制统一记为 Unresolved；本轮结束后，它可以推动另行
冻结的 taxonomy v2。

全部 bad case 都做主标注。再按确定性规则抽取
`min(N, max(30, ceil(0.25N)))` 个 case，由第二位标注者只使用相同的 A 证据独立复标；复标时
看不到主标签、总体类别频次和任何 B/C 数据。原始分歧必须保留，并在 adjudication 前报告一致性。
独立的可靠性预注册冻结抽样、blind 和统计规则。

## 固定核心 Batch

只有完整发布 209 个结果和全部 bad-case 分类后，才能选择最多 12 个核心 case。按“终局结果
+ 主失败层 + 主 subtype”分层；各层按 census 频次降序、再按标识符字典序排列；层内按冻结
salt 的 SHA256 排序；最后在各层之间 round-robin 抽取。

未选中的全部 bad case 自动成为冻结 validation pool，不得参与第一版核心算法设计。核心
batch 和 validation pool 的身份都冻结以后，才允许启动 B/C 和修改算法。

## 主要产物

- 预注册：`experiments/validations/pro_dev_bad_case_census_v1_preregistration.json`
- 标注可靠性：`experiments/validations/pro_dev_bad_case_census_v1_annotation_reliability_preregistration.json`
- 平台解释：`experiments/validations/pro_dev_bad_case_census_v1_platform_interpretation_amendment.json`
- 全部 Dev：`experiments/cases/dev_pro_bad_case_census_v1_209.jsonl`
- 失败分类：`experiments/protocols/envsolve_pro_dev_bad_case_taxonomy_v1.json`
- 待运行 case：`experiments/cases/dev_pro_bad_case_census_v1_pending205.jsonl`
- 两条 lane：`experiments/schedules/pro_dev_bad_case_census_v1_mac_lane1.json` 与
  `experiments/schedules/pro_dev_bad_case_census_v1_mac_lane2.json`
