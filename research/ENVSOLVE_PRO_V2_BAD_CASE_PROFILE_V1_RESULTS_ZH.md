# EnvSolve-Pro V2 已消费 Bad Case 画像

状态：机制诊断已完成，2026-08-20

## 问题

在同一个 DeepSeek V4 Flash 自由 Agent 上增加“同 session 干净重放”，究竟能否修复当前部署失败，还是
历史错误主要来自旧 harness？

这是 6 个已消费开发 case、每个 arm 仅一次实现的诊断实验。它不能支持效应量、泛化、榜单或 SOTA 结论。

## 结果

| 结果 | 数量 |
|---|---:|
| A-F Official Pass | 5/6 |
| B-FSR Official Pass | 4/6 |
| 仅 B 通过 | 1 |
| 仅 A 通过 | 2 |
| 两者都通过 | 3 |

旧 B-FSR 没有战胜自由搜索：它在 `basxconnect` 上获胜，在 `graphium` 和 `cvxportfolio` 上失败，其余
3 个 case 打平。

## 重放实际做了什么

重放触发了 3 次基于反馈的程序修改：

- `basxconnect`：重放发现最终脚本遗漏 Git `safe.directory`；同一 session 补上后，重放和 Official 都通过。
- `UER-Py`：重放发现 `torchcrf` 的导入名与分发包映射错误；程序从 `torchcrf` 改成 `pytorch-crf`，最终
  两个 arm 都通过 Official。
- `graphium`：重放先发现并修复 Git ownership，但随后给出了错误的 Pass。

第三个 case 暴露了决定性的 harness 缺陷。旧重放继承了构建阶段积累的包缓存，而 EnvBench Official 只
挂载仓库，不带构建缓存。Graphium 的通过重放有 41 行 `Using cached`，Official 为 0，并在依赖解析时
失败。`cvxportfolio` 也出现“重放通过、目标态失败”，但其 Official 的空 setuptools 候选集仍可能受网络
或索引波动影响，不能强行归因。

## 三层解释

- **观测层：**重放环境比最终交付环境更容易，Agent 得到了“可重现”的假证据。
- **约束层：**只要忠实失败能够被看见，Agent 通常可以推断缺失条件，例如 Git ownership 和 TorchCRF
  的包映射。
- **操作层：**有效循环很简单：在同一 session 修改完整程序，再从目标状态执行一次。

所以当前主要矛盾不是跨 case 包规则不够多，而是 Agent 判断方案可交付时，没有获得忠实的目标态反例。

## 资源观察

在 3 个双方都成功的 case 上，B 使用 123 次模型请求、179 万 token，A 使用 158 次请求、336 万 token。
这只是描述性结果：样本按双方成功筛选，而且每个 arm 只有一次。Graphium 也说明为什么成功率必须优先：
A 花费 90 次请求和 385 万 token，但它是唯一通过 Official 的方案。

## 决策

下一个最小 treatment 是**同 session 目标态反例重放**：

1. Agent 在一段连续 session 中自由构造完整部署程序。
2. harness 在与最终交付缓存语义一致的新环境中执行整个程序。
3. 第一个可执行失败和有界原始证据返回同一个 session。
4. Agent 修改完整程序并重复，直到目标态重放通过。

提交 `448de40` 已完成必要的测量修正：单次运行包缓存只用于构建，不进入干净重放。方法不增加包规则库、
定时观测、checkpoint 搜索、跨 case 记忆或新的硬操作约束。

这些已消费 case 只用于验证机制是否工作。任何有效性结论都必须来自另一个与结果无关、预先确定的
qualification batch。
