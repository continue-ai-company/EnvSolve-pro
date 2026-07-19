# P6 约束操作资格实验 V8

状态：在 Q8 选样、仓库检查或执行之前预注册。

## 目的

Q7 表明仅接纳 package state 不能在 fresh candidate 之间保持 runtime compatibility。Q8 是
EnvSolve v9 的首个 outcome-blind development batch，用于检验 image-bound runtime observation、
条件式 runtime constraint admission 和累积操作保持能否在新 case 上成立。它不是 case-specific
repair，也不能支持论文主要效果 claim。

## 冻结对比

两种 condition 使用相同模型、seed、repository profile、有界 declaration observer、断网的
base-runtime observer、fresh-container provider、candidate language、Python deployment verifier v5、
终局 evaluator 与原始资源上限。

- `envsolve-operation` 在 proposal 1 前接纳符合条件的 package/runtime constraint，暴露类型化
  operation plan，并执行 operation guard v3。
- `envsolve-operation-ablation` 运行相同的两个 observer，但不接纳类型化初始约束、不暴露 plan，
  也不使用 operation guard。

两种 condition 获得相同 raw repository profile 和已执行候选反馈。Official evaluator 输出仍只在
终局使用。

## 样本与调度

从剩余 161 个 untouched development case 中按 `SHA256(salt + NUL + case_id)` 升序选择 5 个
identity。选样只使用 identity metadata，不检查仓库，也不按 runtime trigger 预筛。Pair 顺序与 pair
内方法顺序由独立 salted hash 固定。5 个 identity 一旦物化，就永久标记为 development-consumed。

## 预注册结果

主要结果是 runtime-state 机制不变量：

1. 每个 run 的 base-runtime observation 与 candidate environment 使用同一 image digest；
2. Full condition 中每个 runtime mismatch 都在下一次真实执行前形成 hard runtime conflict 和
   `runtime_configure` 操作义务；
3. 只要冲突仍存在，或 candidate-scoped evidence 刚满足 runtime requirement，下一 full candidate
   就必须保留 runtime 操作；
4. 已定位失败 action 的命令前缀不得原样再次执行，但在失败点前发生变化的候选仍可接纳；
5. 不得因 operation-guard exception、畸形 plan 或错误的新颖性要求阻塞本来已覆盖义务的候选。

只有至少一个 scientifically eligible 的 full run 观测到不兼容 runtime declaration 或确定性 runtime
mismatch，并且还有后续 proposal 机会时，才算真正**触发**了 runtime 机制。若 trigger count 为零，
Q8 报告为未覆盖机制，不能据此判定 v9 合格，也不得补选 case。任一不变量违反都属于 shared mechanism
defect，完成当前 pair 后关闭 Q8。

次要描述性结果包括 paired official Boolean、internal-Pass 与 evaluator reach、candidate/token 用量、
重复尝试、runtime 操作数，以及被 fresh 正观测关闭的 package/runtime requirement。只有 pair 双方
scientifically eligible 且 official outcome 都是 Boolean 时，才报告 paired official category。

## 资格与适应规则

每个 run 必须通过 artifact integrity、committed source、schedule identity、primitive budget、完整
heartbeat 与无 host suspension 检查。失败或删失 episode 不得覆盖。

选样后不得修改代码、parser、prompt、verifier、evaluator、预算或协议。共享缺陷会在完成当前 pair 后
关闭 Q8；全部已选 identity 保持 consumed，任何修正都必须建立新 freeze 并使用新 case。基础设施失败
记录为 Unknown 并删失 pair，Q8 内不自动重试。

## Claim 边界

Q8 只能判断 runtime-state v9 是否适合继续 development qualification。它不能形成论文级效果结论、
选择 held-out budget、查看 Canary/Official-Test，也不能引入 repository、package、module 或 version map。
