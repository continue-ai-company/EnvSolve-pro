# 目标状态反例重放：已消费 case 机制检查

状态：已完成，2026-08-20

## 问题

完整部署程序在真实目标缓存状态中重放后，能否把有用的可执行反例返回给同一个活跃 Agent session？本实验
只使用三个已经消费过的开发 case 检查机制，不估计效果和泛化能力。

## 结果

三个最终通过冷重放认证的程序都通过了 EnvBench Official。basxconnect 和 Graphium 真实触发了反馈修复，
cvxportfolio 第一次冷重放就通过。

| Case | 重放序列 | 同 session 修复 | Official |
|---|---|---:|---:|
| basxconnect | 失败 -> 通过 | 是 | 通过 |
| graphium | 失败 -> 失败 -> 失败 -> 网络失败 -> 通过 | 是 | 通过 |
| cvxportfolio | 通过 | 否，仅认证 | 通过 |

三条轨迹共使用 139 次模型请求、137 次 shell 操作和 3,133,930 tokens。8 次冷重放包含 5 次失败和 3 次
最终通过。Graphium 出现两次 provider 连接错误，均在同一 session 内自动恢复。

## 因果证据

basxconnect 的重放复现了完整程序遗漏 Git ownership 操作的问题。Agent 随后加入相对仓库根目录的
`safe.directory` 命令，修改后的程序通过重放和 Official。

Graphium 的证据更强。旧版 warm replay 曾经通过，但 Official 失败；新版冷重放依次暴露了不存在的
torchvision 版本、缺失的 Git ownership 处理和遗漏的测试依赖。每个反例都返回同一 session，并导致完整
程序发生变化。之后一次 Conda 下载出现 `HTTP 000`，它被视为网络证据，没有转成兼容性规则；下一次重放
和 Official 均通过。

cvxportfolio 的第一次冷重放与 Official 都通过。历史 package-index 失败没有复现，因此不能据此增加
package-specific 修复规则。

## 不能声称什么

这三个 case 是因为旧轨迹暴露过 replay 问题才被选中的，所以 3/3 不能估计期望成功率。本实验也没有配对
control，每个 case 只有一次实现。

路径质量仍未解决。Graphium 使用 82 次请求、232 万 tokens、约 1 小时生成时间，构建缓存达到 1.2 GiB。
Agent 自主发现并退出了错误的 CUDA 依赖路径，但此前已经产生大量下载。ARM 结果还使用 PopTorch 兼容
模块而非真实 IPU runtime，因此 Official 成功与完整部署能力必须分开报告。

## 决策

保留最简单的候选算法：一个自由的连续 Agent session，加上可反复调用的完整程序目标状态反例重放。不
加入 package 规则、定时观测、checkpoint、跨 case 记忆或新的硬操作约束。

下一步是在打开仓库前预注册独立 qualification batch，并使用同模型 control。Official Pass@1 是主指标，
路径质量单独报告。
