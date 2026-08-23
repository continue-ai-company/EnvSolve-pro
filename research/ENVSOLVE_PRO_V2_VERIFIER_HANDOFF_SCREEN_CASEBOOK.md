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
