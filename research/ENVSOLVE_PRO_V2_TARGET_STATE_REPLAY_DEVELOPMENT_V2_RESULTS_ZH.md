# EnvSolve-Pro V2 目标状态重放 Development V2

状态：outcome-independent 开发期机制扩展已完成

## 问题

保持最小目标状态重放算法不变，在已有随机 Dev16 顺序最后四个 case 上，treatment 是否继续保持 Official
成功，并真正触发反馈修复？

这是开发期机制实验。四个 case、seed、arm 顺序、模型、provider、镜像、prompt、evaluator 和上限都在
下载源码和执行模型前记录。它不是 held-out、榜单、effect size 或 SOTA 证据。

## 结果

| Pair | 仓库 | A：自由反馈 | B：自由反馈 + 目标重放 | 重放证据 |
|---|---|---:|---:|---|
| 1 | rstcheck | Pass | Pass | B 首次重放通过 |
| 2 | plasmapy | Pass | Pass | B 首次重放通过 |
| 3 | pygeo | Pass | Pass | B 重放 Fail、Pass，加入下载重试后恢复 |
| 4 | starsim | Pass | Pass | B 首次重放通过 |

两臂都是 `4/4`。配对表只有四对 both-pass，没有 discordance，精确 McNemar 为 `p=1.0`。这是一组
ceiling case，不能估计成功率效果。

## 机制实际做了什么

四条 B 轨迹都形成候选、调用重放并最终通过 Official，四次最终 replay 与 Official 全部一致。
rstcheck、plasmapy 和 starsim 第一次 replay 就通过，因此 replay 在这三条轨迹中只承担认证作用。

Pygeo 真正触发了修复 loop。第一次目标状态重放在从 `files.pythonhosted.org` 读取 package metadata 时
发生 pip timeout；同一个活跃 session 把完整程序改成带有界 timeout、retry 和 backoff 的版本。第二次
replay 和 Official 都通过。这证明 replay 能修复一个可执行的部署鲁棒性缺陷，但不能证明系统发现了新的
package、版本、ABI 或平台兼容约束。

## 资源

四对合计，A 使用 157 次模型请求、4.47M Token、190 次 shell 操作和 5,213 秒生成时间；B 使用 129 次
请求、2.10M Token、120 次 shell 操作和 3,769 秒。总量分别下降 18%、53%、37% 和 28%。

只看总量会误导。B-A 的配对请求差为 `+7, -6, -46, +17`，中位数为 `+0.5`；生成时间差为
`+332, -71, -2,017, +314` 秒，中位数为 `+121` 秒。总量优势主要由 pygeo 单例贡献，B 在四对中的
两对反而更慢。因此本批不能证明普遍效率提升。

## 部署完整性

Official Pass 只面向 import，并不能区分唯一的环境质量。rstcheck 和 plasmapy 的两臂都安装项目与开发
依赖；pygeo 两臂都混合真实 package 与可选 native module 的 placeholder，因此虽然 Official-valid，
却没有证明完整功能 runtime；starsim A 把三个旧 package 名别名到 `starsim`，B 则安装真实的 `stisim`
和 `hpvsim`。两者都通过 Official，但 B 的依赖状态更完整。部署完整性必须作为独立结果，不能事后覆盖
官方成功定义。

## 合并开发证据

与上一轮 outcome-independent qualification 合并后，A 为 `6/8`，B 为 `7/8`：6 对都通过、1 对只有 B
通过、0 对只有 A 通过、1 对都失败，精确 McNemar 仍为 `p=1.0`。8 条 B 中有 7 条形成候选，最终 replay
与 Official 一致率为 `7/7`。10 次完整 replay 中 5 次首次通过，2 条轨迹发生反馈修复：
`importlib_metadata` 是兼容性/工作区修复，`pygeo` 是网络鲁棒性修复。

这已经是扎实的机制保真证据，但仍是很弱的效果证据。唯一 B-only Official Pass 首次 replay 即通过，
不能把它和随机搜索路径差异分开。

## 决策

预注册保留条件满足：treatment 成功数没有下降，最终 replay 全部与 Official 一致，并出现一次反馈修复。
算法保持不变。随机 Dev 扩展应在这里停止，因为大量 ceiling case 只消耗样本，无法检验核心主张。下一组
实验必须从既有 census 中预先固定“强 baseline 的 Official bad case”分层，再运行 treatment；不能看完
treatment 结果后挑 case。本批不新增网络规则或任何 case-specific 兼容规则。

机器可读证据位于
`experiments/validations/envsolve_pro_v2_target_state_replay_development_v2_result.json`。
