# EnvSolve-Pro P3 候选保留机制结果

状态：已完成 consumed Dev 资格实验；这不是 held-out 效果结论。

## 决策

Best-admissible candidate retention 通过了两个预注册门槛：

- 开启保留时进入官方终态：`2/3`；
- 关闭保留时进入官方终态：`1/3`；
- 终态覆盖净增：`+1`。

因此，该机制可以不做 case-specific 修改，进入未见样本评测。但它尚未证明 Official Pass 有提升：
两组都通过 `1/3`。

## 机制实际做了什么

在 `roboflow/supervision` 上，无保留对照耗尽 5 个候选后没有输出环境。保留组的第 2 个候选完成了
零退出执行，repository-effect audit 有效，Unknown 为 0，但仍有 22 个残余约束。后续候选失败或超时，
冻结排序器因此释放第 2 个候选，并明确标记为 `uncertified`，内部 goal 仍保持 `blocked`。

随后 EnvBench 独立完成评测。Bootstrap 退出码为 0，但仍有 22 个官方 issues，其中包括 8 个未解析
import module，因此 Official Pass 为 false。候选保留修正了“没有终态”的截断问题，没有解决剩余依赖闭包。

## 科学解释

该结果支持一个窄而清晰的机制结论：当内部 verifier 不完备时，不应在预算耗尽时抹掉一个可执行、
可审计的环境。它不支持成功率提升结论。下一步应先判断剩余错误主要来自操作不可行、约束闭包，还是
内部 verifier 与官方成功条件之间的覆盖差异。Spark 上预注册的 8-case 轨迹普查会在下一次算法修改前
估计这个分布。

## 审计

六个有效位置全部通过 artifact integrity 和 scientific eligibility 审计。第 6 位置因人工搬动电脑而从
全新 run root 重跑；两次 launcher preflight 失败和一次 Docker 基础设施失败均已归档并排除。有效尝试
仍使用冻结实现，没有接收先前尝试的反馈，并保留了完整恢复 provenance。
