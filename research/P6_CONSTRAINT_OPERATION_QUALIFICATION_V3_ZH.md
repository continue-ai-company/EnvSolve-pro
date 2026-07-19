# P6 约束操作层资格实验 V3

状态：Q3 选样和执行之前的协议修订。

Q2 在第一组配对 case 后永久关闭。两个 episode 都是可审计的负向机制证据，但 full treatment
暴露出一项违背部分可观测语义的状态转移：只包含 hypothesis 的 verifier 失败错误地清除了来自
前一个 fresh environment、仍未解决的 fact。该配对及全部五个 Q2 case 均保持
development-consumed；Q2 剩余八个位置不得执行。

V3 只做一项通用状态转移修正。fresh-environment verifier 的输出是部分观测，而不是完整环境快照。
只有后续输出规范化出具有相同 `(domain, subject, predicate)` 键的新 fact 时，旧 active fact
才会退休。hypothesis-only 失败，或没有观测该变量的失败，必须保留旧 fact 及其 operation
obligation。verifier 通过后 episode 已成功终止，因此可以清除全部 active facts。

修正只使用合成名称定义和测试，不新增仓库规则、package mapping、parser pattern、repair action、
模型 prompt、verifier 信号、预算、指标或 treatment-specific 信息。

Q3 从 `experiments/cases/train_untouched_after_operation_qualification_v2_186.jsonl`
中，使用 salt `envsolve-p6-operation-qualification-v3-2026-07-17`，按
`SHA256(salt + NUL + case_id)` 升序 outcome-blind 选择五个新 case，并重复冻结的配对比较。
除 source pool、salt、run ID、Q2 closure 和修正后的 mechanism freeze 外，V1 协议继续有效。
任何 Q1 或 Q2 case 都不得复用。

