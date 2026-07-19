# P4D Capability Discovery and Repair Protocol

## Purpose

P4D tests whether a missing executable capability can be mapped to an
installable system package through executable, provenance-bearing evidence,
rather than an LLM guess or a repository-specific lookup table. P4D is an
iterative development phase. Every failed and successful round is retained,
and any semantic change requires a new round identifier.

P4D is additive. It does not modify the frozen P0, P2, P3, P4A, P4B, or P4C
semantics.

## Round 1 development target

Round 1 uses the already consumed P3 capability conflict whose subject is
`pg_config`. Repository identity is used only to prove source-result lineage;
provider and repair selection receive the normalized capability subject, image
context, package manager, and evidence IDs, but no repository name.

This is a development-only state-transition experiment. It is not a new
EnvBench execution and cannot count as Official Pass, Robust Pass, or an
end-to-end Dev success.

## Provider semantics

The provider runs inside the exact evaluator image associated with both the
original consumed result and frozen P4B image inventory. Its discovery input is
one validated executable name from a typed capability conflict.

For an `apt-get` environment, Round 1 performs these separately audited stages:

1. observe OS identity, architecture, `PATH`, provider-tool presence, and
   initial capability absence;
2. run `apt-get update`;
3. install `apt-file` only when it is absent;
4. refresh the `apt-file` contents index;
5. record hashes of apt source definitions and downloaded index files;
6. execute an anchored exact-basename `apt-file search --regexp` query;
7. retain only package/path records whose basename exactly equals the requested
   capability and whose parent directory is present in the observed `PATH`.

The provider must not use package descriptions, repository text, known package
names, web search, or LLM output. Zero retained candidates blocks the round.
Multiple retained candidates remain explicit and are ordered deterministically
by package name and path.

Installing or updating the provider is context-acquisition cost, not repair
success. These mutations are recorded in the action ledger and disclosed
separately from the typed repair actions.

## Evidence and transfer

Raw query output, retained and rejected records, observed `PATH`, source-list
hashes, index-file hashes, image identity, commands, exit codes, and timestamps
are retained in a provider artifact. A structured
`context-capability-package-candidate` evidence item is actionable only when:

- the provider artifact audits successfully;
- source and target image identities match exactly;
- its manager equals the selected frozen context manager;
- every candidate has at least one exact executable path in the observed
  `PATH`;
- the target conflict subject equals the provider query subject.

The target state records the complete provider lineage before P4A is allowed to
propose a repair.

## Repair semantics

The frozen P4A registry generates system-capability repair plans without any
package-name override. Round 1 tries candidates in deterministic order under a
maximum of three candidate plans. For each plan:

1. transition-aware preflight must project a satisfiable state;
2. the frozen package-install command executes in the provider container;
3. the frozen independent `command -v -- <capability>` probe executes;
4. only a successful exact capability observation may supersede the old absent
   fact.

A failed mutation or probe remains a failed trajectory. Later candidates may
run only if the state still contains the original unsuperseded fact and the
action budget permits another plan. Round 1 has no rollback beyond disposal of
the isolated container.

## Isolation and integrity

- Network is enabled only for apt index/provider and candidate package
  acquisition; all network-using actions are explicit.
- No benchmark repository is mounted or cloned.
- No model request is permitted.
- Canary-20 and Official-Test-100 remain uninspected.
- The original P3, P4B, and P4C artifacts remain immutable.

## Round 1 outcomes

- **Provider blocked:** provider bootstrap/query fails or no PATH-reachable exact
  candidate is found.
- **Repair blocked:** candidates exist but all allowed mutations or probes fail.
- **Transition satisfied:** one independently probed capability fact replaces
  only the contradicted absent fact and the typed state becomes satisfiable.

All three outcomes are publishable development evidence and must be retained.
Even a satisfied transition does not complete P4; subsequent failures exposed
by a repository installation belong to later versioned rounds.
