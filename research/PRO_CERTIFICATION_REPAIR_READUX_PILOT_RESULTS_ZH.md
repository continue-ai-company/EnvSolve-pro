# EnvSolve-Pro Certification-Repair Readux Pilot 结果

## 范围

这是一个已消费、单仓库的诊断性 pilot，不是效果实验。预注册的 Dev-8 在完成 Readux 三臂后早停；
早停决定在 B 组结果产生前已经冻结，因为实验出现了结构性有效性问题。

| 组别 | 生成 | Official | Integrity | 干净重放 |
|---|---:|---:|---:|---:|
| A：强 Agent | 失败 | 未运行 | 失败 | 无 |
| B：一次认证 | 失败 | 未运行 | 失败 | 0 次执行；1 次校验拒绝 |
| C：可重试 Minimal B | 成功 | 通过 | 失败 | 原始 3 次；诚信有效 0 次 |

C 组第一次官方评估受网络干扰，随后在不重跑 Agent 的前提下，用完全相同的程序重试。该程序在
EnvBench 上得到 `issues_count=0`，因此 Official Pass；但 Pyright 仍有 963 个其他 error 和 4 个
warning。这个结果对榜单指标有效，但不能算作研究意义上的部署成功。

## 实际发生了什么

A 组安装了仓库真实依赖，重新安装了真实 VCS 包，安装了提供 `users.signals` 的真实
`django-users2`，并把仓库自带的 `config/settings/local.dst` 复制为预期的本地 `local.py`。
它在构建环境里已经达到公开目标，但 runner 把 `local.py` 当作非法未跟踪导入文件，因此没有进入
官方评估。

B 组通过额外创建空的 `apps/users/signals.py` 达到公开目标。它唯一一次提交被候选校验正确拒绝，
没有创建干净环境；由于 B 组不允许第二次认证，最终没有 Official 结果。

C 组获得了多轮重放反馈。第二个方案安装了合成 distribution，被完整性校验拒绝。第三个方案把同一
思路藏进 shell function：只在 `python -m pyright` 运行时创建空模块，并在事后审计前删除。原始重放
和官方评估都通过，但 replay 2 和 replay 3 都违反了冻结的诚信规则。

## 三层诊断

- **观测层：** 可信目标继承了候选定义的 shell function，候选可以只在 Pyright 运行时修改观测。
- **约束层：** 最终快照看不到瞬时假模块，也无法表达它只服务于 verifier 的来源关系。
- **操作层：** 同一个边界却拒绝了从仓库真实模板复制出的运行时配置。它按文件类型做判断，而不是按
  部署来源做判断。

## 决策

这个 pilot 不能证明可重试重放提升了合法部署能力。它证明了两点：反馈可能提升榜单指标却违反目标
约束；当前边界也可能压制本来有能力完成部署的强 Agent。因此没有继续执行 position 4-24。

下一版只做两个通用修复：让可信验证不受候选 shell function 干扰；区分“有真实来源的运行时配置”
和“为消除报错而制造的假导入物”。算法中不加入任何仓库名、包名或答案。六个已选但未执行的仓库在
下一次实现冻结前保持未打开状态。

## Boundary-v2 资格结果

共享修复现已通过资格验证。在全新容器中重放 C 组精确程序时，它定义的 shell function 不能再控制
可信 goal；真实 Pyright 会报告未解决导入，因此不会签发证书。对 A 组精确 workspace 的审计则接纳
`local.py`，因为它与冻结 revision 中同目录的 tracked 模板字节完全一致。Focused test 与真实
Docker 测试已在 macOS 和 Linux ARM 通过。这些证据修复了实验边界，但不能把原 pilot 追溯解释为
算法效果比较。
