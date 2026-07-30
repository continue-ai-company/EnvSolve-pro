# EnvSolve-Pro Stateful-Agent V2.4 Pilot-4 Results

## Status

Pilot-4 is a clean, scientifically eligible development comparison. All 12 scheduled
episodes have valid artifacts, match their frozen schedule identities, and reached the
Official EnvBench evaluator. The four repository identities are now consumed and cannot
qualify a later method.

The comparison held the model (`gpt-5.5`), public executable goal, terminal-only
Official evaluator, seed, and open cumulative Bash interface fixed across:

1. strong single-session goal-aware Codex;
2. same-model multi-session raw repair V2.4;
3. EnvSolve-Pro structured stateful-agent V2.4.

Positions 3-6 in the original execution were interrupted or contaminated by the
experimenter and were excluded before outcome analysis. The frozen amendment assigned
new run IDs and reran every affected position. The formal analysis uses positions 1-2
from the source schedule and positions 3-12 from that outcome-independent amendment.

## Official Results

| Condition | Official Pass | End-to-end wall (s) | Commands | Input tokens | Output tokens | Reasoning tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Strong goal-aware baseline | 4/4 | 2,688.3 | 78 | 2,337,478 | 31,379 | 14,230 |
| Raw repair V2.4 | 4/4 | 3,125.3 | 57 | 2,320,139 | 31,637 | 16,035 |
| Structured V2.4 | 4/4 | 3,233.0 | 78 | 3,867,529 | 36,766 | 18,916 |

| Repository | Strong | Raw | Structured | Structured candidates / rounds |
| --- | ---: | ---: | ---: | ---: |
| great-tables | Pass | Pass | Pass | 1 / 1 |
| pyperf | Pass | Pass | Pass | 1 / 1 |
| cbmonitor | Pass | Pass | Pass | 1 / 1 |
| flavio | Pass | Pass | Pass | 1 / 1 |

There is no Official Pass gain. Relative to raw repair, structured V2.4 used 66.7% more
input tokens, 36.8% more container commands, and 3.4% more end-to-end time. Relative to
the strong single-session baseline, it used 65.5% more input tokens and 20.3% more time.
These are four-case descriptive resource differences, not population estimates.

## Mechanism Finding

V2.4's stateful hypothesis was not exercised. Every raw and structured episode passed
with one submitted candidate in one model round. No failed candidate produced a new
Observation, no constraint frontier was updated across sessions, and no later Operation
could benefit from structured state. The batch therefore does not test
failure-conditioned repair. Its resource differences come from first-round trajectories
and cannot be attributed to the dormant state mechanism.

The three simpler repositories show that a strong agent often solves the public goal
before a cross-session mechanism can act. On `cbmonitor`, an initial PyPI TLS failure
recovered within the session and correctly did not become a false deployment constraint.

`flavio` exposes the main algorithmic contradiction. Successful deployment required
coordinating:

- legacy SciPy API compatibility;
- a Python version that can host old SciPy;
- NumPy below 1.24 because that SciPy line uses removed NumPy aliases;
- ARM package and source-build feasibility for `rundec`;
- static analyzer visibility without breaking runtime interpreter and extension ABI
  consistency.

Raw repair and the strong baseline eventually submitted coherent Python 3.8
environments. Structured V2.4 tried more mutually incompatible states, including a stub
package that upgraded NumPy, several Pyright and Python versions, and a destructive
environment transaction. Its final script added Python 3.9 `rundec` package-cache
contents to a Python 3.8 environment through `PYTHONPATH`. Official Pyright passed, but
loading that compiled extension under Python 3.8 is not established. This is a
benchmark-objective gap, not an Official scoring error, so Official Pass and runtime
coherence must remain separate labels.

## Decision

V2.4 is frozen as an auditable structured baseline and is not promoted. The result does
not support a leaderboard, effectiveness, or efficiency claim.

The next hypothesis is smaller than another semantic rule set:

1. **Observation:** convert command outcomes into a compact, monotonic compatibility
   frontier inside the active agent session.
2. **Constraint:** admit only causally supported package, platform, version, and
   operation facts; keep Official-goal status distinct from runtime coherence.
3. **Operation:** preserve an open terminal, but screen high-impact environment
   transactions with feasibility checks, postconditions, and explicit suppression of
   already falsified actions.

This moves state to the point where strong agents actually fail and recover, instead of
waiting for a second candidate that frequently never exists. The four Pilot-4
repositories may be used only for regression and mechanism construction. Qualification
must use outcome-blind, repository-disjoint cases and measure both Official Pass@1 and
failure-conditioned recovery.

## Evidence

- Frozen analysis schedule:
  `experiments/schedules/pro_stateful_agent_v2_4_pilot4_mac_clean_retry2.json`
- Clean amendment:
  `experiments/validations/pro_stateful_agent_v2_4_pilot4_clean_retry2_amendment.json`
- Hash-audited result:
  `experiments/validations/pro_stateful_agent_v2_4_pilot4_results.json`
- Consumed CWD causal replay:
  `experiments/validations/pro_stateful_agent_v2_4_cwd_causal_replay1.json`
