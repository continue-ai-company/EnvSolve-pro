# 增量可执行程序 V1 资格验证结果

## 结果

固定的三个已消费 case 在进入效果比较前，就否决了 V1 的双工具界面。46 次成功模型响应中，Agent
调用普通 shell 69 次，只调用 `apply_environment_step` 1 次。Qibolab 和 HARK 从未激活定义性
路径；Meerkat 直到第 20 次请求、经过 31 次普通 shell 后才首次激活，记录了一步成功的
`pydantic<2`，此后仍有 79 条活跃约束。三个 case 都没有进入 replay，也没有执行 Official 评测。

最清楚的反例是 HARK 第 6 次请求：Agent 通过 `envbench_shell` 成功执行了
`python -m pip install -e ".[dev,doc]"`。这是真正改变环境的部署操作，本应进入增量程序，却绕过了
新路径。说明 Agent 延续了“用一个 shell 同时观察和修改环境”的既有习惯，没有自然地把两个相似工具
理解成不同语义通道。

## 裁决

这是交互界面失败，不是对“增量构建部署程序”思想的反证。本轮没有跑到足以估计 Official 成功率的
阶段，三条 episode 全部排除在效果终点之外。模型连接错误都通过重试恢复；持久操作绕行发生在正常响应
恢复以后，所以网络波动只是次要噪声，不是机制未激活的原因。

V1 到此停止，不用更强提示词继续修补。下一最小 treatment 只暴露一个可以执行任意 Bash 的 shell
工具，并要求每次调用声明其效果是“仅观察”还是“持久程序步骤”。持久调用成功后，追加到程序并触发已有
目标检查与 replay 转换。它只改变操作界面，不增加 package 规则、命令过滤、checkpoint、跨 case
记忆、hash、冻结 contract 或 gate。

## 精确证据

| Case | 成功响应 | Provider 错误 | Shell | Apply | Token | 结果 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Qibolab | 15 | 2 | 29 | 0 | 239,622 | 研究者停止 |
| HARK | 10 | 5 | 9 | 0 | 62,532 | 研究者停止 |
| Meerkat | 21 | 4 | 31 | 1 | 292,238 | 研究者停止 |

机器可读裁决位于
`experiments/validations/envsolve_pro_v2_incremental_program_v1_consumed3_result.json`。
原始部分证据保存在本机
`runs/envsolve-pro-v2-incremental-program-v1-consumed3-evidence/`，以及 Spark 的
`/home/avdpro/work/runs/envsolve-pro-v2-incremental-program-v1-consumed3/`。
