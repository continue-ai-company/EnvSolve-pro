# EnvSolve-Pro Boundary-v5 Untouched-4 Results

## Status

The preregistered gate is complete: 4 untouched repositories, 3 paired arms, and 12 effective Agent episodes. The implementation and boundary remained frozen throughout the gate. This document records the result without changing the paper claim or the next algorithm.

## Question

Does Agent-visible replay in a fresh environment improve Official EnvBench Pass@1 beyond a strong coding Agent?

- **A, strong-Agent control:** one continuous Agent session, followed by a hidden post-session replay. Replay feedback never returns to the Agent.
- **B, one-shot certification:** the Agent may request one visible fresh replay, but cannot revise after it.
- **C, retryable certification:** the same Agent session may use fresh replay feedback, revise the program, and replay again.

The public goal, model, reasoning effort, candidate language, qualification boundary, repository seed, and Mac host were controlled within the gate.

## Primary Result

| Arm | Official Pass@1 | Cases won against A | Cases lost against A |
| --- | ---: | ---: | ---: |
| A | 4/4 | - | - |
| B | 4/4 | 0 | 0 |
| C | 4/4 | 0 | 0 |

Observed paired success differences are zero. The sample is small and success-saturated, so it cannot establish that replay never helps. It does establish that v5 produced no benchmark-success gain on this gate.

## Mechanism Result

B's first clean replay passed in all four cases, so B created no repair opportunity.

C passed its first replay in two cases. In the other two, the same Agent session revised the program after a failed replay and then passed both fresh replay and Official EnvBench. The retry mechanism therefore works as implemented.

Both repairs, however, concerned the study's provenance boundary:

1. GPflow used a Conda-managed pip installation path that the boundary rejected.
2. NeuralForecast used `uv venv --seed`, which introduced virtualenv seed files without accepted ownership provenance.

Neither first failure was an Official EnvBench missing-import failure. These episodes demonstrate mechanism activation, not recovery of benchmark failures.

## Main Findings

### 1. Replay is not yet the success bottleneck

The strong Agent already solved all four repositories. Adding visible replay did not rescue an additional case. More cross-candidate constraints are therefore unsupported by this evidence.

### 2. Official success is not complete deployment

On NeuralForecast, B intentionally installed the project and direct import providers with `--no-deps`. It passed the frozen Official missing-import metric while pip reported missing transitive dependencies. We must report Official Pass@1 and complete runnable deployment as separate outcomes.

### 3. Successful paths vary more than their scores

Independent NeuralForecast trajectories produced three different successful artifacts:

| Arm | Deployment path | Official result |
| --- | --- | ---: |
| B | Metric-minimal direct providers, incomplete transitive dependencies | Pass |
| C | Complete CPU-only PyTorch environment | Pass |
| A | Complete default PyTorch environment with CUDA dependencies | Pass |

Package and hardware choices dominated time, storage, and network traffic. These choices occurred before replay feedback and are path-quality evidence, not a causal benefit of C.

### 4. Efficiency numbers are descriptive

Mean observed wall time was 1,681 seconds for A, 1,318 for B, and 1,151 for C. Mean input tokens were 616,208 for B and 659,831 for C; A has 759,556 over three episodes because the interrupted GPflow wrapper did not preserve token totals. Four stochastic trajectories, cache state, network conditions, schedule order, and different deployment paths prevent a causal efficiency claim.

## Decision

Do not promote retryable certification as EnvSolve-Pro's core success algorithm from this gate. Freeze boundary-v5 and its A/B/C implementation as a reproducible baseline and orthogonal treatment.

Before another algorithm change, the next gate must be discussed and preregistered. It should:

1. Use an untouched, outcome-blind random or stratified sample.
2. Include enough actual Official failures to measure discordant A/B/C outcomes.
3. Keep Official Pass@1 as the primary leaderboard metric.
4. Evaluate deployment completeness and resource path quality on separate axes.
5. Add a structured rule only after repeated trajectories identify the same causal failure mode.

No next gate or algorithm change has started.

## Evidence

- Machine-readable aggregate: `experiments/validations/pro_certification_repair_boundary_v5_untouched4_gate_result.json`
- Preregistration: `experiments/validations/pro_certification_repair_boundary_v5_untouched4_preregistration.json`
- Case triplets: `trafilatura`, `gpflow`, `zappa`, and `neuralforecast` result JSON files in `experiments/validations/`
- Frozen implementation: `experiments/protocols/envsolve_pro_certification_repair_boundary_v5_implementation_freeze.json`
