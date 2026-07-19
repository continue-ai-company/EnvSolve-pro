# Structured Finding Adapter v1

状态：通过合成资格验证的 adapter contract；尚未执行真实 case。

该 adapter 是 verifier-owned finding 到 solver-owned counterexample evidence 的唯一桥梁。
它接收现有 runtime、package、capability、module 和 platform domain 上的类型化 finding。
Active finding 必须同时给出 required 与 observed value，并转换成 requirement/observation
证据对。Inactive finding 保留在 verification metadata 中，但不形成 repair constraint。
只要存在 unknown finding、verifier 未完成或上游基础设施错误，整个结果就是 Unknown，且
不产生 counterexample。

adapter 不解析日志、repository name、Pyright 文本、package index 或 benchmark-specific
result file。collector 负责 provenance，并负责把原始 diagnostic 分类为 active、inactive
或 unknown 的类型化 finding。不支持的 predicate/domain 组合 fail closed。没有结构化
finding 的确定性 bootstrap failure 保持 failed 但不可规范化，因此 core loop 会阻断，
而不是凭空发明 repair signal。

该合约由 8 个定向测试覆盖，其中包括与 v2 core 的两轮端到端反馈闭环。真实 collector
adapter 仍需单独冻结。
