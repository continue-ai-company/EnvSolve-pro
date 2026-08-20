# EnvSolve-Pro V2 Consumed Bad-Case Profile

Status: complete mechanism diagnosis, 2026-08-20

## Question

Does adding same-session clean replay to the same DeepSeek V4 Flash free Agent repair
current deployment failures, or are the historical failures mostly artifacts of the old
harness?

This is a six-case consumed-development study with one realization per arm. It cannot
support an effect-size, generalization, leaderboard, or SOTA claim.

## Result

| Outcome | Count |
|---|---:|
| A-F Official Pass | 5/6 |
| B-FSR Official Pass | 4/6 |
| B-only pass | 1 |
| A-only pass | 2 |
| Both pass | 3 |

The old B-FSR arm did not beat free search. It won `basxconnect`, lost `graphium` and
`cvxportfolio`, and tied the remaining three cases.

## What Replay Actually Did

Replay produced three feedback-conditioned program changes:

- `basxconnect`: replay exposed omitted Git `safe.directory`; the same session added it,
  and the revised program passed replay and Official.
- `UER-Py`: replay exposed the `torchcrf` import/provider mismatch; the program changed
  from `torchcrf` to `pytorch-crf`, and both arms ultimately passed Official.
- `graphium`: replay exposed and repaired Git ownership, but then issued a false Pass.

The third case revealed the decisive harness defect. Old replay inherited the package
cache accumulated during construction. EnvBench Official starts from the target image
with the repository mounted and no construction cache. Graphium's passing replay logged
41 `Using cached` lines; Official logged zero and failed dependency resolution. The same
class of replay-to-target mismatch appeared in `cvxportfolio`, although its terminal
empty-setuptools result remains network/index ambiguous.

## Three-Layer Interpretation

- **Observation:** the replay environment reported a state that was easier than the
  delivered target state. The Agent therefore received false evidence of reproducibility.
- **Constraint:** once a faithful failure is visible, the Agent can usually infer the
  missing condition, as shown by Git ownership and the TorchCRF provider mapping.
- **Operation:** the useful repair loop is small: revise the complete program in the same
  session and execute it again from the target state.

The active contradiction is therefore not a shortage of cross-case package rules. It is
the lack of a faithful target-state counterexample at the point where the Agent decides
that a program is deliverable.

## Resource Observation

On the three joint-success cases, B used 123 versus 158 model requests and 1.79M versus
3.36M tokens. This is descriptive only: the set is conditioned on joint success and each
arm has one realization. Graphium also shows why success must remain primary: A spent 90
requests and 3.85M tokens but produced the only Official-passing program.

## Decision

The next minimal treatment is **same-session target-state counterexample replay**:

1. The Agent freely constructs a complete deployment program in one continuous session.
2. The harness executes that whole program in a fresh environment matching delivery
   cache semantics.
3. The first executable failure and bounded raw evidence return to the same session.
4. The Agent revises the whole program and repeats until target-state replay passes.

Commit `448de40` implements the required measurement correction by keeping the run-local
package cache in construction only. No package-rule library, scheduled observation,
checkpoint search, cross-case memory, or new hard operation constraint is added.

These consumed cases may verify mechanism activation. Any effectiveness claim requires a
separate outcome-independent qualification batch.
