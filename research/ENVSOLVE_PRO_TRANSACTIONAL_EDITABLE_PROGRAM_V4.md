# EnvSolve-Pro Transactional Editable Program V4

## Research Question

V3 established that a strong Agent can use clean-replay evidence to revise an earlier
deployment step in the same active session. It also exposed one deterministic operation-layer
failure: when the model emitted several indexed edits in one response, early deletions shifted
the targets of later edits. Two intended deletions became invalid and each successful partial
edit caused another expensive replay.

V4 asks one narrow question: can one snapshot-relative program transaction preserve the
Agent's complete repair intent while avoiding index drift and partial-program replay churn?

## Minimal Change

V4 preserves the V3 observation stream, continuous model session, annotated arbitrary-Bash
shell, current goal, clean target-state replay, evaluator isolation, and mutable program.
It changes only `revise_program`:

- the Agent supplies one non-empty list of replacements and deletions;
- every `step_index` refers to the same program visible before the call;
- the whole list is validated before program state changes;
- replacements and deletions are applied together;
- the resulting complete program is replayed once;
- the active construction environment is neither changed nor rolled back.

The V3 runner remains registered unchanged. V4 has a separate runner identity, so later
comparisons and rollback do not rewrite the historical method.

## Three Layers

**Observation.** Shell feedback, complete public-goal observations, and exact clean-replay
counterexamples remain unchanged.

**Constraint.** The same Agent infers case-local unresolved contradictions. V4 adds no package,
version, command, or cross-case constraint rule.

**Operation.** Inspection and persistent construction operations remain unchanged. Only plan
repair becomes a snapshot-relative batch transaction followed by one replay.

## What V4 Does Not Add

V4 adds no stable step identifier, checkpoint, container snapshot, controller classifier,
package rule, command filter, candidate graph, cross-case memory, prompt patch for HARK, hash,
frozen contract, or gate. Unique in-range indices and typed replacement strings are ordinary
transaction input validity, not deployment-policy restrictions.

## Qualification

Deterministic tests cover replacement plus non-adjacent deletion against one pre-edit snapshot,
all-or-nothing validation, unchanged V3 semantics, one replay for one complete batch, runner
registration, and tool schema. They pass on both macOS ARM and Spark Linux ARM.

No second live HARK qualification is used. HARK generated the proposal and is already consumed;
rerunning it to confirm an expected repair would not estimate algorithm effect.

## Next Experiment

The first live V4 experiment is an outcome-blind paired development comparison against Minimal
B. Both arms use the same continuous Agent, public goal, clean replay service, model, provider,
seed, image, source access, evaluator, and broad safety limits. V4 alone maintains the
operation-linked editable program and exposes transactional plan repair.

Cases must be selected before V4 outcomes from a pre-existing baseline failure census, covering
major candidate-formation and target-replay failure strata. Selection may use historical
Repo2Run, Codex, EnvBench-baseline, or Minimal-B outcomes, but not V4 outcomes. Pair order is
alternated. Official Pass@1 is primary; infrastructure censoring is adjudicated separately.

Diagnostic outcomes are candidate formation, edit activation, invalid edits, replay sequence,
counterexample-to-valid-plan latency, requests, tokens, time, traffic, and deployment quality.
Success is compared before resources. Clean reproducibility, completeness, declaration fidelity,
and path cost are reported separately and cannot relabel Official Pass@1.

V3 remains a representation ablation. A V3-versus-V4 edit-efficiency comparison is meaningful
only on prospectively identified episodes where both arms naturally activate plan revision.
