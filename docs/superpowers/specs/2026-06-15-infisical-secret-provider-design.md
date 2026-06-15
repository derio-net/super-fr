# Pluggable secret providers — Infisical runtime injection for fr isolation

**Date:** 2026-06-15
**Status:** Approved design (revised after code review) — ready for planning (`fr-plan`).
**Source:** operator brainstorm session 2026-06-14/15 (rtk/secrets investigation).
**Target repo:** derio-net/super-fr (package: `fr`, module `fr.isolation`).
**Related:** `docs/superpowers/specs/2026-06-14-rtk-isolation-incorporation-design.md`
— sibling seed spec from the same session (independent work, deferred).

**Terminology.** This spec uses the fr **substrate** vocabulary: an *end-to-end*
workflow runs one worktree + one isolated environment behind the
substrate-neutral `Target` protocol (`fr/isolation/types.py:172`). Two
substrates: **docker** (today's environment — a docker-capable host running a
devcontainer; "local" is the legacy misnomer) and **k8s** (pods via
`derio-net/runs-fr`, deferred). "Host" here means the docker substrate's host.
The VK dispatch path is a separate, legacy workflow type (being dropped) and is
out of scope.

## Problem

Today fr injects secrets into the isolation devcontainer as a **static host
env-file**: keys are declared per-profile in `.devcontainer/fr-profiles.yaml`
(`secrets: [...]`), values are filled by the operator into a **hardcoded** host
path `~/.config/fr/secrets/<repo>/<profile>.env` (`secrets_env_file()`,
`fr/isolation/types.py:140-142`), and that file is mounted into the container
via a Docker `--env-file` runArg the scaffold writes into `devcontainer.json`
(`fr/isolation/scaffold.py:104-105`). `_ensure_mounted_env_file()`
(`fr/isolation/local.py:193-213`) parses that runArg and ensures the file
exists. (References verified against the tree on 2026-06-15.)

Two problems:

1. **Long-lived plaintext on disk.** Every declared app secret sits in
   cleartext under `~/.config/fr/secrets/` for the life of the machine —
   readable by any local process, swept into backups, a standing leak surface.
2. **No path to the k8s substrate.** The model is host-rooted
   (`${localEnv:HOME}` + `--env-file`) and so is bound to the docker substrate.
   It cannot serve the forthcoming **k8s substrate** (agent pods via
   `derio-net/runs-fr`), which has no operator `$HOME` and no host mount — pod
   secrets must come from a store the workload authenticates to.

The operator wants to **move away from local credentials as much as possible**
and inject secrets at runtime from a secret store (Infisical), with the seam
general enough that the store and its auth can vary by environment.

## Goals

- A **pluggable `SecretProvider` seam**: the same declared keys resolve through
  a provider chosen per profile. `env-file` stays the default (back-compat);
  `infisical` is the first runtime provider.
- **App secret *values* never written to host disk** with the `infisical`
  provider — `infisical run` executes *inside* the container and fetches them
  straight into the consuming process's environment. (The short-lived UA
  bootstrap *token* is a separate, bounded exception — see Security model.)
- **On-demand retrieval**: most commands touch no secrets; secrets are injected
  only for commands that request them; secret values never reach
  stdout/transcript/logs.
- **Minimal, short-lived credential exposure**: a compromised container holds at
  most a short-TTL, read-only, path-scoped token for one command's lifetime; no
  durable credential ever enters the container.
- An **auth sub-seam keyed by substrate** so the deferred k8s substrate plugs
  its own authentication into *this* interface without rework.

## Non-goals (this spec)

- Implementing the **k8s substrate** path. We **define** the `kubernetes-auth`
  seam; we **implement** only `universal-auth` (docker substrate). The k8s
  substrate / `Target` backend does not exist yet (`fr/isolation/types.py:172-173`,
  the pluggable backend protocol — docker now, k8s later).
- **Per-key injection.** v1 injection is **path-scoped** (`infisical run`'s
  native granularity). True per-key filtering is a Future direction (see below).
- The agent-vault HTTP-broker model (see Future directions).
- Changing the `env-file` provider's behavior beyond reseating it behind the
  new seam.
- Secret *rotation during a run* — `infisical run` resolves once at command
  start (below), so this is moot for v1.

## Current architecture (what exists today)

| Concern | Where |
|---|---|
| Canonical host secrets path | `secrets_env_file()` → `~/.config/fr/secrets/<repo>/<profile>.env` (`types.py:140-142`) |
| Scaffold writes `--env-file` runArg + key placeholders | `scaffold.py:104-105`, `_ensure_env_placeholders` (`scaffold.py:183`) |
| Per-profile declaration (`secrets:`, purpose, default) | `.devcontainer/fr-profiles.yaml`, `_update_profiles_yaml` (def `scaffold.py:159`) |
| Known tool → devcontainer feature map | `KNOWN_TOOL_FEATURES` (`scaffold.py:31-40`); fixed `POST_CREATE` (`scaffold.py:45-48`) |
| Mount-existence check (parses the runArg) | `_ensure_mounted_env_file()` (`local.py:193-213`) |
| Container command execution | `LocalWorktreeDevcontainerTarget.exec()` → `devcontainer exec` (`local.py:136-146`) |
| Runner seam (Docker-free testing) | `subprocess_runner` / `Runner` (`local.py:29-37`) |

## Design

### 1. The `SecretProvider` seam

A provider turns a profile's declared keys into (a) host-side setup at `up`,
and (b) a per-command injection for a command that requests secrets.

```python
@dataclass(frozen=True)
class ProfileContext:           # NEW — wraps what providers need; built from IsolationState + fr-profiles.yaml entry
    repo: str
    profile: str
    keys: tuple[str, ...]       # declared `secrets:`
    config: Mapping[str, Any]   # the profile's provider block (e.g. `infisical:` map)

class SecretProvider(Protocol):
    def up_prepare(self, ctx: ProfileContext) -> None:
        """Host-side setup at `fr isolation up`.
        env-file : ensure the env-file exists (today's behavior).
        infisical: validate config + that BOTH infisical touchpoints are present
                   (host mint binary/HTTP for universal-auth; the in-container
                   `infisical` CLI). Persist no secret material."""

    def exec_wrap(self, ctx: ProfileContext, want_secrets: bool) -> ExecWrap:
        """Injection for ONE command. want_secrets=False ⇒ no secrets."""

@dataclass(frozen=True)
class ExecWrap:
    argv_prefix: tuple[str, ...]   # prepended inside the container
    exec_env: Mapping[str, str]    # extra env for THIS exec (non-secret only; e.g. container token-file path)
```

| Provider | `up_prepare` | `exec_wrap(want=True)` |
|---|---|---|
| **`env-file`** (default) | ensure file exists | `argv_prefix=()`, `exec_env={}` — keys are ambient via the `--env-file` mount |
| **`infisical`** | validate config + both CLI touchpoints; persist no secret | `argv_prefix=("infisical","run","--projectId",<id>,"--env",<env>,"--path",<path>,"--")` run under a shell that sources the token from the mounted token-file (§3) |

`env-file` keeps the legacy **ambient** model (all declared keys in every
command's env via the existing `--env-file` mount). `infisical` is **on-demand**
and **path-scoped**: it injects the secrets under the profile's `path` only for
commands that request them. The asymmetry is intentional — `env-file` is the
back-compat default; `infisical` is the security-forward path.

### 2. The auth sub-seam (`InfisicalAuth`) — keyed by substrate

The Infisical provider delegates *how the in-container `infisical` CLI obtains a
token* to a pluggable auth method, selected by `infisical.auth.method`. The
method is the substrate's authentication strategy — it composes with the
`Target` (docker now, k8s later), not with any per-machine detail.

```python
class InfisicalAuth(Protocol):
    def mint_token(self, ctx: ProfileContext) -> str | None:
        """Produce an access token for the in-container CLI, or None if the
        workload authenticates itself (no host involvement)."""
```

| Method | Substrate | `mint_token` | Status |
|---|---|---|---|
| `universal-auth` | **docker** | **host-side** mint: `infisical login --method=universal-auth …` (or `POST /api/v1/auth/universal-auth/login`) using the referenced UA client-id/secret; returns the access token | **implement now** |
| `kubernetes-auth` | **k8s** (run pods) | returns `None` — the workload authenticates itself, no host mint. **Placeholder shape** — the actual k8s delivery is likely ESO→Secret→env at boot, not in-pod fetch; see the Implementor note | **interface now, impl later** |

Critical properties (corrected after review):

- **Mint is a host-side step for `universal-auth`** — it needs an `infisical`
  binary (or HTTPS client) **on the host**, distinct from the in-container CLI
  that runs `infisical run`. `up_prepare` MUST verify the host mint path and
  fail with an actionable `IsolationError` if absent (consistent with
  `resolve_profile`'s error style).
- **No secret material on any argv.** Neither the UA client-secret (mint input)
  nor the minted token may appear as a command-line argument on host or
  container (argv is `ps`-visible). The client-secret is supplied to the mint
  step via environment/stdin, never `--client-secret=<value>` on argv; the
  token is conveyed per §3.
- **TTL is an identity-side setting, not a mint flag.** Infisical sets UA access
  -token TTL on the *identity* in the platform; the CLI/API cannot shorten it at
  mint time. The design therefore does **not** carry a `token_ttl` knob it
  cannot honor; instead it **documents** that the operator MUST configure a
  short Access-Token TTL (and least-privilege, read-only, path-scoped access) on
  the identity. fr cannot enforce this and says so loudly in scaffold output.

### 3. On-demand retrieval + the `up`/`exec`/`down` flow

`fr isolation exec` gains a repeatable opt-in flag:

```
fr isolation exec --secret DEPLOY_KEY [--secret REGISTRY_TOKEN] -- ./deploy.sh
```

`--secret KEY` declares that *this command* needs secrets. Semantics
(corrected after review — `infisical run` injects by `--path`, not by key):

- It sets `want_secrets=True`, triggering the provider's `exec_wrap`.
- The **injected set is everything under the profile's `path`** — `infisical
  run` has no per-key filter. The named keys are used to **fail fast** (fr
  checks they're declared in the profile, before running) and to make the
  dependency **auditable**; they do **not** narrow what Infisical injects.
- **Operators scope exposure by organizing Infisical paths narrowly** — one
  `path` per logical secret-group, so "all secrets under `path`" equals "exactly
  what this profile's commands are entitled to." This is the v1 isolation
  boundary; true per-key injection is a Future direction.
- The value is injected into the command's subprocess env and **never printed**
  — it does not reach stdout, the transcript, or logs.

**Token conveyance — off all argv (corrected after review).** At `up`, the
`infisical` provider creates a `0600` host **token-file** and bind-mounts it
into the container at a fixed path (e.g. `/run/fr/infisical.token`). On a
secret-bearing exec under `universal-auth`, fr mints a fresh token host-side and
writes it into that file; the wrapped command runs under a shell that reads it
into the environment without it touching argv, e.g.:

```
devcontainer exec … -- sh -lc 'INFISICAL_TOKEN="$(cat /run/fr/infisical.token)" \
   infisical run --projectId <id> --env <env> --path <path> -- <cmd>'
```

The token is never a command-line argument on the host *or* in the container; it
lives only in the `0600` host file (rewritten per request) and the container
process env. For `kubernetes-auth`, `mint_token` returns `None` and the CLI
authenticates via the pod ServiceAccount — no token-file, no host step.

Flow:

- **`up`** — `provider.up_prepare()`. `env-file`: ensure file. `infisical`:
  validate config + both CLI touchpoints; create the `0600` token-file + mount;
  persist no secret.
- **`exec` without `--secret`** — plain `devcontainer exec -- <cmd>`; zero
  Infisical calls.
- **`exec --secret …`** — fail-fast key check → mint (universal-auth) → write
  token-file → run the wrapped command. `infisical run` **resolves secrets once
  at command start**, so the token need only be valid for the *fetch*, not the
  whole command (a long `./deploy.sh` is unaffected once started). Parallel
  execs each mint independently; the per-request token-file write must be
  serialized per workspace (or use per-exec token-file names) to avoid a race.
- **`down`** — shred the token-file (`0600`, best-effort `shred`/unlink). App
  secrets were never materialized on the host; no token persists in the
  container.

Cleanup of the token-file is owned by the `infisical` provider and MUST run on
abnormal exit (exception / SIGINT) too, not only clean `down`.

### 4. Config schema (`fr-profiles.yaml`)

```yaml
profiles:
  dev:                          # no secret_provider ⇒ env-file (today's behavior, untouched)
    default: true
    secrets: []                 # default profile injects NO secrets — git/gh run on
                                # the authenticated host, never in the container
  admin:
    secrets: [DEPLOY_KEY, REGISTRY_TOKEN]   # real in-container needs (NOT GH_TOKEN — gh is host-side)
    secret_provider: infisical
    infisical:
      project_id: <uuid>        # → infisical run --projectId
      env: prod                 # → infisical run --env (Infisical environment slug)
      path: /fr/super-fr/admin  # → infisical run --path (the v1 isolation boundary; scope narrowly)
      auth:
        method: universal-auth  # | kubernetes-auth (future)
        # universal-auth: the durable host identity — REFERENCED, never inlined;
        # consumed via env/stdin at mint, never placed on argv.
        client_id_env: FR_INFISICAL_CLIENT_ID
        client_secret_env: FR_INFISICAL_CLIENT_SECRET
      # NOTE: no token_ttl here — UA token TTL is configured on the Infisical
      # identity (platform-side); fr cannot set it at mint time. Configure a
      # short, read-only, path-scoped identity; scaffold reminds the operator.
```

The committed YAML holds only **coordinates** (`project_id`/`env`/`path`) and
**where to find the host identity** (env-var names the operator populates). No
secret values are ever committed. The same `path` + declared `secrets:` double
as the contract that **pre-authorizes** a pod's ServiceAccount to exactly those
secrets on the **k8s substrate**: just as `fr-profiles.yaml` generates the
docker substrate's `devcontainer.json`, on the k8s substrate it will generate
the **pod template** (the devcontainer.json analog) carrying that
pre-authorization. Building those templates is deferred (k8s substrate), but the
config contract is designed for it now.

### 5. Scaffold / devcontainer changes

- `fr init scaffold` accepts `--secret-provider infisical` (default `env-file`)
  and the `infisical.*` coordinates, written into `fr-profiles.yaml`. It prints
  the **identity-side TTL / least-privilege reminder** (§2).
- For an `infisical` profile, scaffold ensures the **in-container Infisical CLI**
  by adding it the same way other tools are wired: prefer a devcontainer feature
  via the `KNOWN_TOOL_FEATURES` map (`scaffold.py:31-40`); otherwise **append**
  a pinned install to `postCreateCommand` — `POST_CREATE` (`scaffold.py:45-48`)
  is currently a fixed string, so this needs an explicit *append/compose*
  strategy, not a silent overwrite.
- The `--env-file` runArg is still written for `env-file` profiles; for
  `infisical` profiles it is **omitted** (no host secrets file). Instead the
  `0600` token-file mount (§3) is wired.
- `_ensure_env_placeholders` runs only for `env-file` profiles.
- For `universal-auth`, scaffold/`up_prepare` also verifies a **host-side**
  `infisical` binary (or documents the HTTPS-mint fallback).

## Security model

Threat model: the **container is the higher-risk environment** (it runs
agent-generated commands); the operator's host is more trusted. The design
minimizes what a compromised agent can leak:

- **App secret values**: fetched on demand inside the container, live only in
  the requesting command's env for its lifetime — never on host disk, never in a
  persistent container env, never on stdout.
- **The bootstrap token**: under `universal-auth` it briefly exists in a `0600`
  host token-file (rewritten per request, shredded on `down`/abort) and the
  container process env — never on any argv. It is short-lived **iff** the
  operator configured a short Access-Token TTL on the identity (fr documents
  this; it cannot enforce it). Under `kubernetes-auth` there is no token-file
  and no host step at all.
- **The durable identity** (UA client-id/secret): stays host-side, referenced
  from env vars, least-privileged (read-only, path-scoped), never inlined, never
  on argv. It is the unavoidable floor for the docker substrate; the k8s
  substrate eliminates it (ServiceAccount auth, nothing stored).
- **Over-injection is real and bounded by `path`**: a `--secret`-bearing command
  receives *all* secrets under the profile's `path`, not just the named keys.
  Narrow paths are the mitigation; per-key isolation is Future.

## Backward compatibility & migration

- A profile with **no `secret_provider`** resolves to `env-file` with byte-for
  -byte today's behavior. Existing repos/`fr-profiles.yaml` are untouched and
  need no migration.
- `secrets_env_file()` and the `--env-file` machinery remain the `env-file`
  provider's implementation — reseated behind the seam, not removed.
- No change to the `~/.config/fr/secrets/` layout for `env-file` users.

## Testing strategy

The existing `Runner` seam (`local.py:29-37`) makes the lifecycle testable
without Docker; add a `FakeSecretProvider` / fake `InfisicalAuth` so the seam is
unit-tested without a live Infisical. Tests assert:

- (a) no `secret_provider` ⇒ `env-file` behavior unchanged;
- (b) `infisical` + `--secret` ⇒ `infisical run --projectId … --env … --path … --`
  prefix, run under the token-sourcing shell;
- (c) `infisical` without `--secret` ⇒ no Infisical wrap, no mint;
- (d) **no secret material (UA client-secret or minted token) appears in any
  assembled argv** (host mint command or container exec);
- (e) `universal-auth.mint_token` reads the referenced env vars and raises a
  clear `IsolationError` when they're unset;
- (f) `up`/`down` persist no secret; the token-file is `0600` and is shredded on
  `down` **and** on simulated abort;
- (g) `up_prepare` fails actionably when a required `infisical` touchpoint (host
  mint binary, or in-container CLI) is missing — and the in-container-CLI-absent
  failure is also surfaced at exec time, not only `up`.

One narrow integration test may exercise real CLI argument assembly with a
stubbed `infisical` binary on `PATH` (assert args, return canned output) — no
network.

## Architectural ownership

| Invariant | Owner module | Enforcing signature |
|---|---|---|
| Provider selection from profile config | `fr.isolation.secrets` | `provider_for(ctx) -> SecretProvider` |
| Per-command injection assembly | `SecretProvider.exec_wrap` | `(ctx, want_secrets) -> ExecWrap` |
| Per-substrate token acquisition | `InfisicalAuth.mint_token` | `(ctx) -> str | None` |
| No secret material on any argv | `LocalWorktreeDevcontainerTarget.exec` + mint path | token via mounted `0600` file→env; client-secret via env/stdin |
| Token-file lifecycle (create/rewrite/shred, incl. abort) | `InfisicalProvider` | `up_prepare` / `down` + abort handler |
| Back-compat default | `provider_for` | missing `secret_provider` ⇒ `EnvFileProvider` |

## Scope boundaries

**In:** the `SecretProvider`/`InfisicalAuth` seams; `EnvFileProvider`
(reseated); `InfisicalProvider` + `UniversalAuth` (host-side mint, token-file
conveyance, path-scoped injection); the `--secret` exec flag; scaffold /
`fr-profiles.yaml` support (incl. CLI install + TTL reminder); tests; skill-doc
updates (`fr-isolation`, `fr-execute`, `fr-init`).

**Out:** `KubernetesAuth` implementation (interface only); the k8s substrate /
`Target` backend and its pod templates; per-key injection; agent-vault; secret
rotation mid-run; any change to the legacy VK dispatch path (it executes outside
this seam).

## Implementor note — cross-substrate credential model (docker vs k8s)

This spec implements the **docker substrate**, whose git/gh boundary is
host-side: a trusted host drives the container via `docker exec`, git/gh run on
the host, the container holds no git/gh credential. The **k8s substrate inverts
this by design** — and the cleanup that produced this spec surfaced the tension.
The authority is the frank umbrella design
(`derio-net/frank`: `docs/superpowers/specs/2026-06-07--agents--k8s-native-runs-design.md`,
Status: Draft). Maturity as of 2026-06-15: only **Component C** (the `runs-fr`
gateway) is built (walking skeleton, 7/8 phases, pre-deploy); **Component A**
(provisioning, `agent-images`) and **Component B** (`K8sRunner`, `super-fr`)
are designed but unbuilt. So none of the below is integrable yet — it is the
shape the seam must not preclude.

Facts the eventual k8s `SecretProvider` realization must honor:

- **The k8s run pod is an autonomous clean-room** — it clones the repo, checks
  out the branch, runs fr-execute, and **opens the PR itself**. No trusted host
  drives it (`pods/exec` is for *human attach* only). So, unlike the docker
  substrate, the pod **does** need git/gh write credentials in-pod; "gh runs on
  the host" has no k8s analog. The operator-floated "inject a token in the pod"
  is the design direction; the "external driver" alternative is the docker model
  frank explicitly rejects for k8s.
- **Delivery is ESO, not in-pod `infisical run`.** frank Component A injects
  credentials at L2 boot via an **External Secrets Operator–managed k8s Secret**
  (`RunSpec.credsRef`), re-exported into login shells — **ambient-at-boot**
  (like this spec's `env-file` provider), not the docker substrate's on-demand
  fetch. So the k8s realization is most likely an `eso`/`k8s-secret` provider
  (ambient, platform-synced; Infisical can be the ESO *backend*) rather than the
  `infisical` + `kubernetes-auth` in-pod-fetch shape sketched in §2. The seam
  already supports both shapes — ambient (`env-file`) and on-demand
  (`infisical`) — so `kubernetes-auth` is a placeholder; its concrete form is
  Component A/B's to finalize against frank.
- **The open gap to close there:** frank's `credsRef` is framed as *harness*
  credentials (claude auth); **git/gh write credentials for the autonomous
  push+PR are under-specified** in the Draft, yet the run cannot open a PR
  without them. Whoever builds Component A/B + the k8s `SecretProvider` must nail
  down git/gh credential delivery for the pod (scope, least-privilege,
  rotation). This spec's `fr-profiles.yaml` declaration is the natural contract
  to extend into the RunSpec.

This spec implements none of the above; it only ensures the `SecretProvider`
seam and the `fr-profiles.yaml` declaration are shaped so the k8s realization
plugs in without rework.

## Future directions

- **Per-key injection**: fetch only the named `--secret` keys
  (`infisical export`/`secrets get` filtered, captured into env without
  printing) instead of path-scoped `infisical run` — true least-exposure, a
  materially different code path.
- **k8s substrate** secret delivery: per the frank design (see the Implementor
  note), credentials arrive via an **ESO-managed k8s Secret** injected at pod
  boot (`RunSpec.credsRef`) — ambient-at-boot, Infisical as the ESO backend —
  rather than in-pod `infisical run`. Generating the **pod manifests + the
  ExternalSecret** (the devcontainer.json analog) from `fr-profiles.yaml`,
  carrying the pre-authorization, is the work of Component A (`agent-images`,
  provisioning) and Component B (`super-fr` `K8sRunner`) — **not** the `runs-fr`
  gateway (Component C, human-attach only).
- **agent-vault HTTP-broker mode** (MIT, self-hostable): for secrets used as
  HTTP auth, route the agent's requests through a credential broker so the value
  never enters the agent env at all — a parallel injection mode behind the same
  seam, evaluated once its maturity is confirmed.
