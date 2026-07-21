# Typed Replay IR v9

## 目的

Typed Replay IR 把交互式成功轨迹转换成可重放的干净部署程序：保留环境变更，删除只读观测，继续拒绝
副作用未知的 shell 片段。本次修订避免只读测试命令使外部 Agent 的有效轨迹在蒸馏阶段失效。

Replay policy 标识：`typed-replay-ir-v9`。

Complete-candidate policy 标识：
`complete-candidate-v4+typed-replay-ir-v9`。

## 相比 v8 的变化

V9 将通过 `python -m` 执行的标准 `tests`、`test`、`pytest` 和 `unittest` 命名空间下的点分模块识别为
测试观测。由 `cut`、`grep`、`head`、`sort`、`tail`、`uniq` 或 `wc` 组成的只读过滤管道仍属于观测。
这些命令在交互 episode 中真实执行并保留于原始轨迹，但不会写入最终 replay script。

这项修改没有增加环境变更、软件源、shell 权限或仓库特定命令。把测试输出传给 shell、写入文件或调用
任意其他模块命名空间的命令仍然被拒绝。v6-v8 的全部语料继续原样执行。

## 动机与边界

外部 baseline 资格测试暴露了一个纯 harness 故障：强 Agent 已完成模型 loop，但 finalizer 仅因测试模块名
含点号而拒绝成功的测试命令。该故障发生在 Agent 终止后、Official evaluation 之前，不能计为方法失败。
V9 只修复这一通用接口，不改变模型 prompt、工具、反馈、停止策略或 Agent 产生的环境变更。

## 验证

V9 的 repository-free 合成增量同时包含点分测试观测正例，以及 shell、文件写入和任意模块反例。冻结前
必须通过 replay、distillation、candidate、recorded-runner 和 harness 的聚焦测试。旧 v8 协议和结果保持
不可变。
