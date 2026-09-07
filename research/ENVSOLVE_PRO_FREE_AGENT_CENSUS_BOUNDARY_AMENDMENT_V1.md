# Free-Agent Census Boundary Amendment v1 / 自由 Agent 普查边界修订 v1

Status: approved before implementation on 2026-09-07. This amendment applies from
fixed position 3 onward. Positions 1 and 2 are not rerun or retrospectively promoted.

状态：2026-09-07 在实现前获批。本修订从固定位置 3 起适用。位置 1 和 2 不重跑，
也不在事后升级为成功。

## 中文

### 原规则与误杀

`open-candidate-program-v6` 保留了旧规则：只要候选程序直接写入名为
`setup.py`、`pyproject.toml`、requirements 等配置文件，就在执行前拒绝，以防程序
临时修改项目或 verifier 配置后再删除，从而逃过终态 Git 审计。

固定位置 2 `django-lfs` 的候选先令
`legacy_compat_source=$(mktemp -d)`，再在
`$legacy_compat_source/setup.py` 中定义一个安装到虚拟环境的兼容包。该包包含可执行的
`hotshot` 和 `cStringIO` 运行时实现，并在独立干净环境中执行过导入及基本行为检查。
字符串级规则只看到了文件名 `setup.py`，没有识别目标位于项目之外的临时目录，因而在
Official 运行前误杀。该判断不依赖任何 Official 结果：位置 2 没有调用 Official。

### 唯一改动

候选静态验证器只新增一种豁免：当 shell 变量在此前被直接赋值为 `mktemp -d` 的结果，
且配置写入目标明确以该变量为路径根时，不再把它当作项目配置写入。此豁免只允许候选
进入原有的干净执行、终态审计和安装产物审计，不自动证明兼容包合法。

仍然禁止：

- 写入项目或目标工作区内的构建、依赖、类型检查或 verifier 配置，即使随后删除；
- 把变量重新指向项目后利用豁免写入；
- 在项目或目标环境中制造空模块、纯静态类型 stub、符号链接别名或其他伪 provider；
- 修改 evaluator、隐藏终局验证，或读取/反馈 episode 后 Official 结果。

回归测试必须证明：外部临时目录中的功能性兼容包可通过候选静态验证；项目内配置写入、
变量重绑定后的写入和位置 1 式纯 `.pyi` provider 仍被拒绝或在既有 postepisode
合法性审计中判为不合格。

### 结果口径

位置 2 固定记为 `boundary-censored` 并留在 24 个位置的总分母中。修订前的位置 1/2 与
修订后的位置 3--24 不宣称为完全相同协议。若能在不继续已终止 Agent 轨迹的情况下用
新规则离线重判旧提交，只能另报敏感性分析，不能改写主结果。

## English

### Original Rule And False Positive

`open-candidate-program-v6` retained a temporal safeguard that rejected any direct
write to a file named `setup.py`, `pyproject.toml`, requirements, or related
configuration. Its purpose was to stop a candidate from changing project or verifier
configuration and deleting the change before terminal Git inspection.

At fixed position 2, `django-lfs`, the candidate assigned
`legacy_compat_source=$(mktemp -d)` and wrote
`$legacy_compat_source/setup.py` to package functional `hotshot` and `cStringIO`
runtime compatibility implementations for installation into the virtual environment.
It exercised imports and basic behavior in an independent clean environment. The
string-level rule saw only `setup.py`, treated it as a repository write, and rejected
the candidate before Official execution. This diagnosis uses no Official outcome;
Official was never invoked for position 2.

### Sole Change

Static candidate validation gains one exemption: when a shell variable was directly
assigned the result of `mktemp -d` earlier in the script and a configuration target is
explicitly rooted at that variable, the write is not classified as a repository
configuration write. The exemption only admits the candidate to the existing clean
execution, terminal repository audit, and installed-artifact audit. It does not certify
the compatibility package.

The following remain prohibited:

- writes to build, dependency, type-checker, or verifier configuration in the project
  or target workspace, even if later deleted;
- writes after the temporary-root variable is rebound to a project path;
- empty modules, type-only stubs, symlink aliases, or other fake providers in the
  project or target environment;
- evaluator modification, verifier suppression, or online disclosure of postepisode
  Official results.

Regression tests must admit a functional compatibility package built under an external
temporary root while rejecting repository configuration writes, writes after variable
rebinding, and the position-1 pattern of a type-only provider either statically or in
the existing postepisode admissibility audit.

### Reporting

Position 2 remains `boundary-censored` in the denominator of 24. Positions 1--2 and
positions 3--24 are not presented as an identical protocol. An offline application of
the revised rule to an old submission may be reported only as a sensitivity analysis;
it cannot restore the prematurely terminated Agent trajectory or alter the primary
record.
