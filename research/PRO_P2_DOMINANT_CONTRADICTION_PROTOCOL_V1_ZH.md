# EnvSolve-pro P2 主导矛盾协议 v1

## 研究问题

消除接口删失后，阻止强 Agent 到达正确终局环境的第一个高频、可干预部署矛盾是什么？P2 只诊断这个
矛盾，在此之前不增加 EnvSolve-pro 算法机制。

## 样本

从剩余 118 个 untouched EnvBench Dev case 中，按
`SHA256(salt + NUL + case_id)` 升序抽取 6 个。抽样只使用元数据：不 checkout 仓库、不预筛错误、不按
包管理器分层、不替换 case，也不使用既有结果。入选 case 立即成为诊断数据，之后不能承担确认性效果
证据。

## 冻结方法

每个 case 按 salted order 运行四种方法：

1. 使用本地登录态 `gpt-5.5` 的 Codex CLI native agent；
2. 使用 `deepseek/deepseek-v4-pro` 的 Repo2Run reproduced；
3. 使用同一 DeepSeek 模型的 EnvBench raw ReAct；
4. 使用同一 DeepSeek 模型的 P1 EnvSolve-pro scaffold。

所有方法只能在终局访问 Official evaluator。三个 API 方法使用相同的宽松 operational circuit breaker；
资源只记录，不参与成功判定。Codex 保留原生停止规则。不开启跨 case 记忆。

## 分析单位

对每条完整轨迹识别**最早决定性修复机会**：第一个已经出现、且若采用不同状态更新或操作就可能改变
终局的条件。每条轨迹只分配一个主层级，可以保留次级标签。

- **观测层：** 决定性证据不可得、丢失、被误判为算法结果，或没有跨执行上下文传递；
- **约束层：** 已有证据没有转化为缺失/冲突条件，错误 belief 在反证后仍保留，或未解决义务被丢弃；
- **操作层：** 相关条件已经被表示，但没有提出、执行、保留、修复或正确 finalization 可行的环境改变。

基础设施删失保持 Unknown，不归入算法层。若轨迹中看不到决定性机会，则标为 unresolved，不强行分类。

## 主导性门槛

只有某一矛盾家族同时满足以下条件，才允许提出新机制：

- 至少出现在 3 个不同仓库；
- 由直接轨迹证据支持，而不是仅根据 terminal error count；
- 跨至少 2 种方法出现，或具有确定性的方法特定原因；
- 能在三层之一形成 repository-independent 干预；
- 不是 evaluator 接口或网络伪影。

若没有任何家族通过门槛，则另行预注册扩展诊断样本，不能降低门槛或针对孤立 case 优化。

## 冻结规则

P1 提交、prompt、candidate interface、verifier、adapter、baseline compiler、official protocol、方法矩阵、
样本数、salt 和归因规则必须在抽样前冻结。24 个位置执行期间禁止修改 solver 或 wrapper。只有在没有
产生有效模型回复、也没有执行环境命令时，才允许基础设施重试；否则保留 partial episode 并标 Unknown。

P2 可以提出算法假设，但不能证明 EnvSolve-pro 有效果。
