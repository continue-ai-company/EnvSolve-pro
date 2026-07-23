# EnvSolve-pro 目标对齐诊断 v1

## 范围

本事后诊断只使用两组已消费的 P4 轨迹。16 个 case 中有 9 个同时包含最终保留候选
的内部验证与完整 Official evaluation；其余 7 个不进入模块集合比较。本结果不能
支持效果结论。

## 结果

最终候选的 static unresolved-module proxy 覆盖了 `40/41` 个官方
`reportMissingImports` 模块，recall 为 `97.6%`。同一批候选共有 70 个内部模块
义务，其中 30 个不对应官方缺失模块；25 个额外义务集中在 Conan Package Tools。
额外义务出现在 4 个仓库中，并且有 1 个 Official Pass 仍保留内部 unresolved
constraint。

## 解释

可分析子集不支持“大范围看不见计分缺失”的解释：内部 static proxy 通常能看到真正
计分的缺失模块。更值得检验的是 precision 假设：runtime import failure 和 resolver
差异可能把很小的计分前沿放大成大量非计分义务。但该现象高度集中在一个 case，尚不
能宣布为主要矛盾。冻结的跨方法轨迹普查必须先证明 objective dilution 在多个仓库中
反复成为最早决定性分歧，才允许修改 solver。
