# EnvSolve-Pro Stateful Agent V2.1：已消费 Case 机制实验结果

## 范围

这是在 `bradenm/micropy-cli@ac85e9f` 上进行的已消费开发集机制实验，
不能作为 held-out 泛化效果证据。

## 结果

- EnvBench 官方结果：**Pass**
- 官方 `reportMissingImports`：**0**
- 不计分的 Pyright error：**311**
- 模型轮数：**2**
- 模型候选：**2**，另有一次共享初始观测
- 容器命令：**71**
- 总耗时：**1,446.8 秒**
- Token：输入 3,670,827，其中缓存 3,459,072；输出 41,474

初始观测返回 70 条 active finding。约束层没有丢失原始反馈，将其压缩为
24 个完整的 obligation group，unknown 和 omission 都为 0。

## 状态转移

候选 1 安装项目和依赖后，尝试生成一个很小的 `micropy` stub 包。操作层在
执行目标前拒绝了它，因为程序直接生成了可导入文件。

第 2 轮拿到了完整的被拒脚本、具体违规行和目标路径。候选 2 不再生成 Python
源码或 stub，而是通过临时 setuptools 元数据，将当前 checkout 中的
`micropy/app` 映射为遗留导入路径 `micropy.cli`。它在新的精确 revision
环境中依次通过公开目标、仓库审计、V2 源码来源审计和 EnvBench 官方评测。

## 机制结论

观测角色分离、操作前观测、操作前约束三个检查均通过。实验真实触发了一次
“拒绝到修复”的状态转移，但预注册中的 divergent-source rejection 本身没有
被触发。

因此，这次运行是有效的机制证据，也是有效的官方榜单结果；但暂时不能作为
严格 integrity-qualified 的效果证据。

## 新发现的定义缺口

V2.1 能审计源码内容，也能拒绝直接生成可导入文件；但 setuptools 的
`package_dir` 元数据仍可把当前 checkout 中的源码赋予一个新的模块身份。
本 case 的 revision 中不存在 `micropy.cli`，候选却把 `micropy.app` 映射成了
这个名字。

这不影响 EnvBench 的 Official Pass，因为官方只计
`reportMissingImports`，其余 311 个错误不计分。但它说明“源码来源一致”和
“模块身份一致”是两个不同的约束。

下一步只增加一条最小规则并先做 canary：

> 项目命名空间中的源码可以按仓库声明的模块身份安装或复制，但不能通过包
> 元数据、链接、loader 或路径映射获得一个仓库未声明的新导入身份。

在冻结 repository-disjoint Dev 实验之前，必须先验证这条规则。
