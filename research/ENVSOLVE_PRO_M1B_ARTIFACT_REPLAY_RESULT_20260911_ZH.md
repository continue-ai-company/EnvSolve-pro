# EnvSolve-Pro M1b 程序工件重放阶段报告

日期：2026-09-11

## 问题与边界

M1b 要回答：D2 修复后得到的原样部署程序，能否在全新环境中反复复用；P 产生的程序，是否比
简单控制组更可靠或执行成本更低。实验只使用 4 个已经消耗过的 Dev 项目，按预先固定的交错顺序
重复 3 轮；不调用模型、不更新状态，在 Spark 上完成 51 次物理 clean replay。

这里测的是公开目标 qualification，不是新一轮 EnvBench Official 评分；它也是程序工件层面的补充
实验。因此它不能单独证明 Official 成功、结构化状态机制、逐步最优性或经验性的修复成本回本点。

## 固定结果

`A` 表示依赖获取失败，`T` 表示传输删失，`M` 表示目标 Python 版本不匹配。程序相同时只执行
一次物理测量，不能把不同 arm 名称当成独立样本。

| 位置 | 最终 P | 最终 R0 | 最终 R1 | 程序关系 |
|---|---:|---:|---:|---|
| 10，ceph-ansible | 3 pass | 3 pass | 3 pass | P = R0 |
| 17，mpmath | 3 pass | 2 pass + 1 A | 2 pass + 1 A | 各不相同 |
| 22，fontbakery | 3 pass | 2 pass + 1 A | 2 pass + 1 A | R0 = R1 |
| 23，reproject | 2 pass + 1 T | 3 pass | 2 pass + 1 A | 各不相同 |

按 arm 展开后，P 为 11 pass + 1 次传输删失，R0 为 10 pass + 2 次获取失败，R1 为 9 pass +
3 次获取失败。但独立实验单位仍然只有 4 个项目，而不是 12 个 arm-project cell 或展开后的 36
次重放。每个最终 arm-project 工件都至少通过两次，因此 P 没有独占的工件级成功。

21 次 pre-update 物理重放中有 18 次 Python 版本不匹配、3 次依赖获取失败；30 次 final 物理
重放中有 25 次通过、4 次依赖获取失败和 1 次传输删失。pre 到 final 的主要变化，是 D2 程序改用
了目标 Python 版本，不能把它当成新型记忆机制的证据。

## 轨迹说明了什么

观察到的可靠性差异有可操作但尚未因果确认的解释：position 17 的 P 在 pip 外面增加了 shell
重试；position 22 的 P 使用 `venv`，R0/R1 使用更依赖网络的 Conda 创建步骤。但 position 23
中，依赖选择更精简的 R0 才是唯一 3/3 的程序。不同时间段的网络波动仍是另一种合理解释。

所以 M1b 支持“保存并重放可执行部署程序”，并保留“重试与环境路径选择”这个操作层研究机会；
它没有证明显式结构化状态造成了差异。历史 R1 还有 3 个位置未能把 D2 持久化到状态文件，本实验
只能以研究者找回的 submitted script 为准，程序工件能力必须和端到端方法能力分开报告。

position 23 的 P 第二轮保留原始 fail，但判为传输删失：bootstrap exit 255、没有程序级终止错误，
且终止僵住的 SSH 客户端前，远端已不存在对应重放进程。该 trial 没有重试，也没有替换。

## 成本账

共享的历史 D0 首次部署一共使用 6,169,633 input tokens、38,505 output tokens 和 4,718.1 秒
Agent generation。它是各 arm 共享的历史成本，不是免费成本。

| D2 arm | Input | Uncached input | Output | Agent generation（秒） |
|---|---:|---:|---:|---:|
| P | 3,881,243 | 303,003 | 26,059 | 3,699.7 |
| R0 | 2,040,710 | 238,854 | 16,234 | 2,882.9 |
| R1 | 6,704,631 | 451,063 | 14,583 | 2,261.6 |

M1b 本身使用 0 模型 token；51 次重放共计 9,356.8 秒，其中包含 1,566.5 秒的传输删失。
仅看通过 trial，P、R0、R1 的重放时间中位数分别是 183.5、177.4、150.8 秒。这些数字只能描述，
因为各程序安装的依赖范围不同，而且多次运行由网络传输主导。

此前 4 次无效工程尝试继续单列计费，其中 3 次已知 wall time 合计 1,330.7 秒；两次被中断的
Agent 尝试无法恢复 token 用量。没有虚构未来修复 token，也没有计算没有实测依据的回本次数。

## 阶段裁决

裁决：保留“可执行程序工件 + clean replay”假设，也保留操作层可靠性机会；不把当前 P 或显式
持久状态升级为 EnvSolve-Pro 核心算法。

目前最强的简单解释是：强 Agent 写出了适配目标条件的可用程序，普通程序复用保存了成果。P 的
额外 D2 成本没有换来独占成功、明确的执行时间优势，也没有证明其状态表示是原因。

下一项信息量最高的核心实验，应在固定的真实 Dev bad case 上做严格匹配：强 Agent、连续 session、
prompt、工具、触发条件和资源报告完全相同，唯一 treatment 是把“完整程序在干净环境中的重放反馈”
返回同一 session。主指标只看最终 EnvBench Official 成功。结构化状态、checkpoint、假设搜索和
最小化继续作为后续正交 treatment。本报告不会自行启动下一批实验。

## 证据位置

- 固定计划：`experiments/schedules/envsolve_pro_m1b_artifact_replay_v1.json`
- 聚合结果：`experiments/analyses/envsolve_pro_m1b_artifact_replay_result_20260911.json`
- 传输删失审计：`experiments/validations/envsolve_pro_m1b_position23_transport_censor_20260911.json`
- 原始运行：`runs/envsolve-pro-m1b-artifact-replay-v1/`

