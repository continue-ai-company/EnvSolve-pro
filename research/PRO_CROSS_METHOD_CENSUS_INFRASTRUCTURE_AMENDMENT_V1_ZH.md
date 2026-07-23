# 跨方法轨迹普查基础设施修订 v1

Repo2Run 第一次 canary 因 Spark 主机缺少虚拟环境而未能启动。按声明依赖在
Python 3.12 下补齐环境后，第二次 canary 仍在 Agent 启动前失败：未锁定版本的
`pipdeptree` 在 ARM64 上解析到 4.1.0，构建 baseline 镜像时要求当前镜像中没有的
Rust 工具链。

因此我们将 `pipdeptree` 锁定为此前已通过 Repo2Run 环境预检的 2.28.0，并覆盖
静态模板和全部动态镜像生成路径。第一次锁定只覆盖了未被实际执行的静态模板，该次
截断也完整保留。这是与仓库和 case 无关的执行兼容修复，不改变 Repo2Run 的 prompt、
模型循环、操作生成、evaluator 或可见信息。

下一次 canary 已进入原生 Agent 循环，但 `addfile` 操作调用了绑定原开发者账户的
`sudo chown`，导致后台任务等待主机 TTY。复制出的文件本身可读，因此移除该主机
专属的所有权改写，并完整保留被中断的尝试。有效的 Repo2Run 普查改从带
下一次 canary 开始。

该 canary 完成了原生 Agent 循环，但 `waitinglist addfile` 为让主机 parser 读取
容器内依赖文件，把副本留在了源码 checkout。外部完整性 gate 因 dirty checkout
正确拒绝了它，但这些文件是 baseline 工具副作用，并非模型修改源码。现在 addfile
只导出到自动删除的临时目录。有效 Conan canary 从 `infra-retry5` 开始；已经有效的
Jaraco episode 保留。

下一次 Conan 尝试在没有 provider 错误的情况下进入了模型循环，但 Repo2Run 原有
的 `max_tokens=1024` 单次回答窗口被推理模型耗尽。OpenRouter 成功返回 choice，
但 message content 为 null，随后基线在解引用该值时崩溃。我们只把单次回答窗口
提高到 8192 tokens。这是模型适配兼容修复：总 token 消耗仍然只是报告指标而不是
成功门槛；Repo2Run 的 prompt、loop、命令解析器和 evaluator 均不改变。正文为空
而终止的尝试会完整保留并重跑；没有触及旧窗口且已完成的 episode 仍然有效。
有效 Conan canary 从 `infra-retry6` 开始。
