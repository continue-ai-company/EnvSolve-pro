# P6 Two-Layer Import Obligations V1

Status: design preregistration, before implementation and before any new real-case run.

## 1. Research question

Can a benchmark-independent verifier distinguish executable import closure from
static source resolvability, then expose only grounded failures as constraints to
the EnvSolve loop?

This design addresses an objective mismatch observed in consumed development
diagnostics. It does not encode any repository, package, module name, or official
evaluator output.

## 2. Contract

For every bounded, revision-owned absolute import in runtime, test, or build
source, the verifier records two independent obligations:

1. **Runtime-semantic obligation**: the import must execute in the candidate
   environment when the current platform and source control flow make it active.
2. **Static-source obligation**: the imported name must have a statically
   discoverable module, package, extension, namespace package, or type stub on
   the candidate environment's search path.

The layers are evidence, not two repair loops. They are combined into one typed
module finding per source occurrence:

- `active` if either required layer has a grounded `missing` observation;
- `unknown` if no layer is active and at least one required layer is unresolved;
- `inactive` otherwise.

Internal Pass requires zero active and zero unknown findings in both layers.

## 3. Layer semantics

| Source context | Runtime-semantic layer | Static-source layer |
|---|---|---|
| active runtime/test/build import | required | required |
| `try` import guarded by `ImportError` | optional | required |
| compatibility fallback in `except ImportError` | alternative at runtime | required |
| `if TYPE_CHECKING:` import | inactive | required |
| provably inactive target-platform branch | inactive | inactive |
| documentation, fixture, vendored, or generated scope excluded by the frozen inventory contract | out of scope | out of scope |
| syntax or observation ambiguity | unknown | unknown unless independently resolved |

An import that resolves only after executing a dynamic alias is runtime-resolved
but not necessarily static-resolved. Conversely, a stub-only module can satisfy
the static layer without satisfying an active runtime obligation.

## 4. Static resolution

The static resolver is side-effect free. It searches the candidate interpreter's
effective `sys.path` for:

- Python modules and packages;
- PEP 420 namespace-package directories;
- interpreter-supported extension and bytecode suffixes;
- `.pyi` files and `name-stubs` package layouts;
- standard-library modules represented by the interpreter.

It must not import the target module, query a package index, invoke EnvBench, run
Pyright, inspect official outputs, or use learned repository-specific mappings.
Unsupported archive/import-hook layouts are `unknown`, not `missing`, unless a
normal physical search proves the name absent and runtime evidence shows only a
dynamic alias.

## 5. Synthetic counterexamples frozen before code

| ID | Construction | Expected decision |
|---|---|---|
| S1 | active import absent from runtime and static search | active; both layers |
| S2 | active import physically present and importable | inactive |
| S3 | optional `try` import absent | active; static layer only |
| S4 | fallback import absent while primary is runtime-resolved | active; static layer only |
| S5 | import available only through a runtime-created alias | active; static layer only |
| S6 | `TYPE_CHECKING` import backed by a `.pyi` stub | inactive |
| S7 | `TYPE_CHECKING` import absent | active; static layer only |
| S8 | import in a provably inactive platform branch | inactive |
| S9 | active import raises non-missing execution error but is physically present | unknown; runtime layer |
| S10 | unsupported resolver layout with no grounded absence | unknown |

## 6. Acceptance criteria

Implementation is admissible only if:

1. S1-S10 are covered by focused tests without real benchmark cases.
2. Existing semantic import tests, full EnvSolve tests, harness tests, compile
   checks, and the frozen Docker integration test pass.
3. Findings retain per-layer provenance and produce no benchmark-owned feedback.
4. No repository-specific module or distribution mapping is added.
5. A new freeze manifest hashes the implementation, tests, and this protocol
   before any unseen development qualification batch is selected.

## 7. Planned experiment after freeze

After implementation and freeze, preregister a new unseen development batch.
Compare V2 and the two-layer verifier under the same model, budget, candidate DSL,
fresh-container policy, and terminal-only official evaluation. Report internal
Pass calibration, official success, active findings by layer, Unknown rate,
candidate count, wall time, tokens, and cost. Consumed cases remain diagnostic and
cannot be promoted into confirmatory evidence.
