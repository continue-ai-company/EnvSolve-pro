# EnvSolve-Pro Certification-Repair Boundary v2 Casebook

This casebook records high-value development mechanisms while the frozen Dev-8 batch is running. It is not a substitute for the final paired analysis, and no single case may trigger an algorithm change.

## Case 1: `astropy/reproject`

**Frozen outcome:** A (strong Agent control) passed Official EnvBench; B (one-shot certification) passed; C (retryable clean replay) passed its first internal clean replay, but its Official result remained infrastructure-unknown after one timeout and two independent package-download integrity failures.

| Arm | Official state | Commands | Input tokens | Clean replays |
| --- | --- | ---: | ---: | ---: |
| A | Pass | 25 | 603,274 | 0 |
| B | Pass | 8 | 224,180 | 1 (first pass) |
| C | Unknown | 22 | 656,309 | 1 (first pass) |

The non-scoring Pyright error count was 272 for both A and B, while the official missing-import count was zero. This confirms that the harness followed the official EnvBench objective rather than optimizing unrelated diagnostics.

### Mechanism observations

1. A recovered from ordinary shell feedback without a clean-replay API. It created a new virtual environment inside the construction container, disabled pip's local cache, and verified zero missing imports. That venv still shared the already-built source directory, so it was not equivalent to a fresh checkout.
2. B found one missing module after the broad project extras install, added `pytest-astropy-header`, and passed its only clean replay on a fresh checkout. Its certificate did not change the binary success outcome relative to A in this case.
3. C also passed its first clean replay. Therefore the retryable loop was dormant: there was no failed certificate from which to learn and no feedback-conditioned repair.
4. B used fewer commands and tokens than A and C in this trajectory, but source-cache and network conditions differed. These resource numbers are descriptive until the paired batch closes.
5. Package-download hash mismatches were classified as infrastructure only when pip reported an unknown artifact differing from package-index SHA-256 metadata before Pyright ran. Named user requirement hash errors remain deployment failures.

**Decision:** keep boundary v2 and all three algorithms frozen; continue to the next preregistered case.

Machine-readable evidence: `experiments/validations/pro_certification_repair_boundary_v2_dev8_block1_result.json`.

## Case 2: `cda-tum/mqt-bench`

**Frozen outcome:** A and the effective B replacement passed Official EnvBench. C passed its first internal clean replay, but its submitted script later failed under the Official evaluator when pip could not resolve `types-pkg-resources` while backtracking over `pytket` versions.

| Arm | Official state | Commands | Input tokens | Clean replays |
| --- | --- | ---: | ---: | ---: |
| A | Pass | 9 | 224,699 | 0 |
| B | Pass | 10 | 269,993 | 1 (first pass) |
| C | Fail | 12 | 434,501 | 1 (first pass) |

A and B both had zero scoring missing imports and 114 non-scoring Pyright errors. C's bootstrap exited before Pyright, so no comparable non-scoring error count was produced.

### Mechanism observations

1. A used ordinary construction-container feedback to select Python 3.12, install project development dependencies, and reach zero missing imports. It passed the later Official execution without a clean-replay API.
2. B reduced 162 initial missing imports to zero, submitted a four-line environment program, and passed both its single fresh replay and the Official evaluator. Its certificate again did not improve binary success relative to A.
3. C also passed its only fresh replay. Its retryable loop therefore never activated. The later Official failure was unavailable to the Agent and cannot be repaired by an in-session retry interface.
4. C's internal certificate and Official execution used the same source revision and image but obtained different dependency-resolution outcomes. One successful replay is evidence of executability at one point in time, not a proof of repeatability for an unpinned environment program.
5. The first B process made six read-only calls and then showed no semantic progress for at least 2,058 seconds. It was censored before any candidate or replay outcome and replaced under a frozen amendment. The effective replacement ran from an empty Agent session and passed; the censored attempt is excluded from success, token, and time denominators.
6. B used 20% more input tokens than A in this trajectory, while C used 61% more than B. These resource values are descriptive because the effective B arm was a preregistered replacement executed later.

**Decision:** keep the Dev-8 algorithms frozen. Continue the batch, while recording repeated certification or dependency-resolution stabilization as a later orthogonal treatment rather than patching this case.

Machine-readable evidence: `experiments/validations/pro_certification_repair_boundary_v2_dev8_block2_cli147_result.json` and `experiments/validations/pro_certification_repair_boundary_v2_dev8_block2_cli147_adjudication.json`.

## Case 3: `valory-xyz/trader` (Boundary Calibration Only)

**Statistical decision:** exclude this case from the A/B/C effect estimate. All arms discovered the project-native `autonomy packages sync` operation and reduced 241 missing imports to zero. Boundary v2 nevertheless rejected 299 Python files generated by that package manager under the repository lock. C then hid its operation history by creating and deleting a temporary `setup.py`, causing the old boundary to reward an inadmissible path.

Boundary v3 changes only the measurement object, not the three Agent interfaces:

1. audit the state produced by the submitted program in a fresh environment, not exploratory residue in the construction container;
2. reject temporary writes to protected build, dependency, or verifier configuration even when later deleted;
3. admit generated dependencies only when the repository declares the operation, the lock matches the selected revision, and the package manager verifies it;
4. admit standard `virtualenv` runtime hooks only when their version and bytes match a distribution template recorded before candidate execution;
5. qualify A after its session without returning feedback, while B and C retain one-shot and retryable Agent-visible replay respectively.

### Qualification

- A's exact program passes on Linux ARM Spark: zero official missing imports, 299 lock-verified package files, and content-verified standard `virtualenv` hooks.
- B's exact program passes under the immediately preceding v3 implementation. Two executions under the final hash are network-censored before the trusted goal; the final Git-mount change is exercised by both full A and an independent Linux ARM mount test.
- C's exact fourth program is rejected before execution at `cat > setup.py`.
- The full suite reports 735 passed and 8 skipped tests, plus 76 passing subtests.

**Decision:** freeze boundary v3. Treat the first three exposed repositories only as pilot and boundary-calibration evidence. Run 15 A/B/C episodes on the five unexecuted repositories retained from the original outcome-blind order. No algorithm change is allowed until all effective episodes and aggregate trajectory error analysis are complete.

Machine-readable evidence: `experiments/protocols/envsolve_pro_certification_repair_boundary_v3_implementation_freeze.json` and `experiments/validations/pro_certification_repair_boundary_v3_untouched5_preregistration.json`.

## Case 4: `pypa/distutils` (Build-Provenance Calibration Only)

**Statistical decision:** stop the first Untouched Dev-5 block before B and exclude the
repository from all method estimates. C and A both passed Official evaluation. Boundary
v3 nevertheless accepted C's tracked-source native extension under `/tmp` while rejecting
A's equivalent extension under repository `build_output`; it also rejected 106 exact
Python source copies emitted by A's standard build command.

A preregistered native-only boundary v4 accepted the extension but failed because all 106
source copies remained invalid. The version was preserved as a failed calibration rather
than patched in place. Boundary v5 then introduced one repository-agnostic rule: exact
Python copies must match committed bytes and preserve the committed source path as a
suffix; native extensions must correspond to a module provider declared in committed
native source. Modified, renamed, direct, and source-less artifacts remain invalid.

The exact A and C programs were replayed in separate fresh containers with no model or
Official evaluator calls. A qualified with 106 committed-source copies and one repository
native artifact. C qualified with one external native artifact. Both produced zero
missing imports, zero novel unowned import artifacts, and zero remaining repository
violations. Mac full regression passed 759 tests; Spark Linux ARM passed all 24 focused
v4/v5 tests with matching source hashes.

**Decision:** freeze boundary v5 as shared measurement infrastructure. Resume A/B/C only
on the four unopened repositories at case positions 2-5, covering episode positions 4-15
of the boundary-v3 schedule. This case validates the boundary and contributes no evidence
that retryable replay outperforms either control.

Machine-readable evidence:
`experiments/validations/pro_certification_repair_boundary_v5_distutils_consumed_calibration_adjudication.json`
and
`experiments/protocols/envsolve_pro_certification_repair_boundary_v5_implementation_freeze.json`.
