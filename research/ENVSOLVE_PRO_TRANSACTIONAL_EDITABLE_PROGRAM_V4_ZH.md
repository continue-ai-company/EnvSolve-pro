# EnvSolve-Pro 事务式可编辑程序 V4

## 研究问题

V3 已经证明：强 Agent 能在同一个活跃 session 中，根据 clean replay 反例修改早期部署步骤。它同时
暴露了一个确定性的操作层失败：模型在一次响应里发出多条序号编辑时，前面的删除会改变后续目标序号，
导致两条本来合理的删除变成非法调用，而且每次局部成功编辑都会触发一次昂贵 replay。

V4 只问一个问题：能否用一次基于旧程序快照的事务，完整保留 Agent 的修复意图，同时消除序号漂移和
局部程序反复 replay？

## 最小改动

V4 保留 V3 的观测流、连续模型 session、带意图标注的任意 Bash shell、公开目标、目标状态 clean
replay、evaluator 隔离和可变程序。它只修改 `revise_program`：

- Agent 一次提交非空的替换与删除列表；
- 每个 `step_index` 都相对调用前显示的同一程序解释；
- 整组输入先全部验证，再改变程序状态；
- 所有替换和删除一起应用；
- 只 replay 修改后的最终完整程序一次；
- 不修改、也不回滚活跃构建环境。

V3 runner 原样保留。V4 使用独立 runner identity，因此后续比较或回退不会改写历史方法。

## 三层结构

**观测层：** shell 反馈、完整公开目标观测和精确 clean replay 反例均不改变。

**约束层：** 仍由同一个 Agent 推断当前 case 未解除的矛盾。V4 不增加 package、版本、命令或跨 case
约束规则。

**操作层：** 观察和持久构建操作均不改变；只有计划修复变成“相对一个旧快照解释、整组应用、一次
replay”的事务。

## V4 不增加什么

V4 不增加稳定 step ID、checkpoint、容器快照、controller 分类器、package 规则、命令过滤、候选图、
跨 case 记忆、HARK 专用 prompt、新 hash、冻结 contract 或 gate。序号唯一且在范围内、替换值类型
正确，只是普通事务输入合法性，不是部署策略限制。

## 资格验证

确定性测试覆盖：基于同一旧快照同时替换和非相邻删除、非法 batch 不改变程序、V3 原语义不变、每个
完整 batch 只 replay 一次、runner 注册和工具 schema。测试已同时通过 macOS ARM 与 Spark Linux ARM。

不再用 HARK 做第二次真实资格实验。HARK 已经生成了这个提案，属于已消费 case；再次运行只能确认预期
修复，不能估计算法效果。

## 下一实验

首个 V4 真实实验是在结果未知的固定开发 batch 上，与 Minimal B 做配对比较。两臂共享连续 Agent、
公开目标、clean replay service、模型、provider、seed、镜像、源码权限、evaluator 和宽松安全上限；
只有 V4 维护操作关联的可编辑程序，并暴露事务式计划修复。

Case 必须在看到任何 V4 结果前，从既有 baseline 失败 census 中选择，覆盖主要候选形成和目标重放失败
类型。选样可以使用历史 Repo2Run、Codex、EnvBench baseline 或 Minimal B 结果，但不能使用 V4 结果；
pair 内运行顺序交替。Official Pass@1 是主指标，基础设施删失单独裁决。

诊断指标包括候选形成、编辑激活、非法编辑、replay 序列、反例到有效程序的延迟、请求、Token、时间、
流量和部署质量。先比较成功，再比较资源。干净可复现、完整性、声明一致性和路径成本单独报告，不能改写
Official Pass@1。

V3 保留为表示层 ablation。只有在前瞻实验中两臂都自然激活计划编辑的 episode 上，V3 与 V4 的编辑效率
比较才有意义。
