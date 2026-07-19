# P6 约束操作资格实验 V10 结果

状态：五组 pair 全部按照预注册协议执行完成，目标 phase trigger 为零，batch 已关闭。

## 结果

Q10 在 5 个新的 development identity 上执行了全部 10 条 schedule run。10 条 run 全部
artifact-valid 且 scientifically eligible，41 份 environment receipt 全部匹配冻结镜像身份；没有
模型请求错误、host suspension 排除或官方 evaluator 执行。10 条 run 都在 candidate limit 结束，
因此 5 组 paired effectiveness outcome 全部删失。

| 条件 | Runs | Requests | Tokens | Candidates / commands / environments | Wall time |
| --- | ---: | ---: | ---: | ---: | ---: |
| EnvSolve v11 | 5 | 26 | 251,162 | 25 / 20 / 20 | 3,686.9 s |
| Free-form ablation | 5 | 27 | 244,553 | 25 / 21 / 21 | 5,174.2 s |

资源总量只能作描述性分析。两种条件都没有产生 official Boolean outcome，因此 Q10 不能提供部署
效果估计。

## 机制结论

50 个 candidate action 中，10 个失败带有 internal-check marker，其中 8 个后面仍有 proposal
机会；但所有 raw output 中冻结的 network-like signature 都是 0。因此预注册的组合触发条件在
0 条 run 中成立。41 个实际执行的 candidate 全部保持 candidate `Fail`，没有 verifier result 被
升级为 infrastructure `Unknown`。

所以 phase-aware verifier v11 在 Q10 中属于 **未触发**：既没有得到前瞻性资格验证，也没有被
反驳。Q9 的错误转移没有再次出现，这可以作为 Harness 稳定性证据，但不能代替冻结的正向触发。
由于没有 grounded network signature，反向 candidate-network 不变量同样未触发。

另有 2 条 subject-first Python mismatch diagnostic 只出现在 free-form ablation。继承的 runtime
不变量预注册为 full EnvSolve run 的判据，而 full 中触发数为 0，因此 runtime diagnostic v10 也只是
未触发，不是不变量失败。

## 科研含义

Q10 之后不应只是为了寻找一个稀有日志 token 而继续盲目启动新的 qualification batch。当前更大的
主要矛盾是：全部 run 都在 candidate budget 耗尽前无法进入 official evaluation。下一步应对这些已
消费的 development trajectory 做聚合错误分析，分别统计执行前拒绝、candidate command failure、
固定 internal-check failure 与未解决的 structured obligation；找到跨 repository 的主要状态转移
缺陷；再用合成反例定义任何通用算法修改。

Q10 的 5 个 identity 全部保持 consumed，不允许补选或重跑；仍有 146 个 development identity 保持
untouched。本轮没有使用 Official-Test 或 Canary evidence。
