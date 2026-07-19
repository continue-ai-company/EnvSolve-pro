# Typed Replay IR v7 and Complete Candidate v4

## Purpose

This revision closes two generic candidate-language defects found before any
confirmatory run. It changes executable coverage and runtime binding, not the
constraint solver, verifier, model, budget, or benchmark evaluator.

Replay policy identifier: `typed-replay-ir-v7`.

Complete-candidate policy identifier:
`complete-candidate-v4+typed-replay-ir-v7`.

## Changes from v6

First, bounded PDM dependency mutations are admitted as Python package-install
actions. The accepted forms are `pdm install`, `pdm sync`, and their
`python -m pdm` variants. Arbitrary PDM scripts, publishing, dry runs, unknown
subcommands, shell substitution, and control flow remain rejected.

Second, candidate validation gives project virtual environments a semantic
identity. Creation and activation must both resolve to the project-root
`.venv` or `venv`, and activation must follow creation. A command such as
`cd tools && python -m venv .venv` cannot be matched to project-root activation
merely because both strings end in `.venv`.

## Generalization boundary

The rules inspect command semantics only. They contain no repository, package,
module, benchmark split, or evaluator outcome. PDM support follows a public
package-manager interface; virtual-environment binding follows effective path
identity. The consumed Q5 Giskard trajectories are used only for read-only
validation that previously rejected PDM candidates now enter the executable
language. They are not rerun and provide no effectiveness estimate.

## Validation

The complete v6 corpus remains active and the v7 delta adds positive PDM
install/sync forms plus negative run, publish, and dry-run controls. Candidate
tests cover creation/activation order, path mismatch, working-directory
aliases, and a PDM install inside a bound project environment. At freeze time,
the full suite passes 343 tests with one opt-in test skipped, and the real
fresh-container Docker integration passes separately.
