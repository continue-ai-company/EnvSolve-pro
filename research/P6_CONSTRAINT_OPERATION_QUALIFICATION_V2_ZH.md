# P6 约束操作层资格实验 V2

状态：Q2 选样和执行之前的协议修订。

Q1 永久判为 qualification-invalid：candidate validator 接受
`python -m venv .venv|venv`，operation guard 却拒绝同一条规范化命令。前两个位置只作为 harness
诊断保存在 `experiments/validations/p6_operation_q1_closure.json`；Q1 选中的五个 case 全部保持
development-consumed。

V2 只做一项表示一致性修正：限定在项目根的 virtual-environment creation 成为 validator 与 guard
共享的 typed replay action。它不能作为 runtime、package、capability 或 module repair obligation
的满足证据。不改变仓库规则、package mapping、evidence parser、constraint、verifier、模型、预算、
指标或因果 treatment。

Q2 从 `experiments/cases/train_untouched_after_operation_qualification191.jsonl` 使用新 salt
`envsolve-p6-operation-qualification-v2-2026-07-17`，按相同 metadata-only SHA256 升序流程重新选取
五个 case。除 source pool、salt、run ID 和修正后的 parent freeze 外，V1 完整协议继续有效。

