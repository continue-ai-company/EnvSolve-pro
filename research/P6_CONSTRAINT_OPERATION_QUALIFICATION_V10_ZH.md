# P6 约束操作资格实验 V10

状态：在 Q10 选样、仓库检查或执行之前预注册。

## 目的

Q9 因不感知 phase 的 `ConnectionError` 签名而关闭：internal test-collection failure 被错标为依赖
获取基础设施故障。Q10 是 phase-aware verifier v11 的首个 outcome-blind development qualification，
检验决定 loop 终止或继续的是 failure provenance，而不是单独的异常 token。

## 冻结对比

Paired comparison 保持不变。两种 condition 共享 model、seed、repository/base-runtime observer、
fresh environment、candidate language、Python verifier v5、终局 official evaluator 与原始资源上限。
Full EnvSolve 获得 typed admission、operation-plan visibility 和 guard；ablation 获得相同 raw
observation 与 executed-candidate feedback，但不使用这三个组件。Official evaluator feedback 仍只在
终局使用。

## 样本与调度

从剩余 151 个 untouched development case 中按 `SHA256(salt + NUL + case_id)` 升序选择 5 个
identity。选样只使用 identity metadata，不检查仓库，不预筛 failure signature，不按 package manager
分层，也不补选。Pair 和 method 顺序由独立冻结 hash 决定。5 个 selected identity 全部永久标记为
development-consumed。

## 主要 Phase 机制

Scientifically eligible run 必须同时满足以下条件，才算触发 v11：

1. failed-action marker 把失败定位在固定 internal-check phase；
2. 对应 raw output 含有冻结的通用 network-like signature；
3. candidate 与 model budget 仍允许至少一次后续 proposal。

对每条触发 run，verifier 必须返回 candidate Fail 而不是 infrastructure Unknown，把 action result 保留
为 online feedback，并真实进入后续 proposal。反向安全不变量也保持冻结：candidate-command 或
unknown phase 中有依据的网络签名仍可产生 infrastructure Unknown，不得被转成 hard candidate
constraint。

V10 的 subject-first runtime diagnostic 是独立继承不变量。如果它出现在 full run 中，仍必须形成
预注册的 hard runtime conflict 与 `runtime_configure` obligation；没有出现不能据此宣布 v10 合格。

若没有 run 触发 phase mechanism，Q10 只能报告未触发，v11 不算合格，也不得补选。任何已触发 phase
不变量或继承 runtime 不变量违反都会在完成当前 pair 后关闭 Q10。Paired official outcome 只是次要
结果，必须由两条 eligible Boolean result 构成。

## 资格、重试与 Claim

Artifact integrity、committed clean source、schedule identity、primitive budget、完整 heartbeat 与
无 host suspension 是硬条件。只有零 method information 的 pre-episode acquisition failure 可获得一次
同 identity 重试；终局 evaluator 基础设施失败可对相同冻结脚本执行一次 evaluator-only retry。其他
失败直接删失 pair。

Q10 只能判断 phase-aware v11 是否适合继续 development。它不能证明部署效果、调整预算、查看 held-
out case，也不能加入 repository、service、endpoint、package、module 或 version rule。
