# EnvSolve-pro DGX Spark 兼容性报告 V1

## 范围

本轮检查 EnvSolve-pro 冻结快照能否在 DGX Spark 上执行，以便后续并行开展 P0 实验。它不用于证明模型效果，也没有查看 EnvBench held-out 结果。

- 源码版本：`3eef2fdf73a06d1dd5fc3f8860b2b73b7fc98614`
- 主机：NVIDIA DGX Spark 7.3.1、Ubuntu 24.04.3、`aarch64`
- 加速器：NVIDIA GB10，驱动 580.95.05
- 运行时：Docker 28.5.1、Python 3.13
- EnvBench 镜像：本机已有 ARM64 版本

## 发现

首次完整测试为 418 个通过、5 个失败、2 个跳过。Mac 上原样复现了这 5 个失败，因此它们不是 Spark 或 ARM64 回归：

1. 一个 P5 测试依赖被忽略、未提交的历史 run 原始产物来重建冻结结果。
2. 一个 P6 测试用历史冻结清单审计持续演进的 EnvSolve-pro 当前工作树。
3. 三个 V0 测试把解释器路径写死为仓库内的 `EnvBench/.venv/bin/python`。

排除这三个测试模块后，可移植核心测试为 417 个通过、2 个跳过、75 个子测试通过。Docker 能启动完全相同的 EnvBench 镜像，启用 NVIDIA 的容器也能识别 GB10。

## 可移植性修复

测试现改用当前受控解释器；P5 从已提交证据审计；P6 回到不可变冻结版本审计，而不要求当前源码停留在旧版本。`requirements-test.txt` 固定了跨主机复现所需的测试依赖。这些修复不改变观测层、约束层、操作层、验证器或模型策略。

固定上述依赖，并把 EnvBench 专属 import 延迟到真实 V0 episode 启动后，两台主机的完整结果已经一致：
424 个通过、2 个跳过、75 个子测试通过。两个跳过项都是原有的可选测试，不是架构相关失败。

## 剩余边界

当前已经验证源码、Python、Docker、ARM64 与 GPU 容器兼容性。仍需在 Spark 上完成一个真实 episode，才能验证同一冻结 P0 协议下的模型访问、仓库获取、候选执行和官方评测全链路。
