# Kali bridge venv from shared PV — Design (skeleton)

> **Status:** skeleton. Captures context and the options space discovered
> mid-investigation of #139. Actual design TBD via brainstorming session.

## Problem

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
`scripts/install.sh` is invoked. This creates a **drift class:** plugin
manifest on the shared PV is at version X, kali bridge's pinned venv is at
version Y, nobody notices until something breaks.

## How this surfaced

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

## Options space (not selected — to be evaluated in brainstorm)

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

## Out of scope (for this redesign)

- Changes to the vk-local container's install flow (it's already on
  `uv tool install` from install.sh; that's not the drift source).
- The dispatch-reachability gate (separate spec).
- Any runtime version-check guards — once this redesign ships, drift
  becomes impossible by construction; runtime checks would be redundant.
- Multi-version-coexistence on the same PV (we install one vk version at
  a time; rollbacks happen via `uv tool install <older-version>`).

## Decision

**TBD.** To be filled in via brainstorming session before any
implementation plan is written.

## Related

- #139 — consolidated bug that surfaced this drift class
- `2026-05-17-dispatch-reachability-gate-design.md` — sibling spec, the
  operator-side gate
- PR #135 / #138 — incident lineage that surfaced the bigger version /
  reachability question
