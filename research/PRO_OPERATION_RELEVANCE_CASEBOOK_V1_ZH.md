# EnvSolve-Pro 操作相关性资格实验 Casebook v1

状态：pre-closure 诊断记录。这些仓库已经成为开发证据，不能再作为 held-out 或最终
test 证据。

## 证据边界

冻结的五仓库配对实验比较 `envsolve-pro-operation-contract` 与 frozen fresh
`envsolve-pro-goal-contract-evidence-anchor`。原始分析、修正后的测量分析、
infrastructure amendment、schedule 和 artifact 哈希均保存在
`experiments/validations/pro_operation_relevance_contract_v1_*`。

基础设施 closure 前，只有 Django 得到完整配对。Trax 两组都被 provider 超时删失；
UER-py 的 treatment 因方法自身操作超时而未通过，control 被 provider 额度删失；
Tortoise ORM 与 libEnsemble 没有获得任何有效模型响应。当前不能做总体效果声明。

## Case 1：django-registration

两种方法都得到 identity-matched Official Pass，计分 issue 为零。

| 条件 | 候选数 | 请求数 | Tokens | 环境数 | Generation 秒 |
| --- | ---: | ---: | ---: | ---: | ---: |
| operation contract | 2 | 2 | 19,912 | 2 | 181.5 |
| frozen control | 1 | 1 | 6,470 | 1 | 148.3 |

treatment 第一轮留下一个 `nox` finding；第二轮操作明确指向它，引用执行与仓库证据，
随后 internal 和 Official 都通过。这是一条有效的状态化修复轨迹。但 control 第一轮
直接通过，所以本 case 没有成功率增益，且 treatment 开销明显更高。

## Case 2：Trax

两组都因后续 provider 请求超时而没有到达 Official evaluation；原始 attempt 全部
保留，并进入精确 infrastructure retry。control 运行时还因为分析代码尚未提交而没有
通过 clean-source eligibility；runtime 算法文件本身保持冻结。

现有 internal 轨迹仍有诊断价值：

| 条件 | 首次完整 finding 数 | 后续完整 finding 数 | 候选数 | Tokens |
| --- | ---: | ---: | ---: | ---: |
| frozen control | 375 | 无 | 1 | 9,492 |
| operation contract | 48 | 39 | 3 | 103,658 |

treatment 首次操作更窄，明显缩小了未解决 surface。第二轮因依赖构建缺少 `cmake`，
没有进入目标验证。第三轮累计操作安装了构建工具并完成执行，但只把 finding 从 48
降到 39。

两次 policy rejection 共包含 47 个 unknown target ID。用完整 active snapshot 做
post-hoc 审计后，30 个其实仍然 active，只是被有界 operation context 省略；17 个确实
不 active。因此精确 ID 合同同时混合了两类错误：投影丢失和模型幻觉。当前没有发生
failed-script 或 same-family suppression。

## Case 3：UER-py

按冻结协议，treatment 是 primary non-pass。第一轮安装仓库声明依赖后暴露 11 个缺失
模块；第二轮针对全部 11 个 finding，增加包括 TensorFlow 在内的 README optional
dependencies，但在产生完整目标观测前超过 1,200 秒候选命令上限。其描述性状态仍是
`execution_timeout_unknown`，但不符合 infrastructure retry 条件。

control 首轮采用宽安装，把目标缩小到唯一的 `tensorflow.keras.backend` finding。
随后分别尝试 Python 3.11 + TensorFlow 2.15，以及 Python 3.10 + TensorFlow 2.14；
两次完整快照都保留同一 finding。第四次模型请求被 provider 额度拒绝，因此 control
属于外部删失，进入精确重试。

这条轨迹区分了“约束可见”和“操作可行”。两种方法都能保留精确的未解决 import，
但现有操作都没有建立“已经安装的 TensorFlow 为什么仍对静态目标不可见”的原因；
treatment 的证据合同也没有阻止昂贵且无法到达终局的依赖扩张。

## Case 4-5：Tortoise ORM 与 libEnsemble

四个 episode 都在获得有效模型响应前收到 HTTP 402，没有生成候选或环境，也没有任何
方法信息。provider 额度恢复后，可以使用新 run ID 重试；原始 artifact 保持不变。

## 暂定跨 Case 诊断

1. 合同可以表达低维、正确的修复，但 Django 没有成功率增益，资源开销反而更高。
2. 精确 finding ID 与固定投影窗口在高 fanout case 上产生了不必要的接口摩擦。
   grouped 或可查询 target 是候选重设计，不是一个被删失 case 已经证明的结论。
3. 证据来源约束本身不能证明操作可行。UER-py 表明缺少的诊断可能是运行时或包布局
   语义，而不只是未解决 import 的名字。
4. 预注册的 duplicate-family suppression 从未被触发，因此 v1 尚无 suppression
   机制资格信号。

在冻结 infrastructure closure 完成前，不允许修改算法。最终解释必须以 Official
Pass@1 为主，将方法自身无法到达终局计为 non-pass，只删失外部失败，并同时报告原始
与修正后的测量口径。
