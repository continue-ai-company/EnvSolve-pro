# EnvSolve-Pro Free-Agent Census Position 9 Protocol Note

## 中文

### 结论

位置 9 不是 `boundary-censored`，也没有在原 run 结束后另选成功样本补评。原定 run `free-agent-census24-v1-09-A` 自身完成了 Agent 生成、独立 qualification 和 Spark EnvBench Official，最终为 **Official Pass@1**。

### 三类状态

1. **构建目录审计**：Agent 在构建 checkout 中创建了 `neurogym/utils/test_plotting.py`。旧的 clean-tree 审计把它记为 `untracked_import_artifact`，所以底层 `generation/result.json` 保留了一次失败状态。它描述的是构建目录，不是最终 Official 结果。
2. **提交后 qualification**：同一个已提交程序在新的 Spark checkout 中独立重放，bootstrap exit 0、missing imports 为 0。事后 effect audit 将该文件标为 `postepisode-executable-source-review`，没有向 Agent 返回反馈。
3. **EnvBench Official**：同一序列化程序随后由 Spark EnvBench 执行，exit 0、`issues_count=0`，因此主结果是 Official Pass@1。236 个其他 Pyright error 和 1 个 warning 均为非计分诊断。

### 程序同一性

`final-output.json` 中的 `bootstrap_script`、`scripts/generated.sh`、`scripts/bootstrap.sh` 和 qualification 保存的程序内容一致。去除末尾空白后的规范 SHA-256 均为 `1bea685b37882463a683652f544e9064c9387b885d3d8b8d9d0caa26c42e07a9`；Official 清单记录的序列化文件 SHA-256 为 `03f281bc29b0217cbe9252dc374425caad13665f4f1a4b4906dccb5baff276b8`。两者只是规范化口径不同，不是两个程序。

### 规则边界

本 census 按负责人裁决，只以 EnvBench Official Pass/Fail 计算主成功率；源码兼容修改只作标签，不推翻 Official。检查的 EnvBench 文档（revision `bf972d4d0404e6bfcc8241d9a820202cea76dade`）没有明确说明 bootstrap 是否可以创建源码兼容文件。因此，这里只声称“官方 evaluator 通过”，不把它进一步表述为已独立确认符合所有榜单提交规则。项目自己的旧 integrity rule 仍保留在原始证据中，但不作为新的私有计分门槛。

## English

### Decision

Position 9 is not boundary-censored, and no success-selected supplemental evaluation was launched after the original run. The scheduled run `free-agent-census24-v1-09-A` itself completed Agent generation, independent qualification, and Spark EnvBench Official. Its primary outcome is **Official Pass@1**.

### Three states

1. **Construction-workspace audit**: the Agent created `neurogym/utils/test_plotting.py`. The legacy clean-tree audit recorded it as an `untracked_import_artifact`, so the lower-level `generation/result.json` preserves a failed state. That record concerns construction residue, not the final Official outcome.
2. **Post-submission qualification**: the same submitted program was independently replayed in a fresh Spark checkout. Bootstrap exited 0 with zero missing imports. The postepisode effect audit tagged the file as `postepisode-executable-source-review`; no feedback was returned to the Agent.
3. **EnvBench Official**: Spark EnvBench then executed the same serialized program. It exited 0 with `issues_count=0`, yielding Official Pass@1. The other 236 Pyright errors and one warning are non-scoring diagnostics.

### Program identity

The `bootstrap_script` in `final-output.json`, `scripts/generated.sh`, `scripts/bootstrap.sh`, and the qualification program have identical content. Their canonical SHA-256 after trailing-whitespace normalization is `1bea685b37882463a683652f544e9064c9387b885d3d8b8d9d0caa26c42e07a9`; the serialized file consumed by Official has SHA-256 `03f281bc29b0217cbe9252dc374425caad13665f4f1a4b4906dccb5baff276b8`. These are two hashing conventions for one program, not two candidate programs.

### Rule boundary

Under the supervisor's census adjudication, EnvBench Official Pass/Fail is the sole primary success outcome; source-compatibility edits remain tags and do not override Official. The checked EnvBench documentation at revision `bf972d4d0404e6bfcc8241d9a820202cea76dade` does not explicitly state whether bootstrap programs may create source-compatibility files. The claim here is therefore limited to evaluator acceptance, not independently verified compliance with every leaderboard submission rule. The project's legacy integrity result remains preserved as evidence but is not used as a new private scoring threshold.
