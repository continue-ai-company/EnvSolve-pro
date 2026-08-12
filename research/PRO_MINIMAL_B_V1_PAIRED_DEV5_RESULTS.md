# EnvSolve-Pro Minimal B v1: Paired Dev-5 Result

## Scope

This is a frozen, repository-disjoint **development** comparison of one continuous
`gpt-5.5` Agent with and without callable clean replay. It is mechanism evidence only.
It is not held-out, leaderboard, or statistical confirmation.

The preregistered primary outcome is paired Official Pass@1. A run scores one only when
it reaches an Official Pass. Four pre-Agent interruptions or acquisition failures were
replaced under written amendments; their artifacts remain excluded and auditable.

## Primary Result

| Repository | Minimal B | Strong Agent control | Pair outcome |
| --- | ---: | ---: | --- |
| `pymanopt/pymanopt` | Pass | Pass | both pass |
| `datactive/bigbang` | Pass | no pass | treatment only |
| `rdmorganiser/rdmo` | Pass | Pass | both pass |
| `jazzband/tablib` | Pass | Pass | both pass |
| `castagnait/plugin.video.netflix` | Pass | Pass | both pass |

Minimal B scored `5/5`; the control scored `4/5`, an absolute difference of `+0.20`.
There was one discordant pair, so the exact two-sided McNemar test is `p = 1.0`. The
direction is encouraging, but five pairs cannot establish a reliable effect.

The `bigbang` control did substantial useful work but its final program directly created
an importable stub artifact. The shared candidate policy rejected it before the Official
evaluator. This is a method failure under the frozen open-program boundary, not an
infrastructure Unknown.

## Mechanism Audit

Every Minimal B run made exactly one clean-replay call, and every first replay passed.
No trajectory exhibited replay failure followed by repair in the same Agent session.
Therefore this batch does **not** validate the proposed repair-loop mechanism. The
treatment-only `bigbang` success may reflect certification-aware planning or ordinary
run variance; it cannot be attributed to replay-conditioned repair.

The next causal design must separate:

1. a strong Agent that receives only terminal post-hoc replay;
2. the same Agent with one terminal clean-certification call;
3. the same Agent with callable replay and permission to continue after failure.

The comparison between 1 and 2 measures certification-aware construction. The comparison
between 2 and 3 isolates the value of feedback-conditioned repair.

## Resource Result

Across all five paired attempts, Minimal B used `2,855,195` total model tokens versus
`2,724,528` for control (`+4.8%`), and issued `94` container commands versus `107`
(`-12.1%`). For the four pairs with comparable coordinator timing, Minimal B used
`9,664.4 s` versus `7,102.8 s` (`+36.1%`). These are descriptive development results,
not an efficiency benefit.

Peak memory, disk growth, and network bytes were preregistered but not persisted by the
runner. They are missing measurements and must not be reconstructed from anecdotes.
The `bigbang` wall-clock pair is censored because its control used an exact-revision local
source cache after repeated pre-Agent GitHub failures.

## Verifier Limitation

Both methods officially passed `plugin.video.netflix` by adding Pylint's internal
`_pylint_config` directory to `PYTHONPATH`, which made a module named `setup` resolvable.
However, `docs/conf.py` imports `get_addon_data` from that module, and Pylint's module does
not provide the symbol. Clean replay proved exact-program reproducibility under the public
goal; it did not prove semantic compatibility of the resolved provider.

This post-hoc finding does not change Official Pass@1. It does establish a general
measurement distinction for future experiments: **module resolution** is necessary but
not equivalent to **required-interface compatibility**. Any added semantic diagnostic
must be applied identically to all methods and reported separately from the benchmark's
official score.

## Decision

Minimal B remains frozen as a baseline. It is not yet the converged EnvSolve-Pro
algorithm. Before opening another outcome-blind batch, shared infrastructure should kill
entire process trees on timeout, use an immutable exact-revision source cache for every
condition, and persist memory, disk, and network telemetry. These are measurement fixes,
not algorithmic contributions.

After that qualification, the next experiment is the three-arm mechanism decomposition
above on a larger repository-disjoint development batch. Structured state, checkpoints,
hypothesis search, and minimization remain deferred until a repeated failure pattern shows
which one is necessary.

Machine-readable evidence is in
`experiments/validations/pro_minimal_b_v1_paired_dev5_results.json`; it is recomputed by
`experiments/analyze_pro_minimal_b_v1_paired_dev5.py` from the effective-episode
adjudication and original run artifacts.
