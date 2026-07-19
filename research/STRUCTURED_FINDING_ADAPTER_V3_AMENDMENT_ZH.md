# Structured Finding Adapter v3 修订

状态：由已消费 development case 的只读资格验证触发；没有新 benchmark execution。

第一次只读 collector 资格验证表明，只保留 module 名会丢失选择 grounded repair 所需的
信息。同一 missing name 可能来自 runtime import、test、平台分支、guarded fallback 或
documentation file。若缺少 file、line、source identity 和 collector assessment，policy
可能把 Python 版本分支误当成普通 package obligation。

v3 不改变 v2 constraint 语义，只把 structured finding ID 与 provenance 同时附加到
requirement 和 observation evidence value。现有 normalizer 仍只读取相同的类型化
`name`/`present`、`specifier`/`version` 或 equality 字段；额外 provenance 保留在
constraint 引用的 evidence 中。没有新增 repository map 或 import-to-distribution 猜测。

本次修订只读使用一个已经消费的 development artifact，没有模型请求、benchmark 执行、
源码修改或 held-out 检查。泛化仍需新的冻结 development batch 验证。
