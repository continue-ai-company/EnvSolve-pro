# 跨方法轨迹普查基础设施修订 v1

Repo2Run 第一次 canary 因 Spark 主机缺少虚拟环境而未能启动。按声明依赖在
Python 3.12 下补齐环境后，第二次 canary 仍在 Agent 启动前失败：未锁定版本的
`pipdeptree` 在 ARM64 上解析到 4.1.0，构建 baseline 镜像时要求当前镜像中没有的
Rust 工具链。

因此我们将 `pipdeptree` 锁定为此前已通过 Repo2Run 环境预检的 2.28.0。这是与
仓库和 case 无关的执行兼容修复，不改变 Repo2Run 的 prompt、模型循环、操作生成、
evaluator 或可见信息。两次被基础设施截断的尝试均完整保留；有效的 Repo2Run 普查
从带 `infra-retry2` 后缀的 canary 开始。
