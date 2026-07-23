# 跨方法轨迹普查基础设施修订 v1

Repo2Run 第一次 canary 因 Spark 主机缺少虚拟环境而未能启动。按声明依赖在
Python 3.12 下补齐环境后，第二次 canary 仍在 Agent 启动前失败：未锁定版本的
`pipdeptree` 在 ARM64 上解析到 4.1.0，构建 baseline 镜像时要求当前镜像中没有的
Rust 工具链。

因此我们将 `pipdeptree` 锁定为此前已通过 Repo2Run 环境预检的 2.28.0，并覆盖
静态模板和全部动态镜像生成路径。第一次锁定只覆盖了未被实际执行的静态模板，该次
截断也完整保留。这是与仓库和 case 无关的执行兼容修复，不改变 Repo2Run 的 prompt、
模型循环、操作生成、evaluator 或可见信息。有效的 Repo2Run 普查从带
`infra-retry3` 后缀的 canary 开始。
