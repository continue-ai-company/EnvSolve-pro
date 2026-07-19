# P5 Round 16 V6 Results

Round 16 executed the unchanged preregistered V6 contract. It produced all ten
required raw replay artifacts and nine complete snapshots. Inflect, Reticulum,
pytest-xdist, and Poetry each produced two complete snapshots with exactly
equal hashes: 4/5 V6 Pass, 0/5 V6 Fail, and 1/5 V6 Unknown. Across the four
complete pairs there was no delta in Python runtime, marker environment, the
full installed-distribution multiset, or content-addressed project
metadata/provenance.

Gpkit replay A stopped before snapshot collection when `files.pythonhosted.org`
timed out while transferring `plotly`; replay B completed with 74 installed
distributions. The missing pair is infrastructure blocked and remains Unknown.
It is not evidence of state drift and a single successful replay cannot be
promoted to Pass. Round 16 permits no conditional retry, so another local run
would be a new experiment rather than completion of this one.

An independent audit recomputed the preregistration and implementation hashes,
all ten raw-result hashes, and all nine snapshot hashes. It also rechecked exact
source identity and cleanliness, host and container network isolation, distinct
container IDs, and all five aggregate decisions. Every audit check passed. The
round ran no model or official verifier and inspected no held-out case.

The machine-readable analysis is
`experiments/validations/p5_round16_v6_dev5_analysis.json`. P5 freeze readiness
must be decided from the preregistered exit criterion, not by converting the
remaining infrastructure Unknown into a development-set Pass.

## P5 freeze decision

The subsequent read-only freeze audit reconstructed the complete Dev-5 pass
curve from frozen artifacts. V0/V1/V2/V3/V4/V5/V6 contain respectively
5/4/2/5/5/0/4 passes; V1 and V6 retain one Unknown each, and V5 remains not
measured. Official Pass and Robust Pass are both 2/5. Four exact clean replays
cover three PEP 610 projects and one legacy egg-link project.

This satisfies the stated P5 exit criterion: benchmark and robust semantics are
separate and fail closed, benchmark-only limitations are visible, and clean
replay works under both modern and legacy provenance. P5 is frozen without
promoting either infrastructure Unknown. Dependency caching remains a server
batch reliability task, not a reason to tune the verifier on Dev-5.
