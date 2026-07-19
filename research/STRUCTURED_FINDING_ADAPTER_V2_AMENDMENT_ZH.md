# Structured Finding Adapter v2 修订

状态：在任何真实 case 执行前，对 Structured Finding Adapter v1 作出的合成审计修订。

v1 根据 bootstrap 成功且不存在 active finding 来推断目标成功，这混合了两个归属不同
组件的判定。verifier 可能因为某条 finding 判定目标失败，而 collector 认为该 finding
不应驱动环境 repair；忽略 repair evidence 不能把 verifier 的 Fail 改写为 Pass。

因此 v2 要求每个 structured report 显式携带 verifier 自己的三值 `goal_passed` 判定。
finding disposition 只控制是否产生类型化 repair evidence。Unknown finding、执行未完成和
基础设施错误仍具有最高优先级并产生 Unknown。若报告 Pass 同时携带 active counterexample，
adapter 保留该矛盾，让 core pass contract 将其阻断。

本次修订没有观察真实 repository、held-out case、模型响应或 benchmark outcome。v1 的
domain mapping 与其他 fail-closed 规则保持不变。
