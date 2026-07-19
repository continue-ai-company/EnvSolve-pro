# P6 Constraint-to-Operation Protocol V1

Status: implemented mechanism freeze before any new real-case qualification.

## 1. Purpose

EnvSolve separates environment deployment into four interfaces:

1. observation: record what happened as immutable evidence;
2. constraint: infer what is missing or conflicting;
3. operation: restrict how the environment may be changed;
4. verification: execute the complete program in a fresh environment.

This protocol freezes the minimal constraint-to-operation boundary. It does not
add a repository-specific module-to-package map and does not retrieve experience
from other cases.

## 2. Operation plan

`ConstraintOperationPlanner` deterministically projects each supported active
hard conflict into an `OperationRequirement`. Every requirement records:

- the conflict domain and subject;
- allowed operation kinds;
- source conflict identifiers;
- source constraint identifiers.

The V1 domain mapping is:

| Conflict domain | Allowed operation kind |
|---|---|
| runtime | runtime configuration |
| package | Python-package installation |
| capability | system-package installation |
| module | Python- or system-package installation |

Unsupported domains remain explicit in the plan. A hypothesis does not create a
mandatory operation requirement.

## 3. Candidate guard

The model chooses concrete parameters and proposes a complete replayable program.
Before container creation, `constraint-operation-guard-v1` compares its typed
actions with the latest candidate that actually received a verification record.
For every operation requirement, the new candidate must introduce at least one
new action of an allowed kind.

A guard rejection:

- is persisted as an action and failure event;
- consumes candidate and model budget;
- does not provision an environment or consume command budget;
- cannot become execution evidence.

The guard checks action class and novelty, not whether a package name is the
correct repair. Only fresh execution and verification establish that result.

## 4. Future-proof trajectory contract

The immutable event stream must retain enough provenance to reconstruct:

`source conflicts -> source constraints -> operation requirements -> candidate
mutations -> guard decision -> fresh-environment verifier outcome`.

EnvSolve v1 may read only the current episode's state. It must not use cross-case
natural-language experience, summaries, trajectories, rewards, or learned policy
updates. This keeps the first-paper comparison controlled while preserving:

- supervised state-action-outcome transitions for EnvSolve-RL;
- unsupported-domain, rejected-action, and parser-coverage statistics for a
  future Auto-EnvSolve outer loop.

Derived datasets for later projects must be versioned separately and must never
rewrite raw EnvSolve events.

## 5. Acceptance criteria

1. Synthetic tests cover conflict projection and guarded fresh replay.
2. Rejected candidates cannot be treated as executed history.
3. Existing full regression and Docker integration tests pass.
4. No benchmark-owned feedback or repository-specific repair mapping is added.
5. Implementation, tests, and bilingual protocol are hashed before unseen-case
   qualification.

