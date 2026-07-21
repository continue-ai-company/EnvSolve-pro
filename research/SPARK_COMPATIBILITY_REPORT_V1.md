# EnvSolve-pro DGX Spark Compatibility Report V1

## Scope

This check asks whether the frozen EnvSolve-pro snapshot can execute on the DGX Spark before using the host for parallel P0 experiments. It does not claim model effectiveness and does not inspect held-out EnvBench outcomes.

- Source revision: `3eef2fdf73a06d1dd5fc3f8860b2b73b7fc98614`
- Host: NVIDIA DGX Spark 7.3.1, Ubuntu 24.04.3, `aarch64`
- Accelerator: NVIDIA GB10, driver 580.95.05
- Runtime: Docker 28.5.1, Python 3.13
- EnvBench image: present locally as an ARM64 image

## Findings

The first full test run completed with 418 passes, 5 failures, and 2 skips. The five failures reproduced unchanged on the Mac and were therefore not Spark or ARM64 regressions:

1. One P5 test reconstructed a historical freeze from ignored raw run artifacts.
2. One P6 test compared a historical freeze against the evolving EnvSolve-pro worktree.
3. Three V0 tests hard-coded a repository-local `EnvBench/.venv/bin/python` path.

The portable core, excluding those three test modules, completed with 417 passes, 2 skips, and 75 passing subtests. Docker can start the exact EnvBench image, and an NVIDIA-enabled container sees the GB10.

## Portability Fix

The tests now use the active test interpreter, audit P5 from committed evidence, and audit P6 against its immutable freeze revision rather than current source. `requirements-test.txt` records the dependency set used for cross-host reproduction. These changes do not alter the observation, constraint, operation, verifier, or model policies.

After pinning those dependencies and deferring EnvBench-only imports until an actual
V0 episode starts, the complete suite passed identically on both hosts: 424 passed,
2 skipped, and 75 subtests passed. The skips are pre-existing optional tests rather
than architecture-specific failures.

## Remaining Boundary

This establishes source, Python, Docker, ARM64, and GPU-container compatibility. A live Spark episode remains necessary to validate end-to-end model access, repository acquisition, candidate execution, and official evaluation under the same frozen P0 protocol.
