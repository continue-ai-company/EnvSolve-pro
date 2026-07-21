# EnvSolve-pro P2 Dominant-Contradiction Protocol v1

## Question

After removing interface censoring, what is the first frequent, actionable deployment
contradiction that prevents strong agents from reaching a correct terminal environment?
P2 diagnoses that contradiction before adding an EnvSolve-pro mechanism.

## Cohort

Select six cases from the 118 untouched EnvBench Dev cases by ascending
`SHA256(salt + NUL + case_id)`. Selection uses metadata only: no repository checkout,
failure prescreen, package-manager stratification, replacement, or prior outcome.
Selected cases become diagnostic data immediately and cannot later support a
confirmatory effectiveness claim.

## Frozen Methods

Each case runs four methods in salted order:

1. Codex CLI native agent with its locally authenticated `gpt-5.5` model;
2. reproduced Repo2Run with `deepseek/deepseek-v4-pro`;
3. EnvBench raw ReAct with the same DeepSeek model;
4. the P1 EnvSolve-pro scaffold with the same DeepSeek model.

All methods have terminal-only official evaluator access. The three API methods share
the same broad operational circuit breakers; resource use is reported, not a success
criterion. Codex retains its native stopping rule. No cross-case memory is enabled.

## Analysis Unit

For each complete trajectory, identify the **earliest decisive repair opportunity**: the
first observed condition for which a different state update or operation could plausibly
change terminal success. Assign exactly one primary layer and retain secondary tags.

- **Observation:** decisive evidence was unavailable, lost, misclassified as an
  algorithmic result, or not transferred across execution contexts.
- **Constraint:** available evidence was not converted into the missing/conflicting
  condition, an incorrect belief survived contradictory evidence, or an unresolved
  obligation was dropped.
- **Operation:** the relevant condition was represented, but no viable environment
  change was proposed, executed, preserved, repaired, or finalized.

Infrastructure censoring remains Unknown and receives no algorithmic layer. A terminal
failure with no decisive opportunity visible is labeled unresolved, not forced into a
layer.

## Dominance Rule

A mechanism may be proposed only if one contradiction family:

- appears in at least three distinct repositories;
- is supported by direct trajectory evidence, not terminal error counts alone;
- occurs across at least two methods, or has a deterministic method-specific cause;
- admits a repository-independent intervention at one of the three layers; and
- is not an evaluator-interface or network artifact.

If no family meets this gate, expand diagnosis with another preregistered sample. Do not
weaken the gate or optimize on an isolated case.

## Freeze Rule

The P1 commit, prompts, candidate interface, verifier, adapters, baseline compilers,
official protocol, method matrix, sample size, salt, and attribution rules are frozen
before selection. During the 24-position batch, solver or wrapper changes are prohibited.
An infrastructure retry is allowed only when no valid model response and no environment
command were produced; otherwise preserve the partial episode as Unknown.

P2 may identify an algorithmic hypothesis. It cannot establish EnvSolve-pro
effectiveness.
