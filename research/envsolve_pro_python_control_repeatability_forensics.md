# python-control Repeatability Forensics / 重复性诊断

Recorded 2026-09-04. Historical-artifact analysis; not an algorithm-effect claim.

## 中文

问题：同字节 P0 程序为何曾出现通过、缺失导入失败、再次通过？

| 历史执行 | bootstrap exit | Official issues | Pyright | 分析文件数 |
|---|---:|---:|---|---:|
| online/02-P0 | 0 | 0 | 1.1.411 | 141 |
| postepisode/02-P0 | 0 | 1 | 1.1.411 | 140 |
| postepisode/02-N | 0 | 0 | 1.1.411 | 141 |

对三份 `generalDiagnostics` 做完整 JSON 多重集合比较，失败执行恰好多一条 `control/__init__.py` 第 116 行的 `Import "._version" could not be resolved`，没有其他新增或消失的诊断；两份通过报告的诊断集合相同。
仓库的 `pyproject.toml` 指定 setuptools-scm 写入 `control/_version.py`；因此现象与生成版本文件未被分析器看到一致，但不能仅凭诊断确定它从未生成、后来被删除，还是不可解析。

已排除的简单解释：三次报告中的 Pyright 版本、所选 Python 3.10.12、virtualenv 的 pip 25.1.1 和 setuptools 80.3.1 种子版本相同。种子版本不代表安装结束后的全部依赖版本相同。
失败日志有一次对 slycot 的可恢复读取超时，但没有证据说明它导致版本文件问题，不能把两者直接连成因果关系。
原 bootstrap 本身没有 `set -e`，但现有 EnvBench `python_build.sh` 先设置 `set -e` 再 source 它，因此不能因脚本最后有 `cd` 就认定此前 pip 错误被吞掉。

证据缺口：Spark 的原三份仓库目录已不存在。现有 EnvBench `evaluation/main.py` 在容器结束后调用 `repo_downloader.clear_repo`，这与目录清理相符；历史 quiet 安装日志也没有完整依赖清单。因此历史轨迹不足以锁定根因，不补写确定结论。

已获批的 3 x 5 重复诊断现已完成，结果见 `research/envsolve_pro_post_v7_repeatability_report.md`。首次 python-control 重复取得 metric pass，并在 Pyright 输出文件存在时采到非空 `control/_version.py` 和 104 个 dist-info 目录。该文件注明由 vcs-versioning 生成。此观察证明本次可采到相关构建产物，不证明所有重复稳定，不改变算法裁决。

裁决仍为 retain：有历史同程序评分差异的事实，尚无当前核心机制的因果增益证据。原定十五次已完成，语义差异、依赖采样及基础设施删失的比较见最终短报告；未追加成功导向重试。

## English

The three historical executions used identical program bytes and reported bootstrap exit 0. Their Official issue counts were 0, 1, and 0; all used Pyright 1.1.411. Exact multiset comparison of every diagnostic shows a single added missing-import finding for `._version` in the failing run, with no other diagnostic changes. Files analyzed were 141, 140, and 141.

The repository configures setuptools-scm to generate `control/_version.py`. This supports a generated-artifact visibility explanation, but does not establish whether the file was never created, removed, or unresolvable. Python and virtualenv seed versions agree; resolved final dependency versions were not recorded. A recovered slycot read timeout is not a demonstrated cause. EnvBench enables `set -e` before sourcing the program, so its trailing `cd` alone is not evidence of swallowed pip failures.

The retained historical logs cannot resolve the cause: the three source directories are absent, consistent with the current evaluator's postexecution `clear_repo` call, and quiet installation omitted a complete dependency inventory. Do not retroactively assign a root cause.

The approved repeatability study has completed; see `research/envsolve_pro_post_v7_repeatability_report.md`. Its first python-control repetition metric-passed and yielded an in-flight sample containing the generated version file, attributed in its text to vcs-versioning, and 104 distribution directories while Pyright output existed. This validates evidence capture for that execution, not repeatability or algorithm efficacy. Retain the unproven mechanism; all fifteen executions finished without outcome-seeking retries.

## Evidence

- Historical raw root: `runs/envsolve-pro-v7-pilot8/spark-snapshot`; the three paths above each contain `json_results/results.jsonl` and `execution.json`.
- Source: `runs/envsolve-pro-v7-pilot8/mac-controller/pro-v7-pilot8-02-P0/envbench-python-python-control__python-control__dbc998dedf8e18dcdcc15acf15303f22adf9368f/generation/workspace/pyproject.toml`.
- Current evaluator inspected read-only: Spark `/home/avdpro/EnvSolve/EnvBench/evaluation/main.py` and `evaluation/scripts/python_build.sh`.
- New raw root: Spark `/home/avdpro/work/envsolve-pro-post-v7-repeatability-20260904`; first result `round-01-case-02/execution.json`, samples `round-01-case-02.samples.jsonl`.
- Approved schedule and qualifications: `research/envsolve_pro_post_v7_evidence_proposal.md`.
