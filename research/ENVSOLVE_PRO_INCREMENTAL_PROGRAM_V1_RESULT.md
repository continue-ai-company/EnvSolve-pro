# Incremental Executable Program V1 Qualification Result

## Result

The fixed consumed three-case qualification rejects the V1 dual-tool interface before an
effect comparison. Across 46 successful provider responses, the Agent made 69 ordinary
shell calls and only one `apply_environment_step` call. Qibolab and HARK never activated
the defining path. Meerkat first activated it at request 20, after 31 ordinary shell
calls, recorded one successful `pydantic<2` step, and still had 79 active constraints.
No case reached replay or Official evaluation.

The clearest counterexample is HARK request 6. The Agent successfully ran
`python -m pip install -e ".[dev,doc]"` through `envbench_shell`, even though this was a
persistent deployment change that should have grown the executable program. The Agent
therefore preserved its learned use of one shell for both diagnosis and mutation instead
of treating two similar tools as different semantic channels.

## Adjudication

This is an interface failure, not evidence against incremental program construction. The
study did not run long enough to estimate Official success, and all three episodes are
excluded from effectiveness endpoints. Provider connection errors were retried
successfully; persistent-operation bypasses happened after valid responses resumed, so
network instability is secondary noise rather than the cause of non-activation.

V1 is stopped rather than repaired with stronger prompting. The next minimal treatment
will expose one arbitrary-Bash shell tool and require each call to declare whether its
effect is inspection-only or a persistent program step. A persistent successful call will
append to the program and trigger the existing goal/replay transition. This changes only
the action interface: it adds no package rule, command filter, checkpoint, cross-case
memory, hash, frozen contract, or gate.

## Exact Evidence

| Case | Responses | Provider errors | Shell | Apply | Tokens | Outcome |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Qibolab | 15 | 2 | 29 | 0 | 239,622 | Researcher stop |
| HARK | 10 | 5 | 9 | 0 | 62,532 | Researcher stop |
| Meerkat | 21 | 4 | 31 | 1 | 292,238 | Researcher stop |

Machine-readable adjudication:
`experiments/validations/envsolve_pro_v2_incremental_program_v1_consumed3_result.json`.
Raw partial evidence is retained locally under
`runs/envsolve-pro-v2-incremental-program-v1-consumed3-evidence/` and on Spark under
`/home/avdpro/work/runs/envsolve-pro-v2-incremental-program-v1-consumed3/`.
