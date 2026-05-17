# Shared-PV freshness redesign (kali bridge venv + agent source checkouts) — Design (skeleton)

> **Status:** skeleton. Captures context and the options space discovered
> mid-investigation of #139 and during the live incident on 2026-05-17
> (#143 / cross-repo plan for #271). Actual design TBD via brainstorming
> session.

> **Scope note:** originally framed as "kali bridge venv from shared PV"
> only. After the 2026-05-17 dispatch incident, expanded to cover BOTH
> failure modes on the shared-PV substrate — the bridge's vk venv staleness
> AND the agent's source-checkout staleness. Both classes share the same
> root: nothing automatically refreshes shared-PV state when the upstream
> moves.

## Problem

The shared persistent volume between the vk-local container and the kali
container is used for two things, both of which can drift out of sync with
their upstream sources:

### Drift class 1 — kali bridge `vk` venv (Dockerfile-pinned)

The kali bridge daemon (`agent-images/kali/scripts/vk-issue-bridge.py`)
imports `vk` from a dedicated venv at `/opt/vk-bridge-venv/`, installed at
image-build time:

```dockerfile
# agent-images/kali/Dockerfile:54-61
# ── vk library (consumed by /opt/scripts/vk-issue-bridge.py via `from vk import bridge`) ──
# Pinned to a tag so image builds are reproducible; bumping vk = bumping this line.
# Installed into a dedicated venv so vk's deps (typer pulls a newer click)
# The crontab invokes /opt/vk-bridge-venv/bin/python explicitly.
RUN python3 -m venv /opt/vk-bridge-venv \
    && /opt/vk-bridge-venv/bin/pip install --no-cache-dir \
        'vk @ git+https://github.com/derio-net/superpowers-for-vk@v2.1.4'
```

Updating the bridge's vk requires editing the Dockerfile line and rebuilding
the kali image. Meanwhile, the vk-local container (where install.sh runs)
shares a PV with kali and updates its own vk via `uv tool install` whenever
`scripts/install.sh` is invoked. **Drift:** plugin manifest on the shared
PV is at version X, kali bridge's pinned venv is at version Y, nobody
notices until something breaks.

### Drift class 2 — agent source-repo checkouts on the shared PV

The implementing agent runs in vk-local against shared-PV-mounted source
checkouts of the repos it's working in
(e.g. `~/repos/superpowers-for-vk/`, `~/repos/frank/`). When a PR merges
to a repo's default branch:

- The remote (`origin/main`) advances to the new SHA.
- `install.sh`'s preflight requires the local checkout to ALREADY be on
  main + in sync, but **install.sh itself does NOT `git pull`** — it
  verifies, it doesn't refresh.
- Nothing else automatically refreshes the shared-PV checkout.
- The implementing agent reads from that stale checkout and reports
  things like "the plan directory doesn't exist" or "the spec hasn't
  been written yet" — when in fact both ARE on `origin/main`, just not
  on the agent's local SHA.

**Drift:** `origin/main` for a repo is at SHA N, the shared-PV checkout
of that repo is at SHA M ≤ N, the agent's view of the world is M, the
operator's view of the world is N, the bridge's dispatch decision is based
on N (gh state) but the agent's execution is based on M.

## How these surfaced

### Drift class 1 (kali venv)

While designing the dispatch-reachability gate
(`2026-05-17-dispatch-reachability-gate-design.md`) for issue #139, an
"easy patch" was proposed: have the bridge check at startup that its
installed vk version matches the plugin manifest on disk, and fail loudly
on mismatch. While drafting that check, the architectural premise — that
the kali venv being Dockerfile-pinned is itself a fragile pattern — became
the more important question.

Conclusion at that point: the runtime version-check would be treating the
symptom. The drift class is best eliminated architecturally, not detected
defensively.

### Drift class 2 (agent source checkouts)

Surfaced 2026-05-17 immediately after the dispatch-reachability gate
spec + plan landed on `origin/main` (PR #142). Operator ran `vk apply
--yes` against the gate-fix plan (#143) and against a separate plan in
`frank` repo (#271). Both Issues got `vk-ready` + `vk-synced` cleanly;
both implementing agents reported "the plan directory doesn't exist yet"
even though both plans ARE on the respective repos' `origin/main`.

Investigation traced the gap to the same root: nothing automatically
`git pull`s the shared-PV checkouts after a merge. The gate fix (#139)
verifies the plan is on the remote default branch, but the agent's
LOCAL view of that branch can lag indefinitely.

**Pair note:** drift class 2 is what the gate fix would NOT have caught —
the gate's `git ls-tree origin/HEAD` is remote-side; the agent's read is
local-side. The two are independent invariants; both must hold for
correct dispatch.

## Options space (not selected — to be evaluated in brainstorm)

The options below address drift class 1 (kali venv). Most have a natural
sibling for drift class 2 (agent source checkouts) — either the SAME
mechanism applied to source-repo checkouts, or a complementary one
(e.g. `git pull` on tick). To be enumerated explicitly per drift class
during the brainstorm.

### Option A: symlink `/opt/vk-bridge-venv/` to a shared-PV path

Mount the bridge venv from the same PV that holds vk-local's vk
installation. Single source of truth.

**Concerns to evaluate:**
- venvs aren't portable. They contain absolute paths in `activate` scripts
  and `python` is a symlink to a specific interpreter. The PV path must be
  identical inside both containers, AND the Python binary at that path
  must exist with the same version.
- vk-local uses `uv tool install` which puts the binary somewhere like
  `~/.local/share/uv/tools/vk/`. That's a uv-managed venv, not a plain
  `python -m venv`. Layout is different from the kali Dockerfile's.

### Option B: drop the Dockerfile vk install; install at container startup

Kali image has the venv scaffolding but no vk inside. Entrypoint script
runs `pip install --upgrade vk` from the shared PV source (or pinned to
the version declared by the plugin manifest on the PV) before the bridge
starts.

**Concerns to evaluate:**
- Adds startup latency (network or local pip install on every container
  start).
- Requires the shared PV to be mounted before the entrypoint runs (Docker
  ordering: yes by default; k8s: depends on volume readiness probes).
- A pip-install failure at startup means the bridge doesn't start —
  fail-loud, which is what we want.
- Image becomes reproducible only up to "what gets installed when this
  starts", not "what is in this image".

### Option C: bind-mount vk source from PV; install -e at startup

Like B, but the bridge consumes vk via `pip install -e <pv-path-to-source>`
on startup. Code changes on PV reflect on next bridge tick.

**Concerns to evaluate:**
- Most dev-workflow-flavored; closest to "shared PV is the single source
  of truth".
- Requires the source layout on PV to be a valid Python package
  (pyproject.toml present at the install path).
- Editable installs require the venv to be writable at runtime (true for
  Docker by default; restricted in some k8s setups).

### Option D: hybrid — keep Dockerfile pin as fallback; override from PV if present

Image has a fallback pinned vk. Entrypoint checks for a PV-provided vk
source / venv; if present, uses it; if absent, falls back to image-baked.

**Concerns to evaluate:**
- Defense in depth: bridge always starts even if PV is unmounted.
- Complexity: two install paths to maintain.
- May mask configuration errors (PV unmounted silently → bridge runs
  stale vk forever).

### Sibling option for drift class 2 — auto-pull shared-PV source checkouts

The same architectural shift applies to the agent's source-repo
checkouts. Options to evaluate in the brainstorm:

- **Pull on bridge tick.** Before `discover_plans` walks the local
  filesystem, the bridge runs `git -C <repo> fetch && git checkout main
  && git reset --hard origin/main` (or `git pull --ff-only`) for every
  managed repo. Catches: every tick is up-to-date. Risks: bridge could
  clobber operator-in-progress work if they're editing the PV checkout
  directly (mitigated by reset/pull mode choice).
- **Pull on agent dispatch.** A pre-implementation hook on the agent's
  side runs `git pull --ff-only` in its working tree before reading the
  plan. Catches: agent sees latest. Risks: hook needs to be reliably
  present; ad-hoc agents that don't run the hook are still stale.
- **Pull on `install.sh` invocation.** install.sh currently preflights
  but doesn't refresh. Adding a `git pull --ff-only` at the top would
  catch the case where the operator runs install.sh expecting it to
  align everything. Risks: changes install.sh's contract; might
  surprise operators who expect install.sh not to alter their
  checkout.
- **Cron-driven background pull.** Separate cron job pulls every N
  minutes. Catches: long-running staleness. Risks: same as bridge-tick
  pull regarding operator-in-progress work; adds a new piece of
  infrastructure.

Most likely answer is a combination: bridge-tick pull for the bridge's
own view + an agent-dispatch hook for the implementing agent's view.

## Constraints

- The kali container also runs other tools that may depend on Python deps.
  vk's venv is intentionally isolated (`# Installed into a dedicated venv
  so vk's deps (typer pulls a newer click)`). Any redesign must preserve
  the isolation property.
- The bridge crontab invokes `/opt/vk-bridge-venv/bin/python` explicitly.
  Any path change must update the crontab (or use a stable wrapper path).
- vk-local's install.sh is the canonical install entrypoint. The redesign
  should integrate with `uv tool install` semantics rather than introduce
  a parallel install path.
- The bridge daemon runs as a cron job in long-lived kali pods. Restarting
  the daemon (or the container) on every plugin update is acceptable; the
  bridge tolerates restarts.
- Auto-pull strategies for drift class 2 must NOT silently overwrite an
  operator's in-progress edits on the shared-PV checkout. Either refuse
  to pull (and warn) if the checkout is dirty, or use a separate
  bridge-owned checkout distinct from the operator's edit-area.

## Out of scope (for this redesign)

- Changes to the vk-local container's install flow EXCEPT possibly
  adding a `git pull --ff-only` at the top of `install.sh` if that's
  the chosen drift-class-2 mechanism.
- The dispatch-reachability gate (separate spec, already shipped as
  spec + plan in PR #142 and now in implementation).
- Any runtime version-check guards — once this redesign ships, drift
  becomes impossible by construction; runtime checks would be redundant.
- Multi-version-coexistence on the same PV (we install one vk version at
  a time; rollbacks happen via `uv tool install <older-version>`).

## Decision

**TBD.** To be filled in via brainstorming session before any
implementation plan is written. Both drift classes addressed together
since they share the same architectural surface (shared PV between
vk-local and kali).

## Related

- #139 — consolidated bug that originally surfaced drift class 1
- 2026-05-17 incident (#143 / cross-repo plan for #271) — surfaced
  drift class 2 immediately after the gate spec landed
- `2026-05-17-dispatch-reachability-gate-design.md` — sibling spec, the
  operator-side gate (remote-side check; complements this spec's
  local-side checks)
- PR #135 / #138 — incident lineage that surfaced the bigger version /
  reachability question
