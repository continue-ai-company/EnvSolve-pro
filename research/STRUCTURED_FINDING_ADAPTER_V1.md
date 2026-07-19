# Structured Finding Adapter v1

Status: synthetic-qualified adapter contract; no real case has been executed.

The adapter is the only bridge from verifier-owned findings to solver-owned
counterexample evidence. It accepts typed findings over the existing runtime,
package, capability, module, and platform domains. Active findings must provide a
required and observed value and become a requirement/observation evidence pair.
Inactive findings are retained in verification metadata but do not become repair
constraints. Any unknown finding, incomplete verifier, or upstream infrastructure
error makes the complete result Unknown and emits no counterexample.

The adapter does not parse logs, repository names, Pyright text, package indexes, or
benchmark-specific result files. Collectors remain responsible for provenance and
for classifying raw diagnostics into active, inactive, or unknown typed findings.
Unsupported predicate/domain combinations fail closed. A deterministic bootstrap
failure without a structured finding remains failed but unnormalizable, so the core
loop blocks instead of inventing a repair signal.

The contract is covered by eight focused tests, including an end-to-end two-round
feedback cycle with the v2 core. Real collector adapters require their own freeze.
