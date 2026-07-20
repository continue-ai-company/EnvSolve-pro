# Typed Replay IR v8 与 Complete Candidate v4

## 目的

本次 revision 在不改变 accepted candidate language 的前提下，为观测接纳增加 provenance。共享
validator 现在会为每个已接纳 mutation 输出 canonical command 与 typed action kind；verifier 可以
据此要求失败命令类型与 provider error signature 一致。

Replay policy 标识：`typed-replay-ir-v8`。

Complete-candidate policy 标识：
`complete-candidate-v4+typed-replay-ir-v8`。

## 相对 v7 的变化

V7 的全部命令、canonicalization、virtual-environment binding 与拒绝规则原样继承。V8 只在 validator
结果中新增有序、去重的 `actions` 记录；每项只含 replay parser 已经产生的 `command` 和 `kind`。
元数据缺失、格式错误、有歧义或与失败命令不一致时，verifier 一律 fail closed。

这是 evidence interface 变化，不是 shell 权限扩张。它防止 runtime 或无关 operation 产生的类
provider 文本片段被误接纳为负 package-operation fact。

## 验证

V6 与 V7 的既有 corpus 全部继续生效。V8 delta 检查 provider-failure admission 所需的 operation
kind，candidate 测试验证输出的 action record。Replay、candidate、verifier、constraint、guard 与
loop 的聚焦测试全部通过。本接口不通过重跑 development repository 来资格验证。
