# EnvSolve-Pro V2 原子救援：Consumed-4 结果

## 问题

不增加 package 规则、不限制 Agent 搜索操作，只把交付变成原子提交加干净重放，能否救回四个已有
`F+O` Official 失败？

这是一组按历史失败选择的开发诊断，不是 held-out 效果估计。四个历史对照在 atomic 结果产生前都已
Official Fail。

## 结果

原子交付救回 `1/4`。Hark 在重放反例和同 session 修复后通过；Quacc 形成并修复了候选，但 session
耗尽前没能再次认证提交；Ajenti 和 Micropy 都没有形成候选。

| Case | 首次完整目标 Pass | 首次提交 | 重放 | Official | 主导阶段 |
| --- | ---: | ---: | --- | --- | --- |
| Quacc | 请求 65 | 请求 106 | Fail、Fail | Fail | 交付过晚，随后目标状态/网络恢复 |
| Ajenti | 未达到；最好剩 82 | 无 | 无 | Fail | 候选前命名空间搜索 |
| Hark | 请求 16 | 请求 27 | Fail、Pass | Pass | 交付程序遗漏 fresh-checkout Git 操作 |
| Micropy | 未达到；最好剩 19 | 无 | 无 | Fail | 候选前兼容性搜索 |

四个 episode 合计使用 397 次模型请求、1554 万 Token、40 次 provider error 和 21,199 秒。这些是
结果指标，不是成功的硬阈值。

## 机制证据

Hark 是干净的因果救援。构建状态已经通过公开目标，但 fresh replay 因 Git 把 checkout 判为
dubious ownership 而失败。同一 session 加入 `safe.directory` 后，下一次 replay 和 Official 都通过。

Quacc 暴露了下一个瓶颈。完整目标在请求 65 已通过，Agent 到请求 106 才提交。Replay 随即发现
`torch-scatter` 的真实构建隔离缺陷；Agent 用 `--no-build-isolation` 修复。第二次 replay 转而因 PyPI
读取超时失败，网络重试耗完剩余请求，来不及第三次提交。网络失败与依赖语义缺陷必须分开报告。

Ajenti 和 Micropy 划出了 atomic replay 的作用边界：两次 rollout 都没达到完整目标、也没提交，因此
replay 无法激活；不能用它们证明“已经激活的 replay 无效”。

## 决策

保留 atomic delivery 作为基础能力，但不能根据本轮把“自愿原子提交”晋级为论文主算法。下一组已消费
机制实验把定期可信目标观测与同一个 atomic submit 动作耦合，检验更早返回目标状态反例能否为同 session
修复保留足够余量。Agent 搜索仍然自由，不加入任何 case 专用规则。

机器可读结果：
`experiments/validations/envsolve_pro_v2_atomic_rescue_consumed4_v1_result.json`。

