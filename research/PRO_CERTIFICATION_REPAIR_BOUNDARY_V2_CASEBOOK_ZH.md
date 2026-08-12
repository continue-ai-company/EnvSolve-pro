# EnvSolve-Pro Certification-Repair Boundary v2 高价值 Case 记录

本文档记录冻结 Dev-8 批次中的高价值机制现象。它不能替代最终配对分析，也不能用单个 case 驱动算法修改。

## Case 1：`astropy/reproject`

**冻结结果：** A（强 Agent 对照）通过官方 EnvBench；B（一次证书）通过；C（可重试干净重放）的第一次内层干净重放通过，但官方评测经历一次超时和两次独立的包下载完整性失败，最终保持基础设施 Unknown。

| 实验臂 | 官方状态 | 命令数 | 输入 token | 干净重放 |
| --- | --- | ---: | ---: | ---: |
| A | Pass | 25 | 603,274 | 0 |
| B | Pass | 8 | 224,180 | 1（首次通过） |
| C | Unknown | 22 | 656,309 | 1（首次通过） |

A 和 B 都有 272 个不计分的其他 Pyright error，但官方缺失导入数为 0。这验证了 harness 严格遵循 EnvBench 官方目标，没有优化无关诊断。

### 机制观察

1. A 只根据普通 shell 反馈也能恢复：它在构建容器内部创建新 venv、禁用 pip 本地缓存，并验证缺失导入为 0。但该 venv 仍共享已经编译过的源码目录，不等同于全新 checkout。
2. B 在安装项目全部 extras 后发现还缺 `pytest-astropy-header`，补齐后第一次独立干净重放通过。就这个 case 而言，证书没有改变相对 A 的二元成功结果。
3. C 的第一次干净重放同样通过。因此可重试循环没有被激活：没有失败证书，也没有由反馈驱动的修复。
4. B 在这条轨迹中使用的命令和 token 少于 A、C，但源码缓存和网络条件并不完全一致。在整个配对批次完成前，这些资源数据只作描述。
5. 只有当 pip 在 Pyright 运行前报告“无法归属的下载文件与包索引 SHA-256 不一致”时，才判为基础设施问题；用户自己写错具名 requirement 哈希仍算部署失败。

**决策：** boundary v2 和三个算法继续冻结，进入下一个预注册 case。

机器可读证据：`experiments/validations/pro_certification_repair_boundary_v2_dev8_block1_result.json`。

## Case 2：`cda-tum/mqt-bench`

**冻结结果：** A 和有效的 B 替代运行通过官方 EnvBench。C 的第一次内层干净重放通过，但同一提交脚本随后在官方评测中失败：pip 回溯 `pytket` 版本时无法解析 `types-pkg-resources`。

| 实验臂 | 官方状态 | 命令数 | 输入 token | 干净重放 |
| --- | --- | ---: | ---: | ---: |
| A | Pass | 9 | 224,699 | 0 |
| B | Pass | 10 | 269,993 | 1（首次通过） |
| C | Fail | 12 | 434,501 | 1（首次通过） |

A 和 B 的官方缺失导入数都是 0，另有 114 个不计分的 Pyright error。C 的 bootstrap 在 Pyright 之前退出，因此没有可比的非计分 error 数。

### 机制观察

1. A 只使用构建容器内的普通反馈，就选定了 Python 3.12、安装项目开发依赖并将缺失导入降为 0。它没有干净重放 API，但后续官方执行仍然通过。
2. B 将初始 162 个缺失导入降为 0，提交了四行环境程序，并同时通过一次全新重放和官方评测。这个 case 中，证书仍未相对 A 提升二元成功率。
3. C 的唯一一次全新重放也通过，所以可重试循环没有被激活。失败发生在 Agent session 结束后的官方评测中，内层重试接口无法看到并修复它。
4. C 的内层证书与官方执行使用相同源码 revision 和镜像，却得到不同的依赖解析结果。对未锁定依赖的部署程序而言，一次成功重放只能证明“当时能执行”，不能证明“可重复执行”。
5. 第一次 B 进程只完成 6 次只读调用，之后至少 2,058 秒没有语义进展；当时没有候选脚本、重放或官方结果，因此按冻结修正案 censor，并从空白 Agent session 运行一次替代。有效替代通过，原停滞运行不进入成功率、token 和时间分母。
6. 本轨迹中 B 的输入 token 比 A 多 20%，C 比 B 多 61%。由于有效 B 是预注册后置替代，这些资源数只作描述，不能解释为 treatment effect。

**决策：** Dev-8 算法继续冻结并收集后续 case；把“重复认证”或“稳定依赖解析”保留为批次结束后的正交 treatment，不针对这个 case 打补丁。

机器可读证据：`experiments/validations/pro_certification_repair_boundary_v2_dev8_block2_cli147_result.json` 和 `experiments/validations/pro_certification_repair_boundary_v2_dev8_block2_cli147_adjudication.json`。

## Case 3：`valory-xyz/trader`（仅用于边界校准）

**统计决定：** 该 case 不进入 A/B/C 效果估计。三组都找到了项目原生的 `autonomy packages sync`，并把 241 个缺失导入降为 0；但 boundary v2 把包管理器按仓库锁文件生成的 299 个 Python 文件当成违规。C 又通过临时创建并删除 `setup.py` 隐藏了操作历史，使旧边界错误地奖励了不可接纳路径。

boundary v3 因此只修测量对象，不修改三个 Agent 接口：

1. 审计最终提交程序在全新环境中产生的状态，而不是构建容器里的探索残留；
2. 临时创建受保护的构建、依赖或 verifier 配置，即使随后删除，也直接拒绝；
3. 只有仓库明确声明、锁文件与指定 revision 一致、且包管理器自身校验通过的生成依赖可以接纳；
4. 标准 `virtualenv` 启动文件必须匹配候选执行前记录的发行版模板哈希和版本；
5. A 的资格重放发生在 session 结束后，结果不返回 Agent；B/C 仍分别保持一次和可重试的 Agent 可见重放。

### 资格结果

- A 的原始程序在 Linux ARM Spark 上通过：官方缺失导入为 0，299 个包文件通过 `packages.json` 校验，标准 `virtualenv` 文件通过内容来源检查。
- B 的原始程序在修复前一版 v3 中完整通过；最终版的重复执行两次都在可信目标前被 PyPI 网络删失。最终新增的 Git 挂载修复已由 A 的完整执行和独立 Linux ARM 挂载测试覆盖。
- C 的原始第四版程序在执行前被拒绝，命中 `cat > setup.py`。
- 完整测试为 735 passed、8 skipped，另有 76 个 subtests passed。

**决策：** 冻结 boundary v3。前三个已暴露仓库只作 pilot 和边界校准；从原 outcome-blind 顺序中保留尚未执行的 5 个仓库，重新运行 15 条 A/B/C episode。此后只有完成全部有效 episode 和聚合错误分析，才允许改算法。

机器可读证据：`experiments/protocols/envsolve_pro_certification_repair_boundary_v3_implementation_freeze.json` 与 `experiments/validations/pro_certification_repair_boundary_v3_untouched5_preregistration.json`。

## Case 4：`pypa/distutils`（仅用于构建 provenance 校准）

**统计决定：** 在 B 臂开始前停止 Untouched Dev-5 的第一个 block，并把该仓库排除在所有方法效果估计
之外。C 和 A 都通过 Official evaluator，但 boundary v3 接受了 C 在 `/tmp` 中由 tracked source
编译的原生扩展，却拒绝 A 在仓库 `build_output` 中的等价扩展；它还拒绝 A 的标准 build 命令产生的
106 个 Python 源码精确副本。

预注册的 native-only boundary v4 正确接纳了原生扩展，但 106 个源码副本仍被拒，因此校准失败。该
版本作为失败结果保留，没有原地补丁。Boundary v5 随后引入一个与仓库无关的统一规则：Python 副本
必须与提交内容完全一致，并保留提交源码路径后缀；原生扩展必须对应提交原生源码声明的同名模块
provider。被修改、改名、直接生成或没有源码来源的 artifact 仍然无效。

A 与 C 的精确程序分别在全新容器中重放，没有调用模型或 Official evaluator。A 以 106 个提交源码
副本和 1 个仓库内原生 artifact 通过；C 以 1 个外部原生 artifact 通过。两者 missing imports、新增
unowned import artifact 和剩余仓库 violation 都为 0。Mac 全量回归通过 759 个测试；Spark Linux ARM
在源码 hash 一致时通过全部 24 个 v4/v5 focused test。

**决策：** 将 boundary v5 冻结为共享测量基础设施。A/B/C 只能在 boundary-v3 schedule 的 case
positions 2-5 共 4 个尚未打开仓库上恢复，对应 episode positions 4-15。该 case 只验证边界，不支持
“可重试 replay 优于任一对照”的结论。

机器可读证据：
`experiments/validations/pro_certification_repair_boundary_v5_distutils_consumed_calibration_adjudication.json`
与
`experiments/protocols/envsolve_pro_certification_repair_boundary_v5_implementation_freeze.json`。
