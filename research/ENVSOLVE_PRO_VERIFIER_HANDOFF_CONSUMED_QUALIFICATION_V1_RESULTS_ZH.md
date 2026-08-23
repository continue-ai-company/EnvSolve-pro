# Verifier Handoff 已消费资格实验 V1

## 问题

当可信可执行目标已经证明构建环境充分时，controller 能否让连续部署 Agent 立刻把当前状态整理成可重放
程序，而不增加 package 规则，也不限制 Agent 的搜索空间？

本实验使用已经消费过的 qibolab 失败轨迹，只用于验证机制，不是未见 case 效果实验。

## 结果

两组都通过 EnvBench Official。Control 在 request 72、shell operation 96 首次得到完整 scheduled Pass，
但又执行了 11 次模型请求和 10 次 shell 操作，才提交候选。Treatment 在 request 64 得到完整 Pass，
controller 只触发一次 handoff，并在没有新增 shell 操作的情况下强制 request 65 提交候选。

Treatment 第一次干净重放发现 `qibo==0.2.16` 与显式固定的 `networkx==3.0` 冲突。该反例返回同一
session，Agent 删除冲突 pin，第二次重放通过，controller 直接返回认证程序。预注册的完整机制链已经
发生：

```text
可信 Pass -> controller handoff -> 完整程序 -> 干净重放 Fail
           -> 同 session 修复 -> 干净重放 Pass -> Official Pass
```

## 描述性资源结果

| 指标 | Scheduled control | Verifier handoff | 差异 |
|---|---:|---:|---:|
| Official Pass | 1 | 1 | 持平 |
| 模型请求 | 84 | 66 | -21.4% |
| 总 Token | 5,492,967 | 2,593,497 | -52.8% |
| 记录的容器命令 | 130 | 98 | -24.6% |
| 生成时间 | 2,685.8 s | 1,803.2 s | -32.9% |
| 端到端时间 | 3,098.3 s | 2,149.2 s | -30.6% |
| Pass 到认证 Token | 1,139,973 | 151,463 | -86.7% |
| 最终程序大小 | 4,252 B | 3,770 B | -11.3% |

这些数字只来自一对已消费 case，不能证明效率增益。Treatment 做了两次 replay，control 只做一次；
treatment 仍更快，原因是它消除了 Pass 后继续搜索的长尾。

## 科研裁决

可执行 handoff 机制通过资格验证。它解决了 incumbent retention 无法触达的操作层失败：在推理 session
仍活跃时，把已验证的充分状态转成一次完整程序重放。

Runner 0.6.0 还存在一个因果设计混杂：treatment 初始 prompt 提前透露了未来 handoff，因此 trigger
前接口并非完全一致。Runner 0.6.1 删除这段提前说明，使 control 与 treatment 在触发前拥有相同工具和
相同初始 prompt；只有 `candidate_ready` 后才注入 handoff 指令。该修正已通过回归测试，但不产生新的
线上效果 claim。

下一步使用 runner 0.6.1 预注册固定的 prospective bad-case 对照。不能根据 qibolab 新增依赖规则、
checkpoint、跨 case 记忆或动作 gate。
