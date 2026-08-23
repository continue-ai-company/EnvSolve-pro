# EnvSolve-Pro Certified-Incumbent 开发实验结果

状态：完整负结果，仅作为开发证据

## 问题

在连续 session 的 soft replay 基础上，加入 prompt 引导的提前程序化和 clean-replay-certified
incumbent，能否提高部署成功率？

原定 8 对调度保持不变并全部执行。实验过程中审计历史轨迹 registry，发现 Futaba 已经被使用过，
Flask-Security 的目标 revision 已无法从远端获取。因此主分析只包含 6 对 prospective case；Futaba
单列为描述性结果；Flask-Security 记源码获取删失。看到结果后没有补选 case。

## 结果

| Case | B-FSR | C-GCI |
| --- | --- | --- |
| mflowgen | Pass | Pass |
| bread | Pass | Pass |
| pajbot | Pass | Pass |
| qibolab | Pass | 部署失败 |
| mamonsu | Pass | Pass |
| qiita | Pass | Pass |

B-FSR 为 `6/6`，C-GCI 为 `5/6`。配对表是 5 对都通过、1 对仅 B 通过、0 对仅 C
通过、0 对都失败。双侧 exact McNemar 为 `p=1.0`。样本很小，不能估计总体效应，但足以否定
“C-GCI 是 B-FSR 的非退化改进”这一开发假设。

C 的资源也更差。6 对总计使用 271 对 196 次请求、9.40M 对 3.78M Token、7,547 对
5,887 秒生成时间。这个差异受 qibolab 失败影响，因此又比较 5 对共同成功 case：C 仍多用
21.4% Token、19.9% 生成时间和 12.1% 端到端时间。没有任何 C episode 使用 incumbent
fallback。

## 决定性失败

Qibolab 把问题精确定位到三层闭环：

- **观测层：** C 在第 93 次请求得到完整根目录的零 missing-import 结果。
- **约束层：** 这个已经验证的充分状态没有被转化成“先交付当前程序，再探索可选完整性”的持久义务。
- **操作层：** Agent 继续处理大范围依赖、硬件、stub 和 runtime 完整性，直到第 120 次请求仍没有
  提出完整程序。

Incumbent 无法救场，因为只有 clean replay 通过后才存在 incumbent，而 qibolab C 从未调用 replay。
因此“goal-triggered certified incumbent”这个名字高估了真实实现：goal trigger 只是 prompt 引导，
真正可执行的机制要等候选被提交后才开始。

## 决策

否决 bundled C-GCI 作为核心算法。Certified-incumbent fallback 只保留为正交安全原语；clean
target-state replay 继续保留，因为此前轨迹存在真实的 Fail-to-Pass 修复。

下一条最小假设是**验证器触发的程序化交接**。自由搜索阶段不变；可信完整目标一旦通过，控制器就在同一个
活跃 session 中进入“生成累计程序并重放”阶段，优先于可选完整性探索。重放失败时把精确反例返回自由
修复；重放通过则成功终止。这修的是三层之间的控制流，不是增加 package 规则或新的硬兼容边界。

本实验不支持 held-out、外部 baseline、强弱模型或 SOTA 结论。

机器可读结果：
`experiments/validations/envsolve_pro_v2_certified_incumbent_untouched8_v1_result.json`。
