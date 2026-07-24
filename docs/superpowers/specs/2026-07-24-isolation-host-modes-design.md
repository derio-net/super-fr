# Isolation host modes — external containment & host-env worktrees

Status: design
Origin: operator brainstorm (2026-07-24). Motivated concretely by the Hermes
deployment: `hermes-agent-compat` Phase 8 (real-Hermes run) is blocked because
the Hermes pod cannot stand up a devcontainer, and the same limitation applies
to VK workspaces — both are unprivileged containers in a Talos pod with no
docker socket.
Target repo: derio-net/super-fr (package `fr.isolation`, hooks
`plugins/super-fr/hooks/`, skills fr-isolation / fr-brainstorming / fr-goal /
fr-debugging / fr-init).

## Problem

`fr isolation` today has exactly one backend:
`LocalWorktreeDevcontainerTarget` (`packages/fr/src/fr/isolation/local.py`),
instantiated at a single site (`commands/isolation_cmd.py:43`). It welds
together two separable concerns:

1. **Workspace isolation** — a linked git worktree, so the base clone is never
   touched (`_git_worktree_add`, the `.fr-isolation` marker, the
   `fr-isolation-required` hook).
2. **Environment provisioning** — `devcontainer up` with a profile from
   `.devcontainer/<profile>/`, secrets via the mounted
   `~/.config/fr/secrets/<repo>/<profile>.env` file.

`resolve_profile` hard-fails without a devcontainer profile ("isolation never
degrades to unisolated"), and `exec` is `devcontainer exec`. That is correct on
a docker-capable operator machine, and wrong on two real host classes:

- **Type 1 — externally contained.** A container prepared by another process
  (e.g. a k8s run pod): the authenticated agent, the repo checkout, and the
  secrets are already inside; the container *is* the isolation boundary. When
  fr-goal triggers `fr isolation up` there, fr must recognize the containment
  and adopt it — today it would try (and fail) to isolate a second time.
- **Type 2 — docker-less worktree hosts.** Long-lived agent environments with
  no docker socket (the VK and Hermes Talos pods). They can create git
  worktrees — VK's own Workspace concept is essentially one, and Hermes falls
  back to worktrees — but they can never satisfy the devcontainer requirement,
  so every fr-isolating skill (fr-goal, fr-brainstorming, fr-debugging) is
  unusable on them.

The 2026-07-23 bridge audit (fr_dispatch + fr_vk read end-to-end, per the
AGENTS.md bridge-audit rule) confirmed the consumer is the **agent process
itself**, not the dispatch path: fr-vk only sends a card + repo/branch over
MCP and the VK server runs the agent somewhere the bridge can't see; no
env/secrets mechanism exists anywhere in dispatch (credentials are always
ambient in the running process); and no "am I inside a container" detection
exists in any package.

## Design

One taxonomy, three modes. Isolation = workspace isolation × environment
provisioning; each mode assigns each half an owner:

| Mode | Workspace | Environment & secrets | Marker `mode` | Hook validity |
|------|-----------|-----------------------|---------------|---------------|
| **devcontainer** (today) | fr linked worktree | devcontainer + secrets env-file | `worktree` | unchanged |
| **host-worktree** (Type 2) | fr linked worktree | the host process env, as-is | `worktree` | unchanged |
| **external** (Type 1) | preparer's checkout | the container env, as-is | `external` | new branch |

Decided in the brainstorm (operator, 2026-07-24): preparer-written marker for
Type 1 detection; host env *is* the env for Type 2 (no fr-provisioned
secrets); host-level declaration via env var for Type 2 activation; container
evidence required in the hook for `external` markers; `up --branch` ensures
the branch in place in external mode; one spec covering both types.

### A. Mode `external` — adopt a preparer-built containment (Type 1)

**Contract with the preparer.** The external prep process (k8s operator,
image build, attach script — whatever stands the container up) writes the
`.fr-isolation` marker itself at the checkout toplevel:

```json
{"toplevel": "/workspace/<repo>", "branch": "<branch-or-empty>",
 "mode": "external", "created_at": "..."}
```

The marker is the hand-off artifact: writing it is the preparer's explicit
claim "this environment is contained and prepared for fr." No probing, no
guessing — an unprepared container is not silently treated as isolated.

**`ExternalTarget`** (new, implements the existing `Target` protocol,
`isolation/types.py:233`):

- `up(profile, branch, ...)`: validate the marker (mode `external`, recorded
  toplevel == actual toplevel). Ensure the requested branch: if HEAD is not
  already `<branch>`, `git switch -c <branch>` in place — the preparer chose
  the base, fr names the feature branch, and fr-goal's flow works unchanged
  whether or not the preparer pre-cut it. Update the marker's `branch`, save
  `IsolationState` (worktree = the checkout, profile = `"external"`), return.
  Idempotent like the local target. `--profile` is ignored with a note —
  the environment is not fr's to select.
- `exec(state, argv)`: plain subprocess in the checkout with the inherited
  env. The exec-bridge stays the uniform surface skills call; it just stops
  crossing a container boundary.
- `restart` / `stats`: `IsolationError` with "externally managed — restart
  the container via its owner." `status`: reports mode, toplevel, branch,
  container evidence.
- `down`: removes fr's state file and the marker's `branch` claim only.
  The checkout and container belong to the preparer; fr never deletes them.
  (`down --all` likewise only retires fr state.)

**Selection.** `_target()` (isolation_cmd) checks for a valid `external`
marker at the cwd's toplevel *first*; if present, every subcommand routes to
`ExternalTarget` regardless of other configuration. This is what makes
`fr isolation up` inside a prepared container a recognize-and-continue
instead of a second isolation attempt.

### B. Mode host-worktree — fr worktree, host environment (Type 2)

**Activation is a host-level declaration, never a per-call choice:**
`FR_ISOLATION_TARGET=worktree` set in the pod manifest / image env. On a
normal operator machine the variable is absent and nothing degrades; an agent
mid-session cannot reach for the weaker mode to route around a broken docker
(no CLI flag is introduced). Unknown values of `FR_ISOLATION_TARGET` fail
closed with an `IsolationError` naming the valid values
(`devcontainer` | `worktree`).

**`HostWorktreeTarget`** (new): the worktree half of the local target without
the devcontainer half —

- `up`: same `_git_worktree_add` + cold-start-base + marker + state flow
  (shared with the local target — extract, don't duplicate), skipping
  `resolve_profile`, the profile-committed gate, `_ensure_mounted_env_file`,
  and `devcontainer up`. Profile recorded as `"host"`. A repo with no
  `.devcontainer/` at all is fine in this mode — the profile requirement is a
  devcontainer-mode rule, not an isolation rule.
- `exec`: subprocess in the worktree, host env inherited. **No secrets
  provisioning**: the pods already carry their credentials (ESO-injected);
  "relaxed isolation" is honest that it isolates the filesystem/branch, not
  credentials or toolchain. The secrets env-file machinery is not consulted.
- `restart` / `stats`: not applicable (`IsolationError` pointing at the pod
  owner). `status` / `down` / gc: as today minus container concerns (worktree
  removal, branch-changes guard, marker retirement all unchanged).

**Marker mode stays `worktree`.** A host-worktree workspace is a genuine
linked worktree, so the existing hook validity check (recorded toplevel
match + git-common-dir ≠ git-dir) already holds — the enforcement surface is
untouched for Type 2. The *flavor* (devcontainer vs host) is recorded in
`IsolationState.profile`, which is state, not enforcement.

### C. Hook change — `external` marker validity

`_fr_marker_valid` in the shared decision library
(`plugins/super-fr/hooks/lib/fr-isolation-decision.sh`, consumed by both the
Claude Code and Hermes entrypoints — one edit covers both) gains an
`external` branch:

- mode `worktree`: unchanged (toplevel match + linked-worktree check).
- mode `external`: toplevel match **+ container evidence** — any of
  `/.dockerenv`, `/run/.containerenv`, or `$KUBERNETES_SERVICE_HOST`. A
  marker forged on a bare host never validates; the toplevel match already
  defeats a marker copied to the Mac base clone (the container path can't
  equal the base-clone path). Cost: one stat.
- any other mode: fail closed (unchanged).

The OpenCode plugin (`packages/fr-opencode-plugin`) ports the same two-line
change; it is outside CI, so its `bun test` run is a checklist item in the
plan.

### D. Skill & docs surface

- **fr-isolation SKILL.md**: the "requires a devcontainer profile — no
  unisolated fallback" hard rule becomes mode-aware: devcontainer mode keeps
  it verbatim; a host with `FR_ISOLATION_TARGET=worktree` or a valid external
  marker proceeds without a profile. The exec-bridge discipline (all commands
  via `fr isolation exec`) is unchanged in all three modes.
- **fr-brainstorming / fr-goal / fr-debugging**: no flow change — they call
  `fr isolation up` and inherit the mode. The fr-brainstorming HARD STOP on
  "no profile" applies only when the resolved mode is devcontainer.
- **fr-init**: unchanged scope (it scaffolds devcontainer profiles); its
  interview mentions the env-var declaration for docker-less hosts as
  documentation only.
- **Rules**: `plugins/super-fr/rules/fr-isolation-required.md` (and the
  condensed `.claude/rules/` mirror, updated by hand per AGENTS.md) document
  the three modes and the external-marker contract.

### E. What Type 2 unblocks downstream

Hermes: `hermes-agent-compat` Phase 8 (real-Hermes end-to-end run) proceeds
by setting `FR_ISOLATION_TARGET=worktree` in the Hermes pod env. VK: agents
inside VK workspaces can run fr-goal in-pod the same way. Neither requires
dispatch-path changes — `fr_dispatch`'s `Runner` protocol is already
environment-neutral, and VK's server-side workspace remains opaque to fr
(bridge audit findings).

## Non-goals

- **No secrets provisioning in the new modes.** Host-worktree and external
  modes inherit the ambient env by design; anything stronger belongs to the
  environment owner (ESO, image build, preparer).
- **No probe-based auto-detection of containers for mode selection.** The
  external marker is an explicit preparer claim; container evidence is used
  only as *corroboration* in the hook, never as a trigger.
- **No auto-degradation when docker is broken.** A transiently unreachable
  docker on an operator machine keeps failing loudly in devcontainer mode.
- **No dispatch/bridge changes.** fr-vk / fr-dispatch are untouched.
- **No remote-target work** (the "remote later" half of the Target protocol
  docstring stays future).

## Testing & verification

- Unit: `ExternalTarget` lifecycle (adopt, branch-ensure idempotence,
  refuse-to-delete on down, `--profile` ignored); `HostWorktreeTarget`
  lifecycle (up/exec/down without any devcontainer call — assert via the
  Runner seam that no `devcontainer`/`docker` argv is ever issued);
  `_target()` selection precedence (external marker > env declaration >
  default); unknown `FR_ISOLATION_TARGET` fails closed.
- Hook tests (existing bash-hook test harness): `external` marker allows
  edits only with toplevel match AND container evidence; forged externals on
  bare hosts blocked; unknown modes still blocked; `worktree` behavior
  byte-identical.
- OpenCode plugin: mirrored cases via `bun test` (manual checklist item —
  package is outside CI).
- Integration: an end-to-end host-worktree run in a sandbox repo
  (`FR_ISOLATION_TARGET=worktree fr isolation up/exec/down`) asserting the
  base clone is never written.
- Acceptance rows: see matrix additions accompanying this spec (external
  adoption, host-worktree end-to-end, no-degradation guarantee).

## Test Plan

Post-merge — operator-driven. Each step is pinned by an acceptance row (in
parentheses); flip the row's status as the step is proven.

1. **Mac, no degradation** (`isolation-no-silent-degradation`): after
   upgrading the plugin/CLI, in the super-fr base clone with no
   `FR_ISOLATION_TARGET` set, `fr isolation up` still requires a devcontainer
   profile; `FR_ISOLATION_TARGET=bogus fr isolation up` fails closed naming
   the valid values.
2. **Hermes pod, host-worktree live** (`isolation-host-worktree-e2e`): set
   `FR_ISOLATION_TARGET=worktree` in the Hermes deployment env; in-pod, run
   `fr isolation up --branch feat/<slug>` → exec a command → `down`; verify
   no docker/devcontainer invocation was attempted and the pod's base clone
   is untouched. This is also `hermes-agent-compat` Phase 8's unblocking
   step — complete that phase in the same walk.
3. **External containment walk** (`isolation-external-adopt` +
   `isolation-external-marker-enforcement`): in a container whose prep step
   wrote a mode-external `.fr-isolation` marker, run
   `fr isolation up --branch feat/<slug>`: it adopts (no second isolation),
   ensures the branch, and the edit-gate hook permits edits in the checkout.
   Then copy that marker into the Mac base clone and confirm the hook still
   blocks (toplevel mismatch, no container evidence).
4. **VK workspace spot-check** (optional, same rows as step 2): repeat step 2
   inside a VK workspace to confirm the declaration works there unchanged.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-07-24-isolation-host-modes | `derio-net/super-fr` | `2026-07-24-isolation-host-modes` | — |
| 2026-07-24-isolation-host-modes | `derio-net/super-fr` | `2026-07-24-isolation-host-modes` | — |

## References

- `packages/fr/src/fr/isolation/local.py` — `LocalWorktreeDevcontainerTarget`,
  `_write_isolation_marker` (the `mode` field seam), `_git_worktree_add` /
  `_cold_start_base` (shared by HostWorktreeTarget).
- `packages/fr/src/fr/isolation/types.py:233` — the `Target` protocol
  ("local worktree+devcontainer now; remote later").
- `packages/fr/src/fr/commands/isolation_cmd.py:43` — `_target()`, the single
  selection site.
- `plugins/super-fr/hooks/lib/fr-isolation-decision.sh` — `_fr_marker_valid`,
  the one shared enforcement edit.
- `docs/superpowers/implemented/specs/2026-07-23-hermes-agent-compat-design.md`
  — Phase 8 blocked on this spec (Hermes pod, no docker socket).
- 2026-07-24 bridge audit (this brainstorm): fr_dispatch/fr_vk end-to-end —
  VK workspaces are server-side opaque; dispatch carries no env/secrets; no
  container self-detection existed anywhere.
