# P6 约束操作资格实验 V7

状态：在 Q7 选样、仓库检查或执行之前预注册。

## 目的

Q6 表明仅靠类型化被动修复还不够：proposal 1 前 operation plan 为空，且所有 pair 的 official
Pass 都为零。Q7 是保守 pre-action declaration admission 的首个 outcome-blind development
batch。它检验冻结的 EnvSolve v8 机制，不是 case-specific repair，也不能形成论文级效果 claim。

## 冻结对比

两种 condition 使用相同模型、seed、repository profile、有界 declaration observer、fresh-container
provider、candidate language、Python deployment verifier v4、终局 evaluator 和原始资源上限。

- `envsolve-operation` 在 proposal 1 前接纳无条件标准 package declaration，暴露类型化 operation
  plan，并执行 operation guard。
- `envsolve-operation-ablation` 运行同一 declaration observer，但不接纳类型化初始约束、不暴露
  operation plan，也不使用 operation guard。

候选一旦执行，两种 condition 接收相同 verifier evidence。官方 evaluator 仍只在终局调用，其输出
不能进入在线状态。

## 样本与调度

从 166 个 untouched development case 中按 `SHA256(salt + NUL + case_id)` 升序选择 5 个 identity，
选样只使用 metadata。Pair 顺序和 pair 内方法顺序由独立 salted hash 决定。5 个 identity 一旦物化，
无论 Pass、Fail、Unknown、中断或基础设施删失，都永久标记为 development-consumed。

## 结果

主要描述性结果是 paired official Boolean：full-only Pass、ablation-only Pass、both Pass 或 both Fail。
只有双方 run 都 scientifically eligible 且双方 official result 都是 Boolean 时，该 pair 才进入此表；
其余 pair 按冻结原因报告为 censored。

机制指标只从不可变在线 artifact 计算：

- 初始接纳 evidence 与 constraint 数；
- proposal 1 operation requirement 的数量和 subject；
- proposal 1 是否包含允许的 package mutation；
- candidate、environment、command、model request、token 与 wall time；
- 重复 candidate 或重复 mutation 比例；
- internal-Pass 与进入官方 evaluator 的比例；
- 被 fresh metadata 正观测关闭的 package requirement 数。

观察 Q7 后不再选择阈值。5 个 pair 只能提供 calibration evidence 和错误分析，不是有统计功效的估计。

## 资格与适应规则

每个 run 必须通过 artifact integrity、committed source、schedule identity、primitive budget、完整
heartbeat 和无 host suspension 检查。失败或删失 episode 不得覆盖。

选样后不得修改代码、parser、prompt、verifier、evaluator、预算或协议。若出现共享机制缺陷，完成当前
pair 后关闭 Q7；5 个已选 identity 全部保持 consumed，任何修正都必须建立新 freeze 并使用新的
outcome-blind case。基础设施失败直接删失该 pair，不自动重试。

## Claim 边界

Q7 只能判断机制是否适合进入下一轮 development batch。它不能支持论文主要效果 claim、选择 held-out
预算、查看 Canary 或 Official-Test case，也不能引入 repository/package/module 规则。

