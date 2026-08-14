# EnvSolve-Pro V2：DeepSeek V4 Flash 0731 资格结果

状态：在一个已消费开发 case 上通过资格检查；不属于效果证据。

## 决策

后续 API 实验统一使用固定模型 ID `deepseek/deepseek-v4-flash-0731` 和冻结的 Cloudflare provider，
不使用会漂移的 `flash-latest`。此前 V4 Pro Dev-12 只保留为历史 pilot，不与 Flash 结果合并统计。

## 证据

API 目录显示该模型支持所需 reasoning 与 tool 参数，合成 canary 也正确返回指定函数调用。完整 B-FSR
资格运行随后连续执行 53 次模型请求和 49 次构建 shell 调用，没有 provider error。clean replay 在请求
35 和 50 拒绝了不可重放程序；同一 session 修复完整程序后，在请求 52 通过 replay，并在请求 53
提交完全相同的认证 hash。该脚本最终以 `issues_count=0` 通过 Official evaluator。

源运行的第一次 Official 只是宿主启动 preflight：detached `PATH` 找不到 `uv`，evaluator 并未执行。
预注册的 exact-script retry 只把 Spark 已存在的 `.venv/bin` 加入宿主 `PATH`，没有重跑模型或修改脚本。

## 资源信号

在同一个已消费 `mov-cli` case 上，Flash B 使用 53 requests、1,153,483 tokens 和约 649 秒；此前
Pro B 使用 15 requests、158,559 tokens 和约 172 秒。Flash token 是 Pro 的 7.27 倍，但 provider
报告的美元成本低 66.7%。单个 case 不能给模型排序，但它说明 token、时间、美元成本和成功率必须分开
报告。

## 边界

本资格实验只支持模型接口兼容、反馈驱动修复和一次 Official 成功，不支持“Flash 比 Pro 更准确或更
高效”。下一批效果实验必须在执行前冻结，并在相同 Flash 快照上成对比较 A 与 B。
