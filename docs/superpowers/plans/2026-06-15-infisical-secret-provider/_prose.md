# Pluggable secret providers — Infisical runtime injection (docker substrate)

Implements `docs/superpowers/specs/2026-06-15-infisical-secret-provider-design.md`.
Makes secret-value resolution pluggable behind a `SecretProvider` seam in
`fr.isolation`, so the same declared keys (`fr-profiles.yaml`) can be filled
from the existing host env-file (default, unchanged) or fetched at runtime from
Infisical — for the **docker substrate** only. The k8s substrate is
interface-only (see the spec's implementor note); no k8s code here.

## Approach

The seam mirrors the isolation `Target` protocol's own "pluggable backend"
shape. `provider_for(ctx)` selects a provider from the profile's
`secret_provider` key, defaulting to `EnvFileProvider` when absent — so every
existing profile behaves byte-for-byte as today. `EnvFileProvider` is ambient
(all declared keys mounted via the existing `--env-file`). `InfisicalProvider`
is on-demand and path-scoped: only commands that pass `fr isolation exec
--secret KEY` get secrets, fetched in-container via `infisical run --projectId
--env --path` so app-secret values never touch host disk.

Authentication is a sub-seam (`InfisicalAuth`) keyed by substrate:
`UniversalAuth` (docker) mints a fresh short-TTL token **host-side** per
request and conveys it via a `0600` bind-mounted token-file read into the
container env — so neither the UA client-secret nor the minted token ever
appears on any argv (host or container). `KubernetesAuth` is a documented
placeholder; the real k8s delivery is ESO→Secret→env per the frank design.

## Phases

1. **SecretProvider seam + EnvFileProvider** — the types (`ProfileContext`,
   `ExecWrap`, `SecretProvider`), `provider_for`, and today's env-file behavior
   reseated as the default provider. Back-compat is the headline test.
2. **InfisicalProvider + UniversalAuth + token-file** — the host-side mint
   (no secret on argv), path-scoped `exec_wrap`, and the `0600` token-file
   lifecycle (create at up, write per request, shred on down/abort).
3. **Target wiring + `--secret` flag** — `up`/`exec`/`down` call the provider;
   `exec` gains `keys`; the CLI gains repeatable `--secret KEY` with a
   fail-fast declared-key check; the token never lands on the `devcontainer
   exec` argv.
4. **Scaffold + fr-profiles + skill-docs + version bump** — `fr init scaffold
   --secret-provider infisical`, the `infisical:` block, the in-container CLI
   install (composed, not overwriting `postCreateCommand`), `--env-file`
   omitted for infisical profiles, the TTL/least-privilege reminder; document
   `--secret` in the skills; bump the version (touches `packages/`).
5. **[manual] Operator Infisical provisioning + live smoke** — create the
   read-only, short-TTL UA identity, populate the host env vars, and verify a
   real `fr isolation exec --secret` end-to-end. Back-loaded: nothing agentic
   depends on it; the PR ships with this phase marked for the operator (the
   stubs in phases 1–4 cannot exercise a live Infisical).

## Testing

Every agentic phase is TDD (RED → GREEN → refactor) and runs without a live
Infisical: the existing `Runner` subprocess seam plus a fake mint runner /
stubbed `infisical` binary cover provider selection, `exec_wrap` assembly, the
no-secret-on-argv invariant, the token-file 0600 + shred (incl. abort), the
unset-env-var error, and the back-compat default. The full gate
(`ruff`/`mypy`/`pytest`) must pass before review.
