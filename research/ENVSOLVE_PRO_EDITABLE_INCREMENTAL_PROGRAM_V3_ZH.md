# EnvSolve-Pro 可编辑增量程序 V3

## 研究问题

V2 已经证明：强 Agent 会自然区分观察操作与持久部署操作，也能在同一 session 中理解 replay 反馈。
同时，它暴露出两个语义不同的状态被混在了一起：

1. 执行证据是已经发生的历史事实，应当只追加；
2. 当前部署程序是一个待验证假设，一旦 replay 推翻早期步骤，就必须允许修改。

V3 只问一个问题：允许同一个 Agent 修改一条已记录程序步骤，能否把 replay 反例转化为更干净的可执行
修复路径？

## 最小算法

V3 保留 V2 的连续 session 和单个标注式任意 Bash shell：

- `envbench_shell(command, effect=inspect)` 只在活跃构建环境执行；
- `envbench_shell(command, effect=persist)` 在该环境执行，成功后原样追加命令；
- 每次成功追加都执行完整公开目标，目标 Pass 就从目标初始状态 clean replay。

V3 只增加一个非 shell 的计划操作：

`revise_program(step_index, replacement_command)`

- replacement 非空时，替换当前程序中对应序号的步骤；
- replacement 为空时，删除该步骤；
- 编辑只改变当前候选程序，不改变活跃构建环境；
- 每次编辑都立即 clean replay 完整的修改后程序，并把结果返回同一 Agent session；
- 每次结果都返回更新后的、从 1 开始编号的完整程序。

它不是第二个环境修改 shell：不能观察或直接修改活跃构建环境，不能直接安装 package，也不能绕过 replay。
它只编辑“正在被认证的对象”。Agent 认为某一步错误时可直接调用，不由 controller 分类命令，也不设置
何时允许修改的硬规则。

## 三层结构

**观测层：** 普通 shell 输出、每次追加后的完整公开目标观测，以及候选 Pass 或计划编辑后的精确 clean
replay 反例。

**约束层：** 同一个 Agent 根据可执行观测推断当前 case 内未解除的矛盾。历史观测不可改写，harness
不生成 package 或 compatibility 规则。

**操作层：** Agent 可以观察活跃环境、追加新的持久步骤，或者修改一条已有程序步骤。证据轨迹单调累积，
部署程序允许非单调修订。

## V3 不增加什么

V3 不增加 checkpoint、容器快照、package 分类器、版本规则、命令过滤、跨 case 记忆、候选图、固定观测
周期、HARK 专用提示词、新 hash、冻结 contract 或安全 gate。已有 evaluator 隔离与完整性审计继续属于
共享实验基础设施，不算算法 treatment。

V3 仍允许复合持久命令，只记录编辑是否命中复合步骤；命令拆分和路径最小化留作后续正交 treatment。

## 资格验证与 Claim 边界

先用确定性测试验证追加、替换、删除、序号刷新、replay 和同 session 反馈语义。随后可以用已消费 HARK
验证编辑动作是否自然激活，因为 V2 已在该 case 中观测到 replay 推翻错误前缀。如果新轨迹没有产生被
replay 推翻的早期步骤，则按“没有编辑机会”删失，不能算机制失败。

只有当 replay 反例明确指向早期步骤，模型随后自主替换或删除该步，并且修改后的程序真实执行 replay，
机制才通过资格验证。该结果不能支持成功率、效率、泛化或 SOTA。资格验证以后必须先固定 V3，再在结果
未知的开发 batch 上与 V2 或 Minimal B 做配对比较。

效果实验仍以 Official Pass@1 为主终点。诊断指标包括编辑激活、编辑前后程序长度、错误前缀是否保留、
replay 序列、反例到编辑的延迟、replay/Official 一致性、请求数、Token、时间、流量和部署完整性。
Token 与资源只作为测量指标，不作为硬终止阈值。
