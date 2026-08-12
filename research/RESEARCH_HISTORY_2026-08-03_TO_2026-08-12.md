# EnvSolve-Pro Research History: 2026-08-03 to 2026-08-12

This index reconstructs the local research work that accumulated after commit
`6956d03` on 2026-07-30 and was backed up on 2026-08-12.

## Reading the history

The commit timestamps below are the backup reconstruction time. They are not
backdated. The original evidence time is retained inside preregistrations,
amendments, execution bindings, result records, and document status lines.

Some shared source files evolved repeatedly while they were uncommitted. Git can
preserve their final surviving contents, but it cannot recover overwritten bytes
from intermediate versions that never existed as commits. The append-only
experiment records preserve the corresponding hypotheses, decisions, failures,
and adjudications without pretending that an unrecoverable source snapshot exists.

## Ordered milestones

| Evidence period | Commit | Milestone | Preserved evidence |
| --- | --- | --- | --- |
| 2026-08-03 | `2ce26c9` | All-trajectory reassessment | Active-state mechanism gate, preregistration, network amendment, and bilingual reassessment |
| 2026-08-04 to 2026-08-05 | `409c7db` | Minimal B | Continuous Agent session, clean replay MCP, exact-revision cache, process cleanup, Dev-5 protocol and results |
| 2026-08-05 | `a5eb59d` | Certification-repair ablation | A/B/C design freeze, one-shot and replay implementations, selection audit, and preregistration |
| 2026-08-06 to 2026-08-07 | `4a06d44` | Boundary v2 | Noninterfering goal shell, legal repository configuration correction, Readux pilot, and block-level adjudications |
| 2026-08-07 to 2026-08-08 | `62ed69d` | Boundary v3 | Namespace and provenance calibration, consumed controls, untouched preregistration, and validity stop |
| 2026-08-08 | `7358c33` | Boundary v4/v5 | Transitional calibration, dual-platform qualification, untouched-4 triplets, gate result, and casebooks |
| 2026-08-08 | `b959ef1` | Submitted program preservation | Exact submitted programs omitted by the JSON-oriented boundary archive |
| 2026-08-09 to 2026-08-10 | `d7ccc08` | Dev bad-case census | 209-case universe, Observation/Constraint/Operation taxonomy, Spark backend, 119 sequential evidence records, and casebooks |
| 2026-08-10 | `b3b2c72` | EnvSolve-Pro V2 freeze | F versus F+S+R implementation, minimal integrity, blind Dev-12 selection, smoke closure, and preregistration |
| 2026-08-10 to 2026-08-12 | `4b4d229` | Dev-12 Pair01-06 | Pair results, infrastructure censoring, retry amendments, mechanism semantics, bilingual paper and experiment plans |
| 2026-08-12 | `930af1a` | Evaluator retry reliability | Auditable exact-script retry when Official evaluation leaves an empty raw result and network evidence in its log |

## Repository and raw-run boundary

The Git history includes source, tests, case identities, configs, schedules,
protocols, preregistrations, amendments, submitted programs, aggregate results,
casebooks, and bilingual research documents. Local credentials, dependency caches,
baseline checkouts, and `runs/` remain excluded by `.gitignore`.

At backup time, `runs/` occupied about 9.6 GiB and contained roughly 330,000 files.
It includes repeated third-party repository checkouts and full model responses, so it
is neither a suitable nor a safe Git payload. The compact, auditable records needed
to interpret the research are committed under `experiments/validations/`, while raw
run retention requires a separate encrypted object-store archive with a manifest and
retention policy.

## Verification policy

Before publishing this reconstruction:

1. every staged milestone was checked with `git diff --cached --check`;
2. the index was scanned for known credential fragments and private-key markers;
3. no untracked file exceeded 1 MiB, and no external symbolic link was included;
4. focused tests were run after the evaluator retry repair;
5. the full test suite was run against the final reconstructed tree.
