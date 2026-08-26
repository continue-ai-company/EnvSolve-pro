# EnvSolve-Pro V2 Atomic-Submit Pilot Casebook

## Question

Does replacing plain final delivery with one atomic action -- validate the complete
bootstrap program, replay it in a fresh environment, and return any failure to the
same Agent session -- improve deployment success without controlling the Agent's
search policy?

The prospective pilot used the only two Dev-pool cases with no prior execution
evidence. Case selection therefore preceded outcomes, but it did not guarantee that
the matched `F+O` control had headroom. Both arms used
`deepseek/deepseek-v4-flash-0731`, DeepInfra, the same case seed, the same initial
prompt, and the same visible action signatures. The only treatment difference was
the semantics of `submit_bootstrap`.

## Result

Both treatment programs passed clean replay and EnvBench Official. The verticapy
control also passed Official. The fontbakery control's first Official evaluation was
censored by an evaluator read timeout; its unchanged script passed an Official-only
retry, but that retry used a non-identical method label and is therefore supplementary
rather than part of strict automatic adjudication.

The conservative primary table consequently contains one eligible pair and one
censored pair, with no treatment-only success. The semantic outcome is still a
ceiling tie: all four generated programs eventually passed Official without another
model execution.

| Case | Plain `F+O` | Atomic submit | Atomic replay path |
| --- | --- | --- | --- |
| fontbakery | Censored; unchanged-script retry Pass | Pass | Pass |
| verticapy | Pass | Pass | Fail, Fail, Pass |

Universal atomic replay was more expensive in aggregate: 126 versus 88 model
requests, 2.70M versus 1.99M tokens, and 7,419 versus 3,762 generation seconds.
The overhead is concentrated in verticapy, where atomic replay used 57 versus 28
requests, 1.32M versus 0.31M tokens, and 5,753 versus 911 generation seconds.

## Mechanism Evidence

Fontbakery passed its first fresh replay. Verticapy produced the informative chain:

1. replay 1 failed on a downloaded-package hash mismatch;
2. the same session changed the acquisition strategy;
3. replay 2 exposed a different package hash mismatch; and
4. the same session added retry behavior, after which replay 3 and Official passed.

This proves that atomic delivery can expose hidden target-state failures and preserve
repair continuity. It does not show a success-rate gain: the independently generated
plain-control program also passed Official. Final clean replay and Official agreed on
both treatment cases.

## Decision

Do not promote universal atomic replay from this pilot, and do not add package- or
network-specific rules. Retain the implementation as a mechanism treatment. The next
experiment must use a mechanically selected, fixed batch of pre-existing `F+O`
Official failures. It should test whether replay feedback changes Pass@1 where the
control has measured headroom, while reporting replay count, generation time, tokens,
and network transfer as separate costs.

Machine-readable audit summary:
`experiments/validations/envsolve_pro_v2_atomic_submit_replay_v1_prospective2_summary.json`.
Spark artifacts:
`/home/avdpro/EnvSolve-Pro-f52da5a/runs/envsolve-pro-v2-atomic-prospective2-v1`.
