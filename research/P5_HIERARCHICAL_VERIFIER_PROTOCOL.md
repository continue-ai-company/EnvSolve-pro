# P5 Hierarchical Verifier Protocol

## Objective

P5 separates benchmark success from executable environment quality. It does
not modify EnvBench scoring. Instead, it records a V0-V6 verifier curve and
uses source- and metadata-grounded evidence to decide which missing imports are
active repair obligations, inactive platform paths, project-excluded fixtures,
guarded optional features, or unresolved findings.

## Verifier levels

| Level | Contract |
| --- | --- |
| V0 | Bootstrap exits zero. |
| V1 | Declared metadata, installed distributions, and resolver state are consistent. |
| V2 | The unchanged benchmark missing-import check passes. |
| V3 | Package import, entry-point, and CLI smoke probes pass. |
| V4 | Project-native test collection or build succeeds. |
| V5 | An applicable native test subset succeeds. |
| V6 | The same environment plan replays in a fresh container. |

`Official Pass` is computed only from the frozen benchmark contract. `Robust
Pass` requires explicit success at V0-V4 and V6; unknown levels fail closed.
`Native Pass` additionally requires V5 where V5 is applicable. A source
classification never changes V2 or the official score.

## V1 metadata-resolver contract

V1 requires a provenance-matched project distribution, exact `Requires-Dist`
records from its content-addressed metadata, the installed distribution set,
an explicit PEP 508 marker environment, explicitly selected extras, and a
network-disabled direct `python -m pip check` outcome. Names and versions use
PEP 503 and PEP 440 semantics. Inactive markers create no obligation; optional
requirements become active only for an explicitly selected extra.

V1 passes only when every active declared requirement has exactly one
compatible installed distribution. Malformed versions in unrelated ambient
distributions do not fail the project closure. Because bare `pip check` is
environment-wide, a nonzero outcome without project-scoped attribution is
`unknown`, not a project failure. Missing, incompatible, ambiguous, or
malformed evidence inside the active project closure fails. Missing provenance,
marker environment, or resolver evidence produces `unknown`; it never falls
back to the host environment.

## Import evidence

Every `reportMissingImports` finding retains its module, repository-relative
file, zero-based diagnostic line, source hash, and original diagnostic. P5 may
add the following evidence without editing the repository:

- source role: runtime, test, documentation, fixture, build, or vendored code;
- enclosing `try` handler that catches `ImportError`;
- a statically decidable inactive branch under the observed platform/runtime;
- a test skip decorator whose condition is true in the observed environment;
- a default-false optional function branch;
- a repository-owned tool exclusion that matches a fixture path;
- a declared dependency marker that is false in the observed environment.

Source role alone is descriptive and cannot make a finding non-blocking.
Project exclusion applies only to fixture findings and must name the producing
tool and exact repository configuration hash. Platform and branch claims must
be derived from the AST and observed environment facts. Unknown expressions
remain unresolved. A default-false optional branch is restricted to a direct
`if flag` body where the enclosing function declares the literal default
`flag=False`. Defaults such as `port=None` are not observed call arguments and
must not resolve comparisons involving that parameter.

## V3 metadata smoke contract

V3 derives probes only from a content-addressed installed-distribution
snapshot: `METADATA`, explicit `top_level.txt`, and declared console entry
points. It never guesses an import name from a distribution or repository
name. Package and entry-point imports use isolated Python (`-I`) with values
passed as argv. Each console entry point also receives a non-executing
PATH-resolution probe; V3 does not assume that arbitrary CLIs implement
`--help` or `--version`. Probes run without a shell, without network access,
from an empty directory, and with a 30-second timeout.

V3 is three-valued. It passes only when at least one semantic import probe is
planned, all planned outcomes exit zero, all console entry points have import
and CLI coverage, and no metadata is rejected. A nonzero result or timeout is
a failure. Missing provenance, missing outcomes, rejected metadata, or zero
semantic probes produce `unknown`, which fails closed for Robust Pass.

## Repair and scoring boundaries

- Active runtime and test obligations remain repair candidates.
- Documentation findings remain repair obligations when the active verifier
  scanned them; a documentation build is required only when declared applicable.
- Inactive platform findings are not installed into the active environment.
- Project-excluded fixture findings are benchmark-fidelity evidence, not a
  reason to alter the benchmark configuration.
- Guarded optional findings require a feature-specific probe before they can
  contribute to a native capability claim.
- Import stubs, source edits, verifier configuration edits, broad ignores, and
  repository-specific package maps remain prohibited.

## Round 1 scope

Round 1 is a read-only analysis of already consumed Dev-5 artifacts. It makes
no model request and executes no new benchmark case. Synthetic counterexamples
must show that path names alone, unknown platform expressions, unproven
exclusions, and Official Pass without V3/V4/V6 all fail closed.

Canary-20 and Official-Test-100 remain uninspected.

## Development rounds through 9

- Round 1 classified 45 retained findings across the three open Dev-5 cases
  and exposed an unsound use of arbitrary function defaults as runtime values.
- Preregistered Round 2 changed only three Reticulum findings guarded by
  `port != None` from inactive to active. Active repair obligations increased
  from 17 to 20; finding identities and official outcomes did not change.
- Round 3 froze the metadata-derived V3 contract with 14 focused synthetic
  checks. The complete EnvSolve and harness suites passed.
- Round 4 executed five clean source archives in the frozen EnvBench image.
  Three bootstraps succeeded. Poetry passed metadata-derived entry-point import
  and CLI probes after Docker network disconnection. gpkit and Reticulum stayed
  V3-unknown because legacy editable installs provided no PEP 610 direct URL.
  Inflect and pytest-xdist were bootstrap-blocked by Python-hosted wheel read
  timeouts. There were no observed V3 failures, and no official verifier ran.
- Round 5 preregistered and synthetically validated a conservative legacy
  editable provenance path. It requires both a project-targeting `egg-link`
  and uniquely name-matched project-owned `.egg-info`; PEP 610 remains
  preferred. Real validation and the infrastructure-only retries remain open.
- Round 6 ran after explicit network-change confirmation. Inflect recovered and
  passed V3. Poetry remained an unchanged PEP 610 control. Legacy provenance
  matched gpkit and Reticulum, then exposed their `PKG-INFO` metadata format.
  Xdist progressed past its prior download timeout and showed that a Git archive
  lacks VCS state required by setuptools-scm.
- Round 7 froze the V1 metadata-resolver contract with nine focused synthetic
  checks. It claims no real-repository V1 pass; container evidence collection
  remains a later validation round.
- Round 8 added content-addressed `PKG-INFO` support while preserving the exact
  modern `METADATA` hash behavior. Missing installed metadata now produces
  structured unknown evidence rather than aborting the runner.
- Round 9 replaced archive materialization with a clean detached local Git
  checkout, preserving `.git` without reading dirty worktree files or fetching.
  All five Dev-5 bootstraps passed. Twenty-four metadata-derived probes ran
  after Docker network disconnection, producing 5/5 V3 Pass with zero failures,
  unknowns, or collection errors. This is V3 evidence only, not Official Pass.

## Round 10 design-audit remediation

Before further development-case optimization, Round 10 repaired method and
verifier defects found by a complete code review. The constraint engine now
rejects contradictory ordered PEP 440 ranges and consistently excludes
superseded facts. Context observations use event order, including an explicit
`pyenv root` probe instead of executable-layout guessing. V3 fails closed on
partial distribution collection, replaces CLI `--help` execution with entry
point resolution, and V1 scopes malformed-version decisions to the active
project closure. The core shell-trace integration no longer imports the
EnvBench harness, and the V3 host runner no longer assumes `/private/tmp` or
creates an EnvBench result artifact. Event replay is cached and incrementally
applied; full snapshot materialization remains a measured scaling target.

The implementation and harness suites pass 181 tests. Round 9's 24-probe V3
result remains historical evidence for the old CLI convention contract; it is
not silently reused as evidence for the revised Round 10 contract.

The preregistered Round 10 revised-contract replay produced 3/5 bootstrap Pass
and 3/5 V3 Pass. All 21 probes that executed passed, with zero probe failures
and zero collection errors. Inflect stopped before installation because the
frozen bootstrap expected an external `build_output` directory that the
decoupled runner no longer created implicitly. Poetry stopped while installing
build requirements after two `files.pythonhosted.org` read timeouts. These are
recorded respectively as an experimental-fixture mismatch and infrastructure
blocked, not as method failures and not as passes.

The host runner now accepts a preregistered list of safe, collision-checked
pre-bootstrap directories; it contains no repository-name branch or benchmark
result-artifact behavior. After user confirmation of a network change, the
frozen Round 11 replay restored the declared `build_output` fixture and changed
no verifier policy. All five bootstraps passed. Twenty-four metadata-derived
probes then ran with every Docker network disconnected, producing 5/5 V3 Pass,
zero probe failures, and zero collection errors. The three prior passes were
preserved; Inflect and Poetry transitioned from their preregistered fixture and
infrastructure unknowns to V3 Pass, respectively.

Round 11 closes the revised V3 Dev-5 replay requirement only. It is not an
Official Pass or a held-out generalization claim. Real V1, V4, and V6 evidence
remains required, so P5 is not frozen. Canary-20 and Official-Test-100 remain
uninspected.

## Round 12 V1 evidence design

Before any real V1 result is observed, the container collector is fixed to
reuse the same project-distribution provenance and network-isolation policies
as revised V3. It reads exact `Requires-Dist` records from the same
content-addressed installed metadata, records the complete installed
name/version observation set and container marker environment, and directly
executes `python -m pip check` from an empty directory after host-enforced
network disconnection. Selected extras are explicit environment-plan inputs
bound to frozen bootstrap hashes; the collector does not parse repository
names or infer extras.

Round 7's original statement that any nonzero environment-wide `pip check`
directly fails V1 is superseded by the already documented project-attribution
rule. Evaluation first checks the active project closure. A proven missing,
incompatible, ambiguous, or malformed closure requirement fails even when
`pip check` is nonzero. If the project closure is otherwise consistent, a
nonzero bare resolver outcome remains unknown because ambient attribution is
unavailable. Synthetic counterexamples fix this ordering before Round 12.

The preregistered Round 12 replay produced 4/5 bootstrap Pass and 4/5 V1 Pass,
with no V1 failures. Across gpkit, Inflect, Reticulum, and pytest-xdist, 23
active requirements were checked against complete installed name/version
observations. All four direct resolver checks exited zero after Docker network
disconnection, with no timeout or collection error. Explicit extras were empty,
`test`, empty, and `psutil`/`setproctitle`/`testing`, exactly as bound to the
frozen bootstrap hashes. This supplies real V1 evidence for both PEP 610 and
legacy editable provenance.

Poetry failed during bootstrap while downloading `keyring` from
`files.pythonhosted.org`, before any V1 evidence was collected. It remains V1
unknown and infrastructure blocked. Round 13 may perform one identical replay
only after user confirmation of a network change; no V1 policy, bootstrap,
source, timeout, or extras change is permitted.

Round 13 consumed that single retry after user confirmation. The same four V1
passes were reproduced: project metadata hashes, resolver output hashes,
selected extras, active-requirement counts, and decisions all matched Round 12.
Poetry again stopped before V1 collection, this time after an incomplete
`cmake` transfer for the rapidfuzz build system produced `IncompleteRead`,
`ProtocolError`, and `ChunkedEncodingError`. The retry budget is exhausted.
Current real Dev-5 V1 coverage remains 4/5; Poetry remains infrastructure
blocked and unknown. Further work belongs to a preregistered server-side
artifact/cache reliability protocol, not another local retry or a V1 policy
change.

## Round 14 V4 native evidence design

Before observing a real V4 outcome, the V4 planner is restricted to two
project-declared, benchmark-independent entry points. An explicit root
`pytest.ini`, `[tool.pytest.ini_options]` table, or `[tool:pytest]` section plans
direct argv `python -m pytest --collect-only -q -p no:cacheprovider`. Otherwise,
`pyproject.toml` or `setup.py` plans direct argv `python -m pip wheel --no-deps
--no-build-isolation` with output confined to a temporary directory. Test path
names, repository identity, dependency names, tox command strings, and model
output are not planner inputs. Arbitrary project shell commands are never
executed.

Both probes run from the clean temporary project checkout after host-enforced
Docker network disconnection, with `PIP_NO_INDEX=1`, bytecode and pip version
checks disabled, no shell, and a 300-second timeout. Configuration files are
content addressed. Output streams are hashed and only bounded diagnostic tails
are retained. Pytest exit zero passes collection; exit five is unknown because
no applicable tests were observed; other nonzero exits and timeouts fail. A
wheel build passes only on exit zero with at least one content-addressed wheel
artifact. No supported declaration or a missing outcome is unknown. Synthetic
tests fix this three-valued contract before Round 14. The full suite passes 195
tests; no real V4 result has yet been used to tune it.

The preregistered Round 14 replay completed all five bootstraps and produced
5/5 V4 Pass. Gpkit and Reticulum built content-addressed wheels with network
disabled. Inflect, pytest-xdist, and Poetry collected 284, 207, and 1668 tests,
respectively; Poetry also reported 27 deselections. Every observed probe kind,
configuration path, and configuration hash matched its preregistered planner
expectation. No probe timed out or exited nonzero, and no arbitrary project
command was executed. This closes Dev-5 V4 evidence under the two-mode
contract, but does not imply test-body execution, V5, V6, Official Pass, or
held-out generalization.

## Round 15 V6 fresh-replay equivalence design

Before observing paired replay outcomes, V6 is defined as exact equivalence of
two independently bootstrapped fresh-container environment snapshots under one
frozen identity: image ID and digest, platform, repository revision and Git
tree, bootstrap hash, and preregistration hash. Each replay receives a separate
detached checkout, container writable layer, control directory, and temporary
state. No writable volume is shared. Snapshot collection starts only after the
host disconnects every Docker network and the container proves it has no
default route.

The normalized snapshot contains the Python implementation, version,
executable, prefix and base prefix; the full PEP 508 marker environment; the
canonical-name/raw-version multiset of every installed distribution; and every
provenance-matched project distribution's name, version, content-addressed
metadata, provenance kind, and provenance hash. Ordering is normalized but
duplicates are retained. Container IDs, timings, logs, temporary paths outside
the runtime prefixes, and verifier output artifacts are excluded. The snapshot
declares a SHA-256 that the pair runner independently recomputes.

V6 passes only when both complete snapshots have identical hashes and no
structured component delta. A state delta is V6 Fail. Missing bootstrap or
snapshot evidence, collection errors, invalid source/network evidence, reused
container identity, or mismatched frozen replay identities are Unknown. A
single snapshot can never claim V6 Pass. Synthetic equivalence, drift,
tampering, identity, and isolation counterexamples pass; the full suite has 204
tests. No real paired V6 outcome has yet been observed or used to tune this
contract.

The frozen Round 15 command failed before argument parsing or Docker startup:
the directly executed pair-runner file imported `envsolve` before adding the
workspace root to `sys.path`. It created no output root, started zero
containers, made no network request, and observed no V6 outcome. The failure is
retained as a preflight artifact. The runner now initializes its package path
before imports and has a direct-file `--help` regression test. No snapshot or
comparison policy changed. The full suite passes 205 tests. A newly hashed
Round 16 preregistration is required; Round 15 cannot be silently rerun.
