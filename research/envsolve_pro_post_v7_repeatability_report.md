# Repeatability Result / 重复性诊断结果

2026-09-04. All 15 scheduled executions completed; no model calls or extra retries.

## 中文

| 原程序 | 有效评分且通过 | 有明确超时证据 | 原因未决的 bootstrap 失败 |
|---|---:|---:|---:|
| python-control | 3 | 2 | 0 |
| qtconsole | 3 | 2 | 0 |
| yapf | 3 | 1 | 1 |
| 总计 | 9 | 5 | 1 |

1. **主要矛盾**：同程序的终局执行确有波动，但本批主要发生在有效评分之前。尚未找到新的强 Agent 语义修复机会。
2. **支持证据**：原脚本、镜像和执行器不变，仍出现不同终局；只看构建阶段进展不足以保证一次部署交付成功。
3. **反证与替代解释**：九次取得报告的执行全部通过，各项目三份完整诊断集合相同。五次失败含明确超时证据；yapf 一次 setuptools 的 versions:none 原因未决。历史 `._version` 问题没有复现，根因也没有因此被解释。
4. **建议裁决**：retain，保持未证实，不晋升。每个程序只有三次有效评分，不能说“五次稳定”；更不能把外部下载失败及重试解释成 replay 算法增益。Live frontier 不复活。
5. **下一实验**：审议 209 个明确 Dev case 中随机 24 个的强 Agent 普查，寻找真实终局失败。配置与工具能力见原提案；必须保留自由 Agent 自行用新容器验证程序的能力，统一基础设施处理。尚未抽样或启动，不触碰 protected 数据。

## English

The fixed 3 x 5 diagnostic completed with **9 metric passes, 5 executions containing explicit timeout evidence, and 1 unattributed bootstrap failure**. Each original program passed three times. Every scored completion passed; diagnostic multisets agreed exactly within each program.

The operational support is that unchanged programs can produce different terminal outcomes. The stronger competing explanation here is external delivery failure before scoring, not a newly verified semantic repair opportunity. The historical python-control generated-version failure was not reproduced or explained. Sampled distribution-directory names agreed within successful repetitions, but are not proof of identical complete environments.

**Recommendation: retain as unproven; no promotion.** These are selected diagnostic executions, not a representative benchmark estimate or a feedback-treatment experiment. Three evaluable agreements per program do not establish stability. Do not turn download retries into an algorithm-effect claim.

Next, review the proposed random 24-case census from the explicit 209-case development universe with voluntary fresh-container verification available to the free Agent. Keep common infrastructure handling and report unresolved outcomes. No new census or protected evaluation has started.

## Evidence

- Structured result: `experiments/validations/envsolve_pro_post_v7_repeatability_result.json`.
- Local raw evidence: `runs/envsolve-pro-post-v7-repeatability-20260904/`.
- Spark raw evidence: `/home/avdpro/work/envsolve-pro-post-v7-repeatability-20260904/`.
- Historical forensic note: `research/envsolve_pro_python_control_repeatability_forensics.md`.
- Configuration and population proposal: `research/envsolve_pro_post_v7_evidence_proposal.md`.

Verification covered all fifteen script texts, scheduled positions, postepisode-only flags, serial execution intervals, and raw reports. Four ordinary runner tests passed. This report adds no algorithm rule, safety gate, or paper-draft text.
