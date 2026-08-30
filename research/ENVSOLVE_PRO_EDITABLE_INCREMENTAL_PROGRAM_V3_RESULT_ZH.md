# EnvSolve-Pro 可编辑增量程序 V3 结果

## 裁决

V3 通过了已消费 case 上的机制资格验证，但尚未通过效果或效率验证，不能因为一个 HARK 结果就晋升为
最终算法。

有效 retry 完整出现了设计要求的因果链：

1. 活跃构建环境先达到完整公开目标；
2. 自动 clean replay 推翻了早期 `/data/project` 程序步骤；
3. 同一个 Agent session 替换并删除了早期步骤；
4. 每次成功编辑都立即重放修改后的完整程序；
5. 后续持久步骤最终同时通过 clean replay 和 Official EnvBench。

这比“模型调用过编辑工具”更强：replay 反例真正改变了被认证的部署程序，而不只是改变 Agent 的解释或
让它继续追加补偿命令。

## 基础设施删失

第一次尝试必须排除。request 12 的首个 `effect=persist` 命令在构建环境中执行成功，但 runner wiring
缺失，返回 `incremental services are unavailable`，没有记录步骤。修复只为
`incremental-editable` 构造 replay service，并增加 runner 层回归断言。fresh retry 的 case、模型、
provider、seed、prompt、工具语义、evaluator 和分析规则均未改变。

## 有效 Retry

HARK 共得到 39 次模型响应、47 次 provider 尝试，其中 8 次 provider 错误均恢复。全程使用
1,028,668 token、37 次 shell、8 次程序编辑和 8 次 clean replay；前 7 次 replay 失败，最后一次
通过。端到端耗时 2,862.0 秒，随后 Official EnvBench 以零计分问题通过。

构建环境在 request 30 首次达到公开目标 Pass。replay 拒绝了项目目录内的虚拟环境和硬编码
`/data/project` 假设。首次计划编辑出现在 request 34。总计 6 次编辑成功，包括 1 次替换和 5 次
删除；修改后的程序最终得到 clean replay Pass 和 Official Pass。

## 新发现的失败

数字序号编辑接口不能正确组合单次模型响应中的多条编辑。Agent 针对自己刚看到的程序一次发出 6 个
修改；前面的删除立即改变了后续步骤序号，导致后两次调用出现非法序号。Agent 在下一次请求中恢复，
但额外消耗了模型请求、replay 和环境执行。

如果在效果实验前修复该缺陷，最小后继方案应是：所有编辑都相对编辑前快照解释，作为一个原子 batch
应用，完成后只 replay 一次。这比增加稳定 step ID、checkpoint、package 规则或 controller gate 更简单。

## 榜单指标与部署质量

最终三步程序同时通过 clean replay 和 Official EnvBench，但不是完整、忠实的 HARK 部署。它创建了
`/opt/harkenv` 却从未使用；把依赖安装到默认 Conda；没有安装项目本身；仓库声明
`numba<0.60.0`，程序却安装 `numba>=0.61`。

因此后续实验必须区分五个结果：Official 成功、干净可复现、部署完整性、声明一致性和路径成本。
Official Pass@1 仍然是刷榜主指标；其余指标用于解释系统究竟部署出了什么，以及资源比较是否有意义。

## Claim 边界

这个已消费 episode 只证明“部署程序可编辑”和“replay 反例能驱动同 session 修改”两项机制成立。
它不能证明泛化、SOTA、成功率提升或资源下降。下一组效果实验必须使用结果未知、固定且配对的开发 batch，
并把路径质量与 Official Pass@1 分开报告。

机器可读结果：
`experiments/validations/envsolve_pro_v2_editable_incremental_program_v3_hark1_result.json`。
