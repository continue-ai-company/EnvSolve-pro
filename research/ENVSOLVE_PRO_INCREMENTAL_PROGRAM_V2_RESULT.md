# Annotated Incremental Program V2 Qualification Result

## Result

V2 answers two mechanism questions and exposes one design failure. The one-shell
`inspect`/`persist` annotation activated naturally in both episodes that reached a real
deployment-operation opportunity. HARK recorded eight successful program steps, reached
zero active constraints at request 28, and automatically clean-replayed the accumulated
program. Meerkat recorded its main dependency installation at request 15 and reduced the
goal residual to 31 constraints. Qibolab remained in repository and goal diagnosis, so it
is censored as an episode without an observed operation opportunity.

The HARK replay then failed for the right reason. Six earlier steps hard-coded
`/data/project`, created `/data/project/.venv`, and assumed that path was the target source
checkout. Replay reported an outer-workspace violation and missing target-checkout files.
The same Agent understood the counterexample and started rebuilding under `/opt/harkenv`;
by the stop, the new environment had reduced the residual from 21 to 6 constraints.

## Adjudication

The annotation interface and the Observation-Constraint-Operation transition qualify.
The append-only program representation does not. Once a successful but invalid step has
entered the program, V2 can only append compensating work. It cannot replace or delete the
bad step, so every later replay repeats invalid or redundant operations. This is not a
package-specific failure: the same problem applies to a wrong path, interpreter, version,
index, or installation strategy.

This result does not show that V2 would fail Official if allowed to continue; compensation
might eventually pass. It shows that append-only deployment plans are the wrong core state
representation when replay can invalidate earlier decisions. Executable evidence may be
monotonic, while the current deployment plan must be mutable.

The next minimal treatment keeps the same continuous Agent session and annotated arbitrary
Bash shell. It adds one plan-edit action: replace or delete one indexed recorded step, then
immediately clean-replay the revised program. The active construction environment is not
rolled back and no checkpoint, package rule, cross-case memory, command classifier, hash,
contract, or gate is added.

## Exact Evidence

| Case | Responses | Errors | Inspect | Persist | Recorded | Tokens | Mechanism outcome |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Qibolab | 22 | 0 | 41 | 0 | 0 | 424,406 | No operation opportunity observed |
| HARK | 32 | 5 | 31 | 9 | 8 | 627,780 | Goal Pass, replay Fail, same-session redirection |
| Meerkat | 20 | 0 | 29 | 1 | 1 | 417,967 | Early substantive activation; residual 31 |

All episodes were stopped by the researcher and remain excluded from effectiveness
endpoints. No Official evaluation ran. Machine-readable adjudication is in
`experiments/validations/envsolve_pro_v2_incremental_program_v2_consumed3_result.json`.
Raw evidence is retained locally under
`runs/envsolve-pro-v2-incremental-program-v2-consumed3-evidence/` and on Spark under
`/home/avdpro/work/runs/envsolve-pro-v2-incremental-program-v2-consumed3/`.
