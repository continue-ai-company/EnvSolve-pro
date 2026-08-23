# EnvSolve-Pro V2 Verifier-Handoff Screen Casebook

## Scope

This casebook records high-value failures from the preregistered 20-case development
screen. It supports failure taxonomy and algorithm diagnosis. It is not a held-out
effectiveness result, and counterfactual evaluations never replace Pass@1 outcomes.

## Case VH-001: `platformio/platformio-core@7cf8d1d`

**Screen outcome:** Agent noncompletion, Official Pass@1 = 0.

**Counterfactual outcome:** The exact certified replay program passed EnvBench
Official without another model call. This is descriptive classification evidence,
not a corrected screen outcome.

### What Happened

The Agent installed the project and its dependencies, reached zero Pyright missing
imports, and produced a bootstrap program. It then cleaned the live construction
workspace:

1. command 35 removed the active project-local `venv312`;
2. command 36 explicitly removed `build_output`;
3. commands 37 and 38 wrote and inspected the final bootstrap program; and
4. the next scheduled observation still attempted to use
   `/data/project/venv312/bin/python`.

The observation could no longer run its trusted goal. The outer minimal-integrity
audit then rejected the construction workspace because `build_output`, classified
as a harness-owned precondition, was absent. Generation terminated before Official.

### Why This Is Not a Deployment-Program Failure

The screen had already captured `minimal-b-replay-0001.sh`. In an independent fresh
checkout, this 827-character program:

- completed bootstrap successfully;
- produced a complete trusted-goal report;
- had zero missing imports;
- passed repository-effect audit; and
- received a clean-replay certificate.

We then evaluated that exact certified program with EnvBench Official, without
calling the model again. Official completed with `issues_count=0` and passed. The
944 other Pyright errors were non-scoring diagnostics.

### Three-Layer Diagnosis

**Observation layer:** construction ownership and the active interpreter path were
not exposed before cleanup. The next observation used a stale path and arrived too
late to guide repair.

**Constraint layer:** the shared boundary treated preservation of a mutable
construction artifact as a hard deployment requirement. That constraint is not
required by the clean replay or the Official evaluator and is the primary causal
bottleneck.

**Operation layer:** deleting a live interpreter before the next observation is a
risky state transition, but the final replay program does not contain that cleanup
and is sufficient. Therefore operation quality is not the earliest counterfactual
bottleneck for the submitted deployment.

Proposed subtype: `constraint / construction-state-ownership-conflict`. Because the
previously frozen taxonomy v1.0.1 has no such subtype, its compatible legacy mapping
remains `unresolved / novel-mechanism-held-for-taxonomy-v2`.

### Experimental Consequence

This episode remains a scientifically eligible screen failure and must be included
in the complete bad-case set. It is not retried or replaced, and the Official
counterfactual does not count as a screen pass. The fresh paired control and
verifier-handoff treatment will both retain runner 0.6.1. Since they share the same
boundary, this case tests whether that boundary dominates both arms; it is retained
even though the handoff transition alone is not expected to repair it.

Machine-readable evidence:
`experiments/validations/envsolve_pro_v2_verifier_handoff_v1_screen20_platformio_boundary_adjudication.json`.

## Case VH-002: `lichess4545/heltour@1d5fd89`

**Screen outcome:** EnvBench Official Pass.

**Research role:** Mechanism-activation and efficiency evidence, not a bad case and
not a causal treatment result.

### What Happened

The scheduled verifier first reported a complete Pass after request 16: all 77
initial missing-import obligations had been resolved. The control Agent did not
submit. It continued changing and probing the environment, and the request-32
observation regressed to 12 missing obligations. The Agent recovered to Pass at
request 48, then attempted delivery:

1. clean replay 1 failed;
2. the same active model session repaired the bootstrap program;
3. clean replay 2 passed; and
4. EnvBench Official passed with zero scored issues.

The completed control episode used 52 model requests, 1,401,571 total tokens, 49
shell operations, and two clean replays. Generation took approximately 27 minutes.

### Three-Layer Diagnosis

**Observation layer:** the executable verifier exposed a sufficient state at
request 16 and later exposed the regression. The necessary signal existed.

**Constraint layer:** the complete zero-obligation report was already an adequate
handoff condition. No additional cross-candidate constraint was needed.

**Operation layer:** the control policy continued environment mutation after a
verified sufficient state instead of switching to program materialization and
fresh replay. This created avoidable work and a temporary regression.

### Experimental Consequence

Heltour remains a screen success and is excluded from the preregistered failure-only
paired set. The request-16-to-request-52 gap identifies treatment headroom, but it
is only an upper bound: a forced handoff at request 16 might still fail clean replay
and require repair. A fresh paired episode is required before claiming saved
requests, tokens, or time. The case is retained for a later success-conditioned
efficiency analysis that is separate from the primary Pass@1 experiment.

## Case VH-003: `transientskp/tkp@8a19cd23`

**Screen outcome:** EnvBench Official Pass.

**Research role:** Independent handoff-headroom replication and deployment-quality
warning, not a bad case and not a causal treatment result.

### What Happened

The initial and request-16 observations both reported 38 missing obligations under
the base interpreter. The Agent had created `/data/venv`, but had not activated it
in the persistent construction session. It later switched to
`/opt/conda/envs/testenv/bin/python`; the request-32 observation then reported a
complete Pass with zero obligations.

The control Agent continued for nine more requests before its first clean replay at
request 41. That replay failed. After same-session repair, a second replay passed at
request 45, the program was submitted at request 46, and EnvBench Official passed.
The completed generation used 46 model requests, 1,263,597 total tokens, 43 shell
operations, and two clean replays in approximately 18 minutes.

### Three-Layer Diagnosis

**Observation layer:** the verifier correctly distinguished an installed but
inactive environment from the interpreter actually used by the persistent session.
After activation, it immediately exposed the sufficient state.

**Constraint layer:** the zero-obligation report was again sufficient to request a
handoff; no project-specific dependency rule was needed.

**Operation layer:** the Agent first omitted environment activation, then delayed
program materialization after Pass, and finally repaired a replay failure. The
feedback loop corrected all three transitions.

### Deployment-Quality Warning

The certified program created local modules for unavailable `casacore`, `ndimage`,
and legacy `exceptions` imports. This satisfies the Official missing-import
criterion and passed the current minimal boundary, but it does not establish full
runtime equivalence with the real libraries. The Official result remains valid;
deployment completeness must be reported as a separate evaluation axis rather than
being retroactively added as a case-specific hard constraint.

### Experimental Consequence

TKP is excluded from the preregistered failure-only paired set. Together with
Heltour, it shows that verified-sufficient states can precede delivery by many model
steps. The request-32-to-request-46 gap is only treatment headroom, not a causal
saving estimate. The stub-based path is retained for later completeness analysis.
