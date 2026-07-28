# Method-independent dependency cache

This infrastructure reduces repeated package downloads without sharing an
installed environment, repository checkout, or writable container layer between
candidates.

## Boundary

- DevPI is an on-demand PyPI mirror.
- apt-cacher-ng caches HTTP Ubuntu package payloads.
- DevPI allows 120 seconds for an uncached upstream request so slow experiment
  networks do not turn transient latency into a false package-missing result.
- Client pip processes allow 180 seconds, ensuring they do not abandon DevPI
  while the mirror is still resolving a cold upstream request.
- The apt client routes only Ubuntu archive hosts through apt-cacher-ng; unrelated
  HTTPS repositories remain direct. Pipelining is disabled and both sides use
  slow-network retries and 120-second timeouts.
- Every candidate still receives a new container and a new virtual environment.
- The cache is outside EnvSolve's observation, constraint, and operation layers.
- A client image only configures package-manager endpoints. It does not install
  dependencies.
- The same client image and cache state must be available to every compared
  method.

The existing frozen providers and runners are intentionally unchanged.

## Development mode

Start the caches:

```bash
docker compose \
  -f experiments/dependency_cache/compose.yaml \
  up -d --build
```

For a frozen study, pass digest-pinned `ENVSOLVE_DEVPI_PYTHON_IMAGE` and
`ENVSOLVE_APT_UBUNTU_IMAGE` values. Floating defaults are for local development
only; the attestation binds the final service image IDs.

Build a client image from the exact EnvBench base image:

```bash
SNAPSHOT_ID=development-unfrozen
docker build \
  -f experiments/dependency_cache/client.Dockerfile \
  --build-arg BASE_IMAGE=ghcr.io/jetbrains-research/envbench-python:latest \
  --build-arg CACHE_SNAPSHOT_ID="${SNAPSHOT_ID}" \
  --build-arg CACHE_MODE=mutable-shared \
  --build-arg UPSTREAM_MISS_POLICY=allow \
  -t envsolve/envbench-python-cache-client:dev \
  experiments/dependency_cache
```

Use the resulting image in a new experiment config. Do not modify a frozen
config or schedule.

## Frozen experiment mode

1. Stop both cache services.
2. Copy the cache data directory to a snapshot directory.
3. Create and commit a content manifest:

```bash
python experiments/tools/dependency_cache_snapshot.py create \
  --mode frozen \
  --services-stopped-acknowledged \
  --root pypi=/path/to/snapshot/devpi \
  --root apt=/path/to/snapshot/apt \
  --output experiments/validations/dependency_cache_snapshot_v1.json
```

4. Verify the snapshot before each batch:

```bash
python experiments/tools/dependency_cache_snapshot.py verify \
  --manifest experiments/validations/dependency_cache_snapshot_v1.json \
  --root pypi=/path/to/snapshot/devpi \
  --root apt=/path/to/snapshot/apt
```

5. Start a disposable runtime copy of that snapshot with offline mode enabled.
   The source snapshot remains unchanged.
6. Build the client image with `CACHE_MODE=frozen-offline`,
   `UPSTREAM_MISS_POLICY=deny`, and the manifest's `snapshot_id`.
7. Attest the manifest, exact image IDs, endpoints, and client labels:

```bash
python experiments/tools/dependency_cache_attestation.py \
  --manifest experiments/validations/dependency_cache_snapshot_v1.json \
  --cache-mode frozen-offline \
  --upstream-miss-policy deny \
  --image pypi-service=envsolve/dependency-cache-pypi:dev \
  --image apt-service=envsolve/dependency-cache-apt:dev \
  --image client=envsolve/envbench-python-cache-client:frozen-v1 \
  --endpoint pypi=http://host.docker.internal:3141/root/pypi/+simple/ \
  --endpoint apt=http://host.docker.internal:3142 \
  --output experiments/validations/dependency_cache_attestation_v1.json
```

DevPI supports an offline mode that serves only cached files. A frozen study
denies upstream misses. Cache coverage is therefore part of the benchmark
environment and must be identical for every method. A cache that allows
upstream misses is `mutable-shared`, not frozen; its initial and final snapshots,
hit/miss state, and randomized condition order are experimental metadata.

## Validated effect canary

The first completed functional canary used the exact local EnvBench Python base
image and installed `humanize==4.12.3` plus Ubuntu's `sl` package in a fresh
container for every condition:

| Condition | Upstream state | Wall-clock |
| --- | --- | ---: |
| Direct package networks | Online | 151.63 s |
| Empty shared cache | Online | 191.98 s |
| Warm shared cache | Both cache services forced offline | 12.28 s |

The offline replay was 12.35 times faster than direct installation. More
importantly, it succeeded while the DevPI process had `--offline-mode` and the
apt-cacher-ng process had `Offlinemode=1`; apt logs contained cache-output events
without upstream-input events. This demonstrates that the repeated installation
was served from the cache rather than from package networks. The cold-cache
condition was 26.61% slower than direct installation, so cold and warm results
must remain separate.

The complete evidence, exact image IDs, source hashes, noisy whole-machine
network counters, and cache snapshot identity are recorded in
`experiments/validations/dependency_cache_effect_canary_v1.json`. This small
canary validates function and isolation. It is not an EnvBench-scale traffic or
runtime estimate.

### Representative EnvBench replay

A preregistered replay selected the largest persisted download lower bound among
six consumed-development episodes. The UER-py command declared six top-level
requirements but resolved to 35 wheels and 2.896 GB of cached files, dominated
by PyTorch and CUDA 13:

| Condition | Wrapper wall-clock | Frozen timeout | Verification |
| --- | ---: | --- | --- |
| Direct package network | 2584.94 s | exceeded during `--rm` lifecycle | observed |
| Initially empty cache | 2605.31 s | exceeded during `--rm` lifecycle | observed |
| Same cache, DevPI forced offline | 93.74 s | within limit | passed |

The offline replay was 27.58 times faster than direct execution and reduced
wall-clock by 96.37%. DevPI served all 35 wheel requests with zero remote reads,
and the 2.896 GB content snapshot verified unchanged afterward. The direct and
cold wrappers returned 124, so they are conservatively not counted as in-budget
passes even though their verification markers were present.

See `experiments/validations/dependency_cache_uer_py_replay_v1_results.json` for
the preregistration binding, exact measurements, limitations, and raw-log
archive.

## Recommended batch mode

The primary benchmark setting should not use a globally shared mutable cache or
a frozen-offline cache:

- Construct one method-independent seed snapshot from benchmark-visible
  manifests without using outcomes.
- Give every compared episode an independent writable copy of that same
  attested seed.
- Keep upstream misses enabled so an uncached package does not restrict the
  Agent's open operation space.
- Preserve mutations only within an episode, where they prevent repeated
  candidate downloads without leaking state across methods.
- Report seed construction, hits, misses, upstream bytes, cache bytes,
  wall-clock, and peak service memory separately from Official Pass.

The episode coordinator enforces that lifecycle without entering the solver:

```bash
python experiments/tools/dependency_cache_episode.py prepare \
  --manifest /path/to/frozen-seed-manifest.json \
  --seed-root pypi=/path/to/frozen-seed/devpi \
  --seed-root apt=/path/to/frozen-seed/apt \
  --episode-root /path/to/runtime/case-a \
  --episode-id case-a

python experiments/tools/dependency_cache_episode.py open \
  --lease /path/to/runtime/case-a/metadata/lease.json \
  --attestation /path/to/platform-attestation.json \
  --image-tag qualified-arm64 \
  --client-image envsolve/envbench-python-cache-client:qualified-arm64

# Run exactly one compared episode against the endpoints in lease.json.

python experiments/tools/dependency_cache_episode.py close \
  --lease /path/to/runtime/case-a/metadata/lease.json
```

`prepare` verifies the frozen seed, creates a writable clone, verifies the clone,
and emits client endpoint metadata. Docker Desktop binds cache ports to
loopback. Native Linux binds them only to Docker's bridge gateway, making them
reachable through `host-gateway` without exposing them on every host interface.
`open` refuses changed image tags or an attestation for another seed and starts
with upstream misses enabled. `close` stops services before hashing, normalizes
Linux container-written ownership inside the episode copy, verifies that the
source seed is unchanged, and records the episode-only cache delta. Before
removing containers it preserves content-hashed service logs and counts package
requests, upstream reads, and upstream timeouts. One coordinator instance owns
one episode; parallel episodes use distinct roots, Compose project names, and
host ports.
Client launches should also use the emitted
`--add-host=host.docker.internal:host-gateway` argument; it is required by
native Linux Docker and harmless on Docker Desktop.

Use forced-offline mode to verify snapshot coverage and reproducibility, not as
the primary EnvSolve-Pro versus baseline condition. Previously frozen schedules
remain unchanged and cache-disabled.

## Fairness rules

- Never warm a cache from held-out outcomes.
- Prewarming may use benchmark-visible repository metadata only.
- Never provide a method-specific cache.
- Never count cache state as algorithm memory.
- Report both cold-start and warm-cache resource results.
- Treat cache availability as an experimental setting, not a success criterion.
- Record download bytes as a resource outcome, not a hard budget.
- Bind exact image IDs and the initial snapshot in every preregistered batch.
- Use `mutable-shared` only with randomized or counterbalanced method order.
