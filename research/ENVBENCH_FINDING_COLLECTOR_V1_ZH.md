# EnvBench Finding Collector v1

状态：使用已消费 development case 完成 recorded qualification，尚未在 unseen batch
上准入。

collector 将一次 fresh EnvBench replay 转换为 structured verifier report。官方目标判定
严格保持 `exit_code == 0 && issues_count == 0`。bootstrap 成功但存在 missing-import issue
时，collector 把精确 Pyright `reportMissingImports` diagnostic 绑定到 revision-owned 源码，
并使用冻结的 P5 import-context analyzer 分类。所有可归因的官方 missing import 都保持
goal-active module requirement；P5 语义 disposition 单独保存在 provenance 中，用于 repair
risk 与 Robust-Pass 分析。源码无法读取、diagnostic 格式错误或计数不一致时返回 Unknown。

bootstrap 失败时，collector 复用现有通用 action-result normalizer，提取 Python version、
missing capability 和 missing module 证据对。已知网络特征产生 infrastructure Unknown。
其他确定性 bootstrap failure 保持 failed 但不可规范化，core loop 会阻断而不是发明 repair。

collector 不做 module-to-package 映射，不根据 repository identity 选择 repair，不修改源码，
不把非 missing-import Pyright error 当成环境义务，也不改变官方 scoring。7 个合成测试覆盖
identity、source provenance、diagnostic cardinality、guarded import、通用 bootstrap evidence
和网络删失。
