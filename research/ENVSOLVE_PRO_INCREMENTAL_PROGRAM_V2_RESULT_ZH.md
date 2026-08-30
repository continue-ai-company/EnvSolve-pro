# 标注式增量程序 V2 资格验证结果

## 结果

V2 回答了两个机制问题，也暴露了一个设计错误。在真正出现部署操作机会的两个 episode 中，单 shell 的
`inspect`/`persist` 标注都自然激活。HARK 记录了 8 个成功程序步骤，在第 28 次请求把活跃约束降到
0，并自动从干净环境重放累计程序。Meerkat 在第 15 次请求就记录了主要依赖安装，把目标残差降到 31。
Qibolab 一直在诊断仓库和目标，没有识别出必要部署操作，因此按“未出现操作机会”删失，既不支持也不
否决界面。

HARK 的 replay 随后因为正确的原因失败：前六步写死了 `/data/project`，创建了
`/data/project/.venv`，并误把该路径当成目标源码 checkout。重放同时报告外层 workspace 污染和目标
checkout 文件缺失。同一个 Agent 理解了这个反例，转而在 `/opt/harkenv` 下重建环境；停止时，新环境
已经把约束从 21 条降到 6 条。

## 科研裁决

标注界面以及“观测→约束→操作”状态转换通过资格验证；append-only 程序表示不晋级。一条成功执行但
后来被 replay 证明错误的步骤一旦进入程序，V2 只能在末尾追加补偿，不能替换或删除它。以后每次重放都
必须重复非法或冗余操作。这个问题与具体 package 无关，错误路径、解释器、版本、软件源和安装策略都会
产生同样矛盾。

这轮并没有证明 V2 继续运行后一定无法 Official Pass；追加补偿可能最终通过。它证明的是：当 replay
能够推翻早期决策时，append-only 不适合作为部署计划的核心表示。可执行证据可以单调累积，但当前部署
计划必须允许修改。

下一最小 treatment 保留同一连续 Agent session 和可以执行任意 Bash 的标注式 shell，只增加一个程序
编辑动作：替换或删除一个带序号的已记录步骤，然后立即从干净环境重放修改后的程序。活跃构建环境不回退，
也不增加 checkpoint、package 规则、跨 case 记忆、命令分类器、hash、contract 或 gate。

## 精确证据

| Case | 响应 | 错误 | Inspect | Persist | 成功记录 | Token | 机制结果 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Qibolab | 22 | 0 | 41 | 0 | 0 | 424,406 | 未观测到操作机会 |
| HARK | 32 | 5 | 31 | 9 | 8 | 627,780 | Goal Pass、replay Fail、同 session 改向 |
| Meerkat | 20 | 0 | 29 | 1 | 1 | 417,967 | 更早的实质激活；残差 31 |

三个 episode 都由研究者主动停止，不进入效果终点；本轮没有执行 Official 评测。机器可读裁决位于
`experiments/validations/envsolve_pro_v2_incremental_program_v2_consumed3_result.json`。原始证据
保存在本机 `runs/envsolve-pro-v2-incremental-program-v2-consumed3-evidence/`，以及 Spark 的
`/home/avdpro/work/runs/envsolve-pro-v2-incremental-program-v2-consumed3/`。
