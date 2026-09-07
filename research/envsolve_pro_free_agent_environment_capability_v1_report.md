# Free-Agent Environment Capability / 自由 Agent 环境能力

Status: qualified on 2026-09-07. This is an experiment memo, not a paper draft.

## 中文

### 结论

强 Agent 对照现在拥有通用、可选的独立环境能力。Agent 可以创建原始 revision 和基础镜像的新容器，在其中运行任意命令或完整部署程序，读取原始结果，并自行关闭环境。工具不会自动执行程序、公开目标或 Official evaluator，也不会自动重试或修复。

Spark 和 AgentHub 的无模型后端探针均通过。AgentHub 首次暴露 Docker Desktop bind mount 不接受容器内 chmod 的兼容问题；修复仅复用了已有主机所有权语义，Linux 才 chmod，随后同一探针通过。

真实 Codex smoke 使用已消费的 pyperf case、`gpt-5.6-sol`、`xhigh` 和 Codex CLI `0.153.4`。普通任务 prompt 明确说明新环境可选、不要求 replay 证书。Agent 自主完成以下动作：

1. 在 construction 环境诊断和安装；一次慢下载触发命令超时后继续修复。
2. 自主创建一个 fresh environment。
3. 在 fresh environment 执行后来提交的完整程序；去掉 shebang 后字节完全相同。
4. 在同一 fresh environment 运行公开 Pyright 检查，44 个文件、0 个 `reportMissingImports`。
5. 读取反馈、主动关闭环境，然后在同一个 turn 内提交程序。

该 episode 没有调用 Official evaluator。episode 结束后的 advisory qualification 通过，但其输出没有返回 Agent。

### 科学含义

后续 A/B 不能把“是否有新容器能力”当作唯一因果差异。自由 Agent 已可自愿验证完整程序；未来 treatment 必须只增加自动把 target-state 完整程序失败返回同一活跃 session 的策略，并保留相同通用工具能力。

这项结果只证明能力真实存在，不证明 Agent 总会使用它，也不证明 voluntary replay 或 EnvSolve-Pro 提高 Official Pass@1。

## English

### Result

The strong-Agent control now has a generic, optional independent-environment capability. It may create a fresh container from the original revision and base image, execute arbitrary commands or a complete deployment program, inspect raw results, and close the environment. The tool does not automatically execute a program, invoke the public goal or Official evaluator, retry, or repair.

Model-free backend probes passed on Spark and AgentHub. The first AgentHub attempt exposed a Docker Desktop bind-mount chmod incompatibility. Reusing the existing host ownership semantic, so only Linux bind mounts are chmoded, fixed it; the same probe then passed.

An end-to-end Codex smoke used the consumed pyperf case, `gpt-5.6-sol`, `xhigh`, and Codex CLI `0.153.4`. The normal task prompt made fresh environments optional and required no replay certificate. The Agent voluntarily created a fresh environment, executed the exact body of its eventual submitted program, ran the public Pyright check there with 44 files and zero `reportMissingImports`, inspected the result, closed the environment, and submitted within the same turn. No Official evaluator ran online or during this generation-only episode.

### Scientific Consequence

Future A/B work cannot use mere access to a fresh container as the treatment. Both arms must retain this generic capability. The treatment may only add the policy that returns target-state complete-program failure to the same active session. This qualification proves capability, not usage prevalence or an Official Pass@1 benefit.
