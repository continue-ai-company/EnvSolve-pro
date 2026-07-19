# P6 约束操作资格实验 V9 结果

状态：按照冻结的 shared-defect 规则，在 pair 1 后关闭。

## 结果

Q9 在一个新 development identity 上执行了 positions 1 和 2。两条 artifact 都通过 integrity 与
scientific eligibility 审计，但都在 official evaluation 前以 `infrastructure_unknown` 终止。该 pair
被删失，不贡献 effectiveness estimate。

| Condition | 请求数 | Tokens | Candidates / commands / environments | 终局 |
| --- | ---: | ---: | ---: | --- |
| EnvSolve v10 | 2 | 12,805 | 2 / 2 / 2 | Unknown |
| Free-form ablation | 1 | 6,169 | 1 / 1 / 1 | Unknown |

没有使用 Official-Test 或 Canary 证据。Positions 3--10 未执行，Q9 已选的 5 个 identity 全部保持
development-consumed。

## 机制判定

预注册的 subject-first Python mismatch diagnostic 没有出现，因此 Q9 trigger count 为零：runtime-
diagnostic v10 既没有通过资格验证，也没有被证明违反主要不变量。Q9 是因为另一个共享 Harness 缺陷
而关闭，目标机制尚未来得及被触发。

## 共享 Harness 缺陷

两种 condition 都执行到了固定 internal command `python -m pytest --collect-only -q`。测试收集尝试
连接 repository-local Elasticsearch 服务 `localhost:9200`，并以 `ConnectionError: connection
refused` 失败。这是 candidate/environment feedback，不是依赖获取基础设施故障。

`PythonDeploymentVerifier` 在区分失败阶段之前，对 candidate 与 internal-check 的合并输出扫描裸
`ConnectionError` token，因此错误报告 `dependency_acquisition_failure`，把两条 verifier 结果从
Fail 改成 Unknown，并在下一次 proposal 前终止 loop。这个错误改变了在线控制流，不能靠离线重标
修复 trajectory。

## 重试与 Claim 边界

冻结的 acquisition retry 不适用：两条 run 都已经完成模型响应并执行 fresh candidate。Evaluator-
only retry 也不适用，因为两条 run 都没有进入 official evaluator。两个 episode 均不得重跑。

Q9 不支持部署效果 claim，也不支持 v10 qualification claim。下一项合规工作是先构造 phase-aware
合成反例，再做通用 verifier 修复与新 freeze，最后使用新的 untouched development identity。修复
不能加入 repository、package、service、endpoint 或 version rule。
