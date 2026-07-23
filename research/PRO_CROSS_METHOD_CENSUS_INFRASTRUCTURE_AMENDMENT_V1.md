# Cross-Method Census Infrastructure Amendment v1

The first Repo2Run canary did not start because its Spark host virtual environment
was absent. After the declared requirements were installed under Python 3.12, the
second canary still failed before the agent started: an unpinned `pipdeptree`
installation resolved to version 4.1.0 on ARM64 and required unavailable Rust
tooling while building the baseline image.

We therefore pin `pipdeptree==2.28.0`, the version already present in the previously
qualified Repo2Run environment, in every static and generated image-construction
path. The first pin covered only the unused static template; that censored attempt
is also retained. This is a repository-independent execution repair. It does not
change Repo2Run's prompt, model loop, generated operations, evaluator, or access to
case information.

The next canary entered the native agent loop, then stopped because an `addfile`
operation invoked a hard-coded `sudo chown` for the original developer account.
The copied file is already host-readable, so the host-specific ownership rewrite is
removed. The interrupted attempt remains retained. The valid Repo2Run census begins
with the next canary.

That canary completed the native agent loop, but `waitinglist addfile` copied dependency
files from the container into the source checkout solely so the host parser could read
them. The external integrity gate correctly rejected the dirty checkout, although the
files were baseline-tool side effects rather than model-authored source changes. Addfile
exports now use an auto-removed temporary directory. The valid Conan canary begins with
`infra-retry5`; the already valid Jaraco episode is retained.

The next Conan attempt reached the model loop without provider errors, but Repo2Run's
original `max_tokens=1024` completion window was exhausted by the reasoning model.
OpenRouter returned a successful choice with null message content, and the baseline
then dereferenced that null value. We raise only the per-response completion window
to 8192 tokens. This is a model-adapter compatibility repair: total token use remains
a reported metric rather than a success gate, while Repo2Run's prompt, loop, command
parser, and evaluator remain unchanged. Attempts ending in null content are retained
as censored and retried. Completed episodes that did not exhaust the old window remain
valid; the valid Conan canary begins with `infra-retry6`.
