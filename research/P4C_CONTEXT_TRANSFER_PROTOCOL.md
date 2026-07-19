# P4C Image-Provenance Context Transfer Protocol

## Purpose

P4B observes case-independent capabilities of a frozen evaluator image. P4C
permits those observations to support a development-case repair only when a
complete provenance chain proves that the case ran in the identical image.

P4C is additive and does not modify P0 through P4B frozen semantics.

## Required lineage

A transfer requires three independently auditable artifacts:

1. the original case run manifest and audit;
2. the derived P3 constraint state and its raw-result source hash;
3. the P4B case-free context state and image-inventory summary.

Transfer is allowed only when:

- repository and revision in the case manifest equal the P3 state identity;
- the original raw result still matches the SHA256 recorded by P3;
- the source and target states independently reconstruct and audit;
- image reference, image ID, and repository digests match exactly between the
  original case run and P4B inventory;
- the local image still resolves to the frozen image ID;
- every transferred item is a high-confidence structured context evidence item
  selected by the frozen P4B builder.

Any mismatch rejects the complete transfer before the target trajectory is
modified.

## Derived state

The P3 event log is copied to a new development artifact; the frozen source is
never edited. Transferred evidence receives deterministic target-local IDs and
records source case ID, source snapshot hash, image identity, and source
evidence ID. The target repository profile records hashes for every lineage
artifact. Repeating the same transfer is idempotent.

## Development runtime validation

After transfer, the frozen P4A registry may generate a runtime plan using only
constraints and transferred context evidence. P4C preregisters one
development-only validation on the already consumed `automl/neps` conflict:

- expected selected runtime: highest observed version satisfying
  `<3.12,>=3.8`, currently `3.11.7`;
- mutation: frozen P4A `pyenv local <version> && hash -r` action;
- independent probe: `python --version`;
- execution contract: derive the `pyenv` root from the selected structured tool
  observation, require its Python shim to be executable, and prepend its shims
  directory to `PATH` for every repair and verification action;
- execution image: the exactly matched evaluator image;
- container isolation: network disabled and no repository mount.

The validation tests only the runtime state transition. It is not an EnvBench
run, does not install the repository, and cannot be counted as Official Pass,
Robust Pass, or end-to-end Dev success.

An initial diagnostic trajectory (`p4c-neps-runtime-transfer-v1`) is retained
as a negative result: `pyenv local 3.11.7` succeeded, but the image's Conda
directory preceded pyenv shims in `PATH`, so the independent probe still saw
Python 3.13.2. The v2 execution contract is a generic response to this missing
runtime-manager activation semantics; it does not change the frozen repair
plan or specialize on the development repository.

## Integrity rules

- Dev evidence may guide development but not confirm generalization.
- No repository identifier appears in transfer or repair selection code.
- No context value is copied across different image identities.
- Requirements remain immutable; only the contradicted observed runtime fact
  may become `superseded` after the independent probe succeeds.
- Canary-20 and Official-Test-100 remain uninspected.

## P4C exit criterion

P4C is complete when matching-lineage transfer, mismatch rejection,
idempotence, selected-evidence filtering, derived-state audit, runtime-plan
preflight, and verification-gated runtime transition pass; all prior freezes
remain valid; and the development result is reported with its limited scope.
