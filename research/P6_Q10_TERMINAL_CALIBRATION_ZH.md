# P6 Q10 终局校准

状态：在读取任何新的 Official evaluator 结果前完成预注册。

## 研究问题

Q10 的 50 个候选全部被 internal verifier 判为失败，且没有执行 Official evaluator。因此当前有两种
解释混在一起：一是部署操作本身不够好，二是 internal verifier 拒绝了 terminal objective 实际会
接受的脚本。在区分二者之前，继续修改 solver 无法归因。

## 冻结干预

对 10 条已关闭的 Q10 run，各自选择最后一个拥有 `verification_recorded` event 的 candidate。该规则
只读取 trajectory structure，并在任何新 Official outcome 之前执行；它会排除后来被共享 candidate
validation 或 operation guard 拒绝、从未真正进入 internal verification 的 proposal。

10 份脚本逐字节复制到 `experiments/scripts/p6_q10_terminal_calibration/`。Binding manifest 固定
source episode、candidate ID、event sequence、源路径、冻结路径和 SHA256；proposal、verification、
源文件与冻结副本的哈希必须一致。

所有冻结脚本按照 binding position 依次评测，每份只运行一次；EnvBench 源码提交、protocol、config
和 Docker image 均保持不变，每次使用 fresh environment。实验不调用模型，不做 generation retry、
replacement、overwrite 或 infrastructure retry。

## 结果定义

所有入选脚本的 internal 判断均为失败。因此，只要某次完整 Official evaluation 通过，就构成明确的
internal-verifier false negative。Official evaluation 完成但失败，表示二者在 Boolean 层面对齐，
具体诊断差异只做描述。Evaluator 基础设施失败记为 `Unknown`，既不重试也不替换。

若出现 false negative，下一项修改必须先构造通用 synthetic counterexample，再对 verifier 做最小
scope correction，之后才能修改 solver search。若全部完成的 Official evaluation 都失败，则本次
校准没有提供放松 verifier 的证据，研发主目标应转向 candidate feasibility 与 search efficiency。

## 声明边界

这是 episode 后的 development calibration，不是 Q10 重跑、效果估计或榜单结果。5 个 case identity
已经属于消耗过的 development data；结果不能触发 replacement，也不能改写原始 Q10 closure。
