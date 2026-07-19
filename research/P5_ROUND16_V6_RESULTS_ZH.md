# P5 Round 16 V6 结果

Round 16 按未改动的预注册 V6 合约执行，生成了全部 10 个 required raw replay artifact
与 9 个完整 snapshot。Inflect、Reticulum、pytest-xdist 和 Poetry 的两次 snapshot 哈希
分别完全一致，因此结果为 4/5 V6 Pass、0/5 V6 Fail、1/5 V6 Unknown。四个完整 pair 在
Python runtime、marker environment、完整 installed-distribution 多重集和内容寻址项目
metadata/provenance 上都没有任何 delta。

Gpkit replay A 在采集 snapshot 前下载 `plotly` 时遇到 `files.pythonhosted.org` read timeout；
replay B 成功形成包含 74 个 installed distribution 的完整 snapshot。这个缺失 pair 被分类为
基础设施阻塞并保持 Unknown：它不是状态漂移证据，单个成功 replay 也不能提升为 Pass。
Round 16 的 frozen contract 不允许 conditional retry，因此再次本地执行会构成新实验，而
不是补全本轮。

独立审计重算了预注册与实现哈希、全部 10 个 raw result 哈希和 9 个 snapshot 哈希，并复核
精确 source identity/cleanliness、host 与 container 断网、container ID 独立性及全部 5 个
聚合判定；所有检查均通过。本轮没有模型或 official verifier 调用，也未查看 held-out case。

机器可读分析位于 `experiments/validations/p5_round16_v6_dev5_analysis.json`。P5 是否冻结
必须依据预注册退出条件判断，不能通过把剩余 infrastructure Unknown 调成开发集 Pass 来决定。

## P5 冻结判定

后续只读 freeze audit 从冻结 artifact 重建了完整 Dev-5 pass curve。V0/V1/V2/V3/V4/V5/V6
的 Pass 数依次为 5/4/2/5/5/0；V1 与 V6 各保留一个 Unknown，V5 保持 not measured。
Official Pass 与 Robust Pass 均为 2/5。四个精确 clean replay 覆盖三个 PEP 610 项目和一个
legacy egg-link 项目。

这满足既定 P5 退出条件：benchmark 与 robust 语义分离且 fail closed，榜单单指标的局限可见，
并且 clean replay 在 modern 与 legacy provenance 下均成立。P5 在不提升两个 infrastructure
Unknown 的前提下冻结。dependency cache 仍是服务器批跑可靠性任务，但不应成为继续针对
Dev-5 调 verifier 的理由。
