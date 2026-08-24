# EnvSolve-Pro V2 Verifier-Handoff Screen Casebook

## Scope

This casebook records high-value failures from the preregistered 20-case development
screen. It supports failure taxonomy and algorithm diagnosis. It is not a held-out
effectiveness result, and counterfactual evaluations never replace Pass@1 outcomes.

## Screen Closure

All 20 scheduled cases produced scientifically eligible outcomes: 17 Official Passes
and three Official Pass@1 failures, with no censored case. Two passing outcomes used
the preregistered exact-script Official-only retry after evaluator read timeouts; the
model and deployment program were not rerun.

The complete mechanically selected bad-case set is PlatformIO, Marimo, and ILAMB.
Their earliest decisive causes span one constraint-layer failure
(`construction-state-ownership-conflict`) and two operation-layer failures
(`replay-feasibility-and-late-delivery` and `masked-required-provider-failure`). The
screen also exposed a general observation-layer cwd defect on SDK Python, but that
episode recovered and passed Official, so it is diagnostic evidence rather than a
bad case. These counts describe this development screen only; they are not an
estimated population distribution or a held-out result.

The final `section-properties` episode passed after request 32 first reached zero
missing-import obligations, one clean replay passed, and request 34 submitted the
program. Its direct import probe still found `pypardiso` unusable without an MKL
runtime. Together with other passing cases, this confirms that Official success and
deployment completeness must remain separate reported axes rather than motivating a
post-hoc case-specific gate.

Machine-readable closure evidence:
`experiments/validations/envsolve_pro_v2_verifier_handoff_v1_prospective_screen20_result.json`.
The paired schedule contains both fresh arms for every bad case:
`experiments/schedules/envsolve_pro_v2_verifier_handoff_v1_paired_screen_bad_cases.json`.

## Paired Result

All six fresh runs completed. On EnvBench Official Pass@1, the scheduled-observation
control passed `3/3` cases and verifier handoff passed `2/3`; there was one control-only
Pass and no treatment-only Pass. Protocol-compliant success was `2/3` versus `1/3`
because both Marimo arms created manual placeholder modules under `site-packages` and
are algorithm failures on the allowed-action axis, despite both receiving Official Pass.

PlatformIO is the only concordant, protocol-valid success pair. Handoff used 16 rather
than 35 model requests, 226,687 rather than 1,026,414 tokens, and 174 rather than 1,211
generation seconds. This is an efficiency signal from one development pair, not a
success-rate result. On ILAMB, the control passed through the preregistered exact-script
Official-only retry after a classified evaluator read timeout; handoff failed Official
and was ineligible for retry under the frozen classifier.

The prospective pilot therefore falsifies verifier-triggered handoff as the primary
success-rate mechanism. It may remain an optional efficiency treatment after a trusted
replay Pass, but the next algorithm must address two earlier causes: trusted goal
observations must be invariant to the Agent's current working directory, and clean-replay
counterexamples must be converted into executable program postconditions without
restricting the Agent's repair policy. The Marimo pair additionally justifies an
integrity check on import-provider provenance; it does not justify package-specific
rules.

Machine-readable paired evidence:
`experiments/validations/envsolve_pro_v2_verifier_handoff_v1_paired_screen_bad_cases_result.json`.
Protocol adjudication:
`experiments/validations/envsolve_pro_v2_verifier_handoff_v1_marimo_protocol_adjudication.json`.

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

## Case VH-004: `getsentry/sentry-python@ec7172e1`

**Screen outcome:** EnvBench Official Pass.

**Research role:** Version-compatibility convergence and low handoff-headroom
evidence, not a bad case and not a causal treatment result.

### What Happened

The base interpreter initially exposed 215 missing-import obligations. The Agent
created a Python 3.11 virtual environment, installed broad integration extras, and
then activated that environment in the persistent session. Scheduled observations
recorded the following contraction:

`215 -> 215 -> 215 -> 19 -> 9 -> 1 -> 0`.

After basic package coverage, the remaining obligations were legacy or
version-sensitive module paths. The Agent consulted repository `tox.ini` evidence,
selected compatible dependency versions, and handled the final
`pytest_chalice.handlers` path. The first complete Pass appeared at request 74. The
Agent issued its first clean replay at request 77; it passed, the program was
submitted at request 78, and EnvBench Official passed.

Generation used 78 model requests, 4,258,047 total tokens, 98 shell operations, and
one passing clean replay in approximately 65 minutes. The complete case, including
Official evaluation, took approximately 76 minutes.

### Three-Layer Diagnosis

**Observation layer:** executable observations separated interpreter activation
from dependency installation and exposed monotonically shrinking residuals.

**Constraint layer:** module-path obligations remained stable while their causes
changed from package absence to version/API incompatibility. Project-specific
package rules were unnecessary.

**Operation layer:** the Agent used repository evidence to choose versions and
resolve the residuals, then produced a replayable program on its first attempt.

### Experimental Consequence

Sentry is excluded from the failure-only paired set. Unlike Heltour and TKP, the
gap from first Pass to submitted program was only four requests. This is evidence
that handoff opportunity and potential efficiency gain are heterogeneous across
cases; aggregate and distributional paired results are required, rather than a
maximum-saving anecdote.

## Case VH-005: `injectivelabs/sdk-python@a93aab12`

**Screen outcome:** EnvBench Official Pass.

**Research role:** Observation-semantic false-regression evidence and an additional
deployment-quality warning. It is not a bad case and not a causal treatment result.

### What Happened

The initial and request-10 scheduled observations both reported 19 missing-import
obligations under `/opt/conda/bin/python` from `/data/project`. While investigating
historical package wheels, the Agent changed its persistent shell directory to
`/tmp/inj`. The request-21 observation then reported 183 obligations and labelled
the transition a regression, although the interpreter and installed environment had
not changed. Immediately returning to `/data/project` restored the original
19-obligation result in the Agent's own probe.

The Agent subsequently resolved the real compatibility problems. The trusted
observations contracted to 5 obligations at request 34 and zero at request 45. The
first clean replay passed, the program was submitted at request 46, and EnvBench
Official passed with zero scored issues. Generation used 46 model requests,
2,001,524 total tokens, 63 shell operations, and one passing clean replay. The
replay bootstrap took approximately 63 seconds.

### Three-Layer Diagnosis

**Observation layer:** the trusted goal receives an absolute project-root argument,
but executes from the Agent shell's current directory. Pyright configuration and
module resolution are therefore affected by an unrelated temporary `cd`. The 183
obligations were an observation false regression, not a deployment-state regression.

**Constraint layer:** the true obligations remained missing module paths. No new
dependency rule was needed; the erroneous delta came from inconsistent observation
context.

**Operation layer:** changing directories for investigation is a legitimate Agent
operation. Requiring the Agent never to leave the project root would unnecessarily
restrict free search. The verifier should instead run the public goal from a stable
project-root working directory while preserving the active interpreter and
environment.

### Deployment-Quality Warning

The selected old `injective-py` distribution satisfied Pyright resolution, but its
generated protobuf modules were incompatible with the installed protobuf runtime.
The Agent observed this runtime import failure and correctly noted that it was
outside EnvBench's `reportMissingImports` objective. The Official Pass is valid, but
it does not establish runtime-complete deployment. As in TKP, completeness remains
a separate reporting axis rather than a retroactive case-specific gate.

### Experimental Consequence

SDK Python is excluded from the preregistered failure-only paired set. Runner 0.6.1
remains frozen for the current screen and pair. After the pair completes, the next
runner version should execute scheduled goals from `/data/project` and add a
regression test in which the Agent temporarily changes directory without changing
the environment. This is an observation-semantic correction, not a new deployment
constraint.

Machine-readable evidence:
`experiments/validations/envsolve_pro_v2_verifier_handoff_v1_screen20_sdk_python_cwd_adjudication.json`.

## Case VH-006: `marimo-team/marimo@537b2309`

**Screen outcome:** Agent noncompletion, Official Pass@1 = 0.

**Research role:** A scientifically eligible bad case exposing replay-feasibility,
operation-ordering, and late-delivery failures.

### What Happened

The initial trusted goal reported 91 missing-import obligations. The Agent built a
Python 3.12 environment and first reached a complete construction-state Pass at
request 64. It voluntarily attempted clean replay at request 69. Three successive
programs all timed out during bootstrap at approximately 1,800 seconds; none reached
the trusted goal in the replay environment.

The Agent then measured cold installation directly. A broad dependency command took
1,870 seconds and produced a 7.5 GB environment because `langchain`, `pymde`, and
other transitive dependencies upgraded Torch to a CUDA build, pulling approximately
2.9 GB of NVIDIA libraries. At request 116, the Agent verified that a pip constraint
could preserve `torch==2.13.0+cpu`. Its final construction command completed and a
request-120 probe reported zero missing imports under the resulting environment.
However, this final program was never clean-replayed or submitted. Generation ended
with `Agent exhausted the request safety cap without submission`.

The episode used 120 model requests, 7,256,220 total tokens, 117 shell operations,
and three unknown clean replays over approximately 4 hours 38 minutes. No provider
error occurred.

### Three-Layer Diagnosis

**Observation layer:** clean replay faithfully exposed a deployment fact hidden by
the warm construction cache: the cumulative program could not complete inside the
fixed command window. Later scheduled construction observations were polluted by
temporary working-directory and PATH changes, but those false regressions were not
the earliest decisive cause because replay had already exposed the real timeout.

**Constraint layer:** the stable public obligations were known, and the replay
counterexample added a deployment-feasibility condition: satisfying all imports with
an unconstrained CUDA dependency closure was not replayable. The harness did not
convert this into a package-specific rule, and the Agent eventually inferred the CPU
compatibility condition from execution evidence.

**Operation layer:** the cumulative program installed the broad dependency set before
preserving the CPU Torch condition. Repeating nearly the same cold closure consumed
most of the episode. The Agent found a plausible order-and-version repair only at the
end and spent the final request probing the construction state rather than replaying
and submitting the deliverable. The primary subtype is therefore
`operation / replay-feasibility-and-late-delivery`.

### Experimental Consequence

Marimo must enter the complete preregistered bad-case set. The request cap is a matched
experimental safety condition, not a claim that Token or request count defines the
deployment problem. The late CPU-constrained program is diagnostic evidence only:
without a clean replay, it cannot retroactively change the failure. A verifier handoff
would have triggered at request 64 rather than the control's first replay at request
69, but whether those five requests and an earlier counterexample change the terminal
outcome is unknown and requires the fresh paired episode.

This case motivates a possible later treatment that maintains replay feasibility while
constructing the operation sequence. It does not yet justify a package rule, automatic
dependency minimizer, or new gate; those would require recurrence across the frozen
bad-case set.

Machine-readable evidence:
`experiments/validations/envsolve_pro_v2_verifier_handoff_v1_screen20_marimo_adjudication.json`.

## Case VH-007: `rubisco-sfa/ilamb@c0aecd5e`

**Screen outcome:** Clean replay Pass, EnvBench Official Fail.

**Research role:** A scientifically eligible bad case exposing masked provider failure
and incomplete postcondition enforcement inside the delivered operation sequence.

### What Happened

The initial trusted goal reported 28 obligations. The Agent installed ILAMB's
scientific stack, discovered that `cf_units` required the UDUNITS2 XML database on
Linux ARM, and reached zero construction obligations at request 23. Its first clean
replay passed in 217 seconds, it submitted at request 25, and generation completed.

Official executed the same program but failed before Pyright. The relevant program
logic was:

```bash
conda install -y -n base -c conda-forge udunits2 >/dev/null 2>&1 || true
export UDUNITS2_XML_PATH="$PPREFIX/share/udunits/udunits2.xml"
[ -f "$UDUNITS2_XML_PATH" ] || \
  export UDUNITS2_XML_PATH=/opt/conda/share/udunits/udunits2.xml
```

The provider operation did not produce UDUNITS2 in the Official container, but the
program suppressed its failure and never checked that the fallback path existed.
Building `cf_units` then failed with `Can't open UDUNITS2_XML_PATH file`. Official
reported bootstrap exit code 1. Its `issues_count=0` is not a Pass because Pyright
never ran.

The episode used 25 model requests, 504,687 total tokens, 32 shell operations, and
one passing clean replay. Generation took approximately 16 minutes; Official failed
after approximately 6 minutes. No provider-model error occurred.

### Three-Layer Diagnosis

**Observation layer:** replay and Official executed the same program but sampled
different outcomes of a provider-dependent operation. A single successful replay
proved one executable path, not that every required postcondition was enforced. This
is partial execution coverage rather than evidence that the target image or goal was
different.

**Constraint layer:** the requirement was already known and concrete: a real
UDUNITS2 XML file must exist before building `cf_units`. The final program represented
it only as two candidate paths and did not retain existence as an enforced
postcondition.

**Operation layer:** `|| true` converted a required provider operation into an
unchecked optional action, and the fallback assignment changed a string without
creating the required file. The earliest decisive cause is therefore
`operation / masked-required-provider-failure`.

### Experimental Consequence

ILAMB remains an Official Pass@1 failure and enters the complete bad-case set. The
episode has a scientifically valid Agent outcome, so the preregistered infrastructure
retry rule does not apply. A later exact-script success under better network conditions
would be a counterfactual, not a replacement outcome.

Verifier handoff would trigger at request 23 and the control replayed at request 24,
leaving almost no pre-replay headroom. A fresh pair must still be run, but this case is
unlikely to be solved merely by moving the same replay one request earlier. The broader
hypothesis is that replay feedback should expose and preserve required operation
postconditions; one case does not justify a hard syntactic rule against shell failure
handling.

Machine-readable evidence:
`experiments/validations/envsolve_pro_v2_verifier_handoff_v1_screen20_ilamb_adjudication.json`.
