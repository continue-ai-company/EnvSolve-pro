# EnvSolve-Pro Dev Bad-Case Census V1 Casebook

Status: live A-only census record, 2026-08-10

This casebook preserves high-value counterexamples from the frozen 209-case Dev census. Official outcome is primary. Advisory qualification is recorded separately. Infrastructure-censored attempts are not algorithm failures.

## Taxonomy v2 correction (2026-08-30)

The historical labels below predate the separation between deployment mechanisms and
failure causes. They remain unchanged as an audit trail. Under taxonomy v2, hard-boundary
false rejections are **Constraint** failures: the system imposed the wrong admissibility
requirement before the candidate could run. They are not Operation failures. Likewise,
fresh-target facts that never reached the active Agent session are **Observation**
failures, even when the final symptom appeared during Official evaluation.

The 16 non-success trajectories currently yield 13 attributable algorithmic failures:
Observation 6/13, Constraint 5/13, and Operation 2/13. Three intermittent empty-index
events remain unresolved and infrastructure-unknown; they are excluded from the O/C/O
prevalence denominator. This is a provisional single-reviewer annotation over consumed
Dev evidence, not a reliability or effectiveness claim. The auditable record is
`experiments/validations/pro_dev_bad_case_census_v1_taxonomy_v2_annotations.json`.

| Taxonomy v2 layer | Cases | Decisive distinction |
|---|---|---|
| Observation | `ajenti`, `HA-Battery-Notes`, `basxconnect`, `clarity`, `graphium`, `hark` | The decisive target-state fact was unavailable or was not returned before the Agent stopped. |
| Constraint | `bigbang`, `uer-py`, `django-machina`, `phobos`, `androidviewclient` | An encoded hard boundary imposed an incorrect admissibility requirement. |
| Operation | `quacc`, `micropy-cli` | The requirement was known and active, but the delivered program did not satisfy it. |
| Unresolved / infrastructure-unknown | `plugin.video.netflix`, `cvxportfolio`, `evox` | The evidence cannot separate an intermittent package-index event from algorithm behavior. |

## Exposure correction (2026-08-24)

The earlier pending-state summary was incomplete because it considered the A-only census
more narrowly than the full research history. A cross-store audit of local artifacts,
historical artifacts, committed result records, and Spark artifacts found prior execution
evidence for 203 of the 205 cases in the pending-census file. The only cases for which no
execution evidence was found are `fonttools/fontbakery` (position 70) and
`vertica/verticapy` (position 196). They are reserved and must not be used for ROL
mechanism development.

The four recently resumed A cases were already exposed before ROL and are development
evidence only. BayBE, PortingDB, and pywal16 pass Official. Reddit2telegram's first
Official attempt was censored by package-index DNS failure; one exact-script,
evaluation-only retry passes Official. The updated A snapshot is 54 terminal episodes:
32 passes and 11 failures among 43 non-censored Official-primary outcomes, 6 terminal
infrastructure-censored cases, and 5 pre-Official algorithm failures. This correction
supersedes the stale Pending adjudication and Current census snapshot text below without
rewriting the historical record. The machine-readable evidence is
`experiments/validations/envsolve_pro_v2_case_exposure_audit_20260824.json`.

## Confirmed Official failures

| Case | Terminal mechanism | Current taxonomy hypothesis | Why it matters |
|---|---|---|---|
| `Quantum-Accelerators/quacc` | `tblite` metadata/build failure because the Linux ARM environment lacks a usable LAPACK configuration | Operation: native/system dependency realization | The Agent recovered from an earlier network timeout but stopped at a deterministic architecture-specific build obligation. |
| `ajenti/ajenti` | Build isolation could not resolve the required setuptools environment | Constraint: build-backend and isolation compatibility | Installing project requirements is insufficient when the isolated build environment has a different dependency frontier. |
| `andrew-codechimp/HA-Battery-Notes` | `ulid-transform` build isolation could not resolve Cython | Constraint: transitive build-time dependency | Runtime dependency reasoning did not cover a transitive source-build requirement. |
| `basxsoftwareassociation/basxconnect` | `setuptools_scm` failed on Git dubious ownership in the fresh Official container | Observation/Operation: clean-replay ownership drift | The construction container succeeded, but the submitted program did not normalize a deployment fact that changed across clean environments. |
| `bradenm/micropy-cli` | Bootstrap completed, but Official Pyright retained one `reportMissingImports` for the repository's own nonexistent `micropy.cli` module | Constraint/Operation: known unsatisfied constraint without an admissible realization | The Agent observed the same missing import before submission and verified that a temporary synthetic stub could remove it, but correctly removed that prohibited source-tree artifact and submitted without a legal replacement. The other 310 Pyright errors are non-scoring diagnostics. |
| `castagnait/plugin.video.netflix` | After one infrastructure-censored retry, the terminal Official bootstrap failed because pip returned no versions for `setuptools` | Causal attribution unresolved; likely upstream index resolution | Frozen Official policy counts this as Fail, but the package is known to exist and its metadata was reached in the first attempt. Keep it in the Official denominator, but do not use it to motivate an algorithm rule. |
| `claritychallenge/clarity` | `setuptools_scm` failed on Git dubious ownership in the fresh Official checkout before Pyright ran | Observation/Operation: clean-replay ownership drift | This independently repeats the `basxconnect` mechanism. Advisory replay passed because its checkout ownership semantics differed from Official, exposing a concrete fidelity gap in the current replay tool. |
| `cvxgrp/cvxportfolio` | The isolated build environment returned no available versions for `setuptools` before Pyright ran | Causal attribution unresolved; likely upstream index resolution | Frozen Official policy counts this as Fail because no recognized infrastructure signature was present. Construction had installed the same project, so this repeats the ambiguity seen in `plugin.video.netflix`; do not use it to motivate an algorithm rule without deterministic reproduction. |
| `datamol-io/graphium` | Editable installation failed when `setuptools_scm` encountered Git dubious ownership in the fresh Official checkout | Observation/Operation: clean-replay ownership drift | This is the third independent occurrence of the `basxconnect`/`clarity` mechanism. The submitted path also exposed PopTorch source as a static namespace without installing an executable SDK, so both replay correctness and deployment completeness failed. |
| `econ-ark/hark` | Editable metadata generation failed when `setuptools_scm` encountered Git dubious ownership in the fresh Official checkout | Observation/Operation: clean-replay ownership drift | Construction and advisory fresh replay both passed, but neither reproduced Official checkout ownership. This is the fourth primary Official failure and fifth independent reproduction of the ownership mechanism when the Bigbang counterfactual is included. |
| `emi-group/evox` | Official build isolation returned no available version for `setuptools>=61.0` after the same exact script passed advisory fresh replay | Causal attribution unresolved; likely upstream index resolution | Frozen Official policy counts this as Fail, but it repeats the intermittent empty-setuptools candidate set seen in `plugin.video.netflix` and `cvxportfolio`. Do not use it to motivate an algorithm rule without deterministic reproduction. |

## Confirmed pre-Official system failure

| Case | Terminal mechanism | Current taxonomy hypothesis | Why it matters |
|---|---|---|---|
| `datactive/bigbang` | The strong Agent completed 31 commands and returned a bootstrap program, but frozen candidate policy v5 rejected writes to `pyproject.toml` and `setup.cfg` under a variable assigned by `mktemp -d` | Operation: conservative candidate-boundary false positive | This is direct evidence that structured safety constraints can suppress a strong Agent. The exact-program counterfactual also failed on fresh-checkout Git dubious ownership, so the false positive did not cost a benchmark pass on this case. |
| `dbiir/uer-py` | The Agent returned a program that symlinked TensorFlow's installed `python/keras` directory to `tensorflow/keras`; frozen candidate policy rejected symbolic links inside Python import search directories | Operation: third-party import-layout mutation rejected | The exact rejected program subsequently passed a fresh non-scoring Official diagnostic with zero issues. A remains Fail by preregistration, but this proves that the categorical v5 boundary removed a benchmark-capable path. |
| `ellmetha/django-machina` | The Agent returned a program that created an empty `tests/settings_local.py` after real dependency installation; frozen candidate policy rejected direct materialization of an importable artifact | Operation: project-local configuration artifact rejected | The exact rejected program subsequently passed a fresh non-scoring Official diagnostic with zero issues. A remains Fail by preregistration, but this is the second proven benchmark pass lost to categorical pre-execution rejection. |
| `dfki-ric/phobos` | The Agent installed substantial real dependencies and generated two local `.pyi`-only distributions; frozen candidate policy rejected direct materialization of importable type-stub artifacts | Operation: generated type-stub artifact rejected | The exact-program diagnostic failed earlier on fresh-checkout Git dubious ownership, so this case cannot establish whether the boundary cost an Official pass. It independently raises deployment-completeness concerns and is the sixth ownership reproduction. |
| `dtmilano/androidviewclient` | The Agent packaged empty Python-2 GUI compatibility modules and behaviorless Android MonkeyRunner classes into a local wheel; frozen candidate policy rejected direct importable-artifact materialization | Operation: synthetic legacy-import wheel rejected | The exact rejected program passed fresh non-scoring Official with zero issues. This is the third proven benchmark pass lost to categorical rejection, while also being a clear incomplete-deployment path. |

## Confirmed Official passes with diagnostic value

| Case | Official outcome | Diagnostic value |
|---|---|---|
| `adamchainz/django-mysql` | Pass | A straightforward strong-Agent success under Linux ARM. |
| `ansible/molecule` | Pass | Advisory qualification failed while Official passed, proving advisory validity must remain separate from the benchmark outcome. |
| `astropy/reproject` | Pass | A complex scientific stack passed Official despite an advisory artifact concern. |
| `alteryx/featuretools` | Pass after one exact-script network retry | The initial `files.pythonhosted.org` timeout was infrastructure censoring, not an algorithm failure. |
| `automl/neps` | Pass | A 37-command continuous Agent trajectory and clean replay succeeded, making this a path-cost and minimization case rather than a success-repair case. |
| `beeware/briefcase` | Pass | A 12-command trajectory and short two-line submitted program passed clean replay and Official, providing a comparatively efficient success path. |
| `benthayer/git-gud` | Pass | Advisory qualification rejected an installation artifact, but the frozen script passed Official with zero issues. This is evidence for refining the audit boundary, not evidence of an algorithm failure. Its 148 Pyright errors are non-scoring diagnostics. |
| `brainglobe/brainrender` | Pass | Advisory qualification reported that the candidate did not return control, while the same frozen program passed Official. This is a second qualification false negative and a useful boundary-calibration case. |
| `bottlecapdave/homeassistant-octopusenergy` | Pass | Agent generation and clean replay passed. Official also passed with 1,299 non-scoring Pyright errors, reinforcing that total error count is not the benchmark objective. |
| `cantools/cantools` | Pass; deployment completeness flagged | The program created an empty `site-packages/StringIO` namespace rather than installing executable `StringIO` behavior. It satisfied the Official missing-import objective but is retained as a metric-aligned, incomplete-environment counterexample. |
| `bradyajohnston/molecularnodes` | Pass; deployment completeness flagged | A 30-command, 1.49M-input-token path retagged a cp37 `pyopenvdb` wheel as py3-any and used `fake-bpy`. Official reported zero missing imports, while runtime compatibility remains unestablished. |
| `censys/censys-python` | Pass | A 9-command, 213K-input-token path used an ordinary editable install, passed clean replay in 42 seconds, and passed Official in 31 seconds. This is an efficient, comparatively complete success path. |
| `cherrypy/cheroot` | Pass | Advisory clean replay retained 32 missing imports after a transient docs-extra resolution failure, while the exact frozen script passed Official. This seventh false negative shows replay evidence must be classified and returned to the Agent, not used as a hard submission gate. |
| `calliope-project/calliope` | Pass | The program installed GLPK, created a Python 3.10 venv, installed the project and development dependencies, then passed both clean replay and Official. It is a comparatively complete system-plus-Python success path. |
| `cda-tum/mqt-bench` | Pass | A 22-command trajectory resolved a historical `pytket`/`pytket-qiskit` incompatibility with an explicit pin, passed clean replay in 164 seconds, and passed Official with zero missing imports. Its 114 other Pyright errors are non-scoring. |
| `ceph/ceph-ansible` | Pass; deployment completeness flagged | The program repackaged tracked `module_utils/ca_common.py` into an undeclared inline wheel under Ansible's namespace. Official accepted the resulting zero-missing-import environment, while advisory provenance rejected it. This is a metric success but not evidence of complete Ceph-Ansible runtime deployment. |
| `cityofzion/neo3-boa` | Pass; deployment completeness flagged | The program installed an empty synthetic `boa3-stubs` wheel for an import used by a legacy negative-test fixture. Advisory and Official both reported zero missing imports, while Official retained 5,796 non-scoring errors. The audit missed the wheel because its declared top-level token was not a Python identifier; this is metric success, not a complete runtime deployment. |
| `conan-io/conan-package-tools` | Pass; deployment completeness flagged | A 25-command path installed Conan 1.6.1 and then overlaid Conan 1.66.0, preserving historical internal modules beside newer files. Fresh replay and Official passed, but runtime version coherence is not established. |
| `couchbase/cbmonitor` | Pass; deployment completeness flagged | A short 12-command path replaced the legacy dependency set with current packages including Django 6.1. Official passed with zero missing imports, while advisory replay was a false negative; compatibility with the old application is untested. |
| `de7vid/klingon-assistant-data` | Pass | A 10-command, 153K-input-token path used an ordinary virtual environment, installed declared requirements plus two imported packages, and passed both clean replay and Official. It is a useful efficient-path control. |
| `democracyclub/uk-polling-stations` | Pass | The program installed all documented requirement groups plus imports found during construction, derived ignored local settings from a tracked sibling template, and passed both fresh replay and Official. Official retained 2,620 non-scoring errors across 733 files, a strong example of the narrow benchmark objective. |
| `democracyclub/everyelection` | Pass | A 27-command path installed the broad Django, CDK, and test dependency set plus two pinned DemocracyClub packages, derived local settings from a tracked example, and passed both clean replay and Official. It is a comparatively complete success path, although runtime services remain untested. |
| `diefenbach/django-lfs` | Pass; deployment completeness flagged | The program compiled CPython 2.7 and exposed its hotshot sources and cStringIO extension on Python 3.13 PYTHONPATH. Official accepted zero missing imports while retaining 1,284 non-scoring errors; this is metric success without evidence of cross-runtime executability. Advisory replay was a network false negative. |
| `dnarayanan/powderday` | Pass; deployment completeness flagged | A 66-command, 2.74M-input-token path installed a large scientific stack, then created empty namespace directories for unresolved legacy imports. Clean replay and Official passed, but the empty paths make this a strong metric-success versus executable-deployment counterexample. |
| `eastsidepreparatoryschool/epschedule` | Pass; deployment completeness flagged | A 25-command trajectory installed the named import-bearing distributions with `--no-deps`, passed clean replay in 52 seconds, and passed Official in 19 seconds. The missing-import objective is satisfied, but transitive runtime completeness is not established. |
| `dj-stripe/dj-stripe` | Pass | A conventional local venv and editable project installation passed clean replay and Official. The path has no trajectory-level completeness red flag, although runtime services remain untested. |
| `ecds/readux` | Pass after one exact-script network retry | The first Official attempt was censored by a `files.pythonhosted.org` read timeout. The unchanged retry passed with zero missing imports, while advisory provenance incorrectly rejected a requirements-declared editable dependency checkout. |
| `facebookresearch/hydra` | Pass; deployment-policy boundary flagged | A 52-command, 2.62M-input-token path built a Python 3.10 environment with broad real dependencies and changed two committed ANTLR-generated files from `typing.io` to `typing`. Official passed, while advisory repository-effect policy rejected the tracked changes. This separates generated-source compatibility repair from ordinary environment installation. |

## Terminal infrastructure-censored cases

| Case | Evidence | Disposition |
|---|---|---|
| `ai4co/rl4co` | Both Official attempts ended in `files.pythonhosted.org` read timeouts | Excluded from the pass numerator and algorithm-failure denominator; no further replacement retry. |
| `astropy/regions` | Initial Conda package read timeout; retry ended in `CondaHTTPError: HTTP 000 CONNECTION FAILED` | Excluded from the pass numerator and algorithm-failure denominator; no further replacement retry. |
| `cclib/cclib` | Initial Conda package download ended in `ReadTimeoutError`/`IncompleteRead`; the exact-script retry ended in `CondaHTTPError: HTTP 000 CONNECTION FAILED`, both before Pyright | Excluded from the pass numerator and algorithm-failure denominator; no further retry. The trajectory remains useful for deployment-completeness analysis because it copied Python-2-era PyQuante files into Python 3.13. |
| `convexengineering/gpkit` | The initial attempt received package bytes with a mismatched hash; the sole exact-script retry received a truncated PyPI JSON response, both before Pyright | Excluded from the pass numerator and algorithm-failure denominator; no further retry. The trajectory remains valuable because the Agent replaced the current Pyright with `pyright==1.1.320` after the current verifier found one missing `distutils.core` import, exposing verifier-identity manipulation as a separate measurement risk. |
| `columnflow/columnflow` | The initial Official attempt ended in a Conda HTTP 000 connection failure; the sole exact-script retry ended while cloning cmsdb with a GnuTLS receive error, unexpected disconnect, early EOF, and invalid index-pack output | Excluded from the pass numerator and algorithm-failure denominator; no further retry. The unpinned runtime clone and `root_base --no-deps` remain separate robustness and completeness concerns. |
| `eggpi/citationhunt` | Both exact-script Official attempts ended with Conda HTTP 000 while fetching defaults/conda-forge repodata, before project installation or Pyright | Excluded from the pass numerator and algorithm-failure denominator; no further retry. Advisory fresh replay reached zero missing imports but separately misclassified conda-forge build-origin metadata as local provenance. |

## Pending adjudication

- No A episode is active. `emdgroup/baybe` and `fedora-python/portingdb` are frozen as the next outcome-blind lane 1 and lane 2 cases but have not started. Hydra, CitationHunt, and Readux are terminal. Earlier generic-runner invocations were withdrawn by the remote-runner invocation correction and do not count as A episodes.
- `commaai/comma10k` has not entered an Agent session: its single shallow-fetch working state has grown to approximately 14 GB and remains active on Spark after the 600-second SSH acquisition timeout. No duplicate fetch has been started; adjudication waits for the original acquisition to complete into the immutable source cache.

## Current research signal

The strongest repeated deterministic failure mechanism is clean-replay ownership drift: `basxconnect`, `clarity`, `graphium`, and `hark` fail in their primary Official runs, while the non-scoring Bigbang and Phobos counterfactuals independently reproduce the same mechanism. Six independent reproductions show that the current advisory replay's checkout semantics are systematically too weak. A second contradiction now has three independent causal examples: the exact programs rejected for UER-Py, django-machina, and AndroidViewClient all pass Official, proving that categorical operation-layer guards suppress benchmark-capable strong-Agent repairs across third-party layout repair, project-local configuration, and synthetic compatibility packaging. AndroidViewClient also shows why removing all checks is insufficient: its Official-pass path supplies almost no executable legacy behavior. Phobos remains causally unresolved because ownership stopped its counterfactual before the rejected type stubs were exercised. Together these observations favor an Official-equivalent in-session replay plus post-execution provenance/effect checks, with benchmark success and deployment completeness reported separately. The A-only census still continues before treatment selection.

## Current census snapshot

Fifty A episodes now have terminal outcomes. Among the 39 cases with non-censored Official-primary outcomes, 28 pass and 11 fail; 6 additional cases are terminally infrastructure-censored, while Bigbang, UER-Py, django-machina, Phobos, and AndroidViewClient are five pre-Official algorithm failures caused by the frozen candidate boundary. The previously reported 29-trajectory resource snapshot had a command-count median of 24 with range 6-77 and an input-token median of 685,007 with range 141,263-4,435,262; resource statistics will be recomputed atomically now that this batch is closed. These are observations, not stopping thresholds. Four generic-runner launch errors are explicitly excluded by the remote-runner invocation correction.

Advisory clean replay is not a reliable substitute for Official: among the 38 non-censored outcomes with a binary advisory result it has 16 true positives, 6 true negatives, 12 false negatives, and 4 false positives. Its current agreement with Official is therefore 22/38; `cvxportfolio` is excluded because advisory replay was unavailable after a control-plane transport timeout. Pre-Official boundary failures and their non-scoring counterfactuals are not part of this matrix. This supports classifying and returning replay evidence to the Agent as an observation while retaining Official as the primary outcome; it does not support using advisory qualification as a hard submission gate. The repeated ownership, provenance, and repository-effect mismatches additionally show that replay evidence is only useful when it reproduces target semantics and distinguishes path-quality concerns from benchmark failure.

## Provisional three-layer failure matrix

| Case | Observation layer | Constraint layer | Operation layer | Submission-time evidence |
|---|---|---|---|---|
| `quacc` | The trajectory encountered source builds and architecture-specific packages. | A usable LAPACK provider was required by `tblite`. | The program installed compilers and CMake but not LAPACK. | No passing execution of the exact submitted program. |
| `ajenti` | Construction succeeded in an accumulated environment; fresh replay entered an isolated build environment. | The isolated environment independently needed setuptools. | The program upgraded setuptools only in the parent venv and did not control build isolation. | Fresh replay failure was generated after the Agent session and not returned to it. |
| `HA-Battery-Notes` | Construction reported zero missing imports; fresh replay rebuilt `ulid-transform`. | The isolated source build independently needed Cython. | The program installed requirements conventionally and did not make the build dependency reproducible. | Fresh replay failure was generated after the Agent session and not returned to it. |
| `basxconnect` | The checkout ownership differed between construction and Official replay. | Git provenance inspection required the new checkout to be trusted. | The program installed the package but did not normalize Git safe-directory state. | The Agent verified only the accumulated construction state. |
| `micropy-cli` | The Agent directly observed the remaining nonexistent `micropy.cli` import. | The goal remained unsatisfied under the admissibility boundary. | A synthetic stub worked but was prohibited; no legal replacement was found. | The Agent explicitly submitted a known-unsatisfied constraint. |
| `clarity` | Advisory replay and Official used different checkout ownership semantics. | `setuptools_scm` required Git to trust the Official checkout. | The submitted program did not normalize `safe.directory`. | The only exact-program replay seen by the Agent-equivalent workflow passed, so the differing Official fact remained unobserved. |
| `graphium` | Construction observed a root-owned checkout, while Official evaluated a fresh checkout under different ownership semantics. | Editable build metadata required Git provenance and therefore a trusted checkout. | The program installed dependencies and exposed PopTorch source but did not normalize `safe.directory`. | The post-session advisory rejected a different installation-integrity issue and was never returned to the Agent; the Official ownership failure remained unobserved. |

The shared hypothesis is therefore **submission without replay proof**, not a shared package-manager rule. The minimal candidate treatment is an in-session tool that executes the exact current program in a fresh environment, returns the last deterministic unsatisfied constraint, and lets the same Agent revise the program. This hypothesis is frozen only for future comparison; the A-only census continues outcome-blind before treatment selection.
