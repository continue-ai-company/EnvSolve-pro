# Cross-Method Census Infrastructure Amendment v1

The first Repo2Run canary did not start because its Spark host virtual environment
was absent. After the declared requirements were installed under Python 3.12, the
second canary still failed before the agent started: an unpinned `pipdeptree`
installation resolved to version 4.1.0 on ARM64 and required unavailable Rust
tooling while building the baseline image.

We therefore pin `pipdeptree==2.28.0`, the version already present in the previously
qualified Repo2Run environment. This is a repository-independent execution repair.
It does not change Repo2Run's prompt, model loop, generated operations, evaluator,
or access to case information. Both censored attempts remain retained. The valid
Repo2Run census begins with the `infra-retry2` canary.
