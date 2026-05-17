# v2 bridge rebuild — actually deliver the thin wrapper v2 promised

## Problem

The v2 rebuild spec (`docs/superpowers/specs/2026-05-06-vk-rebuild-state-machine-design.md`) explicitly promised:

> The bridge in `willikins/scripts/vk-issue-bridge.py` becomes a thin wrapper.

The spec gave a 7-line code sample of what the thin wrapper would look like. That code sample is exactly what `src/vk/bridge/__init__.py::tick` is today — the library function exists. **What doesn't exist is the actual bridge USING it as the bridge.**

The bridge that was supposed to BECOME the thin wrapper:

- Was specced as living in `willikins` (never moved there)
- Actually lives in `agent-images/kali/scripts/vk-issue-bridge.py` (bootstrapped fresh in commit `bc6322c`)
- Is 1089 lines, not 7
- Calls `vk.bridge.tick` from inside itself as ONE operation alongside everything else — both the v2 library path AND the legacy per-Issue loop run on every cron tick, with a deduplication rule (`v2_owned` set in `_run_lib_path`)

So v2 shipped HALF the rebuild: the library function that was supposed to BE the bridge. The bridge that was supposed to BECOME it never did. Every brainstorm in this repo since has assumed `vk.bridge.tick` IS the bridge surface — the actual bridge in `agent-images` was never read.

The audit + migration table that motivated this rebuild is in tracking issue [#147](https://github.com/derio-net/superpowers-for-vk/issues/147).

### Concrete failure modes already observed

Three bugs this week trace to the same anti-pattern (critical invariant supposedly owned by v2; actually enforced only by accidental legacy compensation):

1. **#139 dispatch race** — `vk apply --yes` from a non-pushed branch dispatched fine because the legacy bridge has its own body-text-driven dispatch. PR #135 implementation merged without ever reading the plan. Reverted; gate added (#146 merged).
2. **2026-05-17 stale-checkout incident (#143, frank-#271)** — plans ARE on `origin/main`, but the shared-PV checkout the agents read from never auto-pulls. Agents reported "plan doesn't exist."
3. **Dependency gating bug (2026-05-17)** — `_lifecycle_label` returns `vk-ready` for every fresh agentic phase regardless of `depends_on`. The renderer's signature literally precludes seeing dependency state. Dep gating works only because the legacy bridge's `check_blockers` body-parses and queries gh independently. **The labels lie. Operators looking at `vk-ready` on a blocked phase have no way to know it's actually blocked.**

The user observation that triggered this rebuild:

> "this is so stupid and wasteful. After all these planning and designing and tests and tdd? The renderer was supposed to OWN the sync. What business has the 'legacy' bridge functionality? Isn't this what the first v2 delivered? We left parts of the legacy bridge standing because they were not implemented in v2. But if this part fails, WHAT was even implemented in v2?"

## Goal

After this rebuild:

1. All bridge functionality lives in the `vk` package (`superpowers-for-vk`).
2. The legacy "Issue-body driven" dispatch path is **retired** (no more body-text parsing for dispatch decisions; the renderer is the single source of truth for what's ready).
3. The bridge daemon is invoked via a hidden module entry (`python -m vk.bridge`) wrapped by a tiny shell script written by `install.sh --install-bridge`. NO public `vk bridge` CLI verb is exposed.
4. `agent-images/kali/scripts/vk-issue-bridge.py` (1089 LOC) and `agent-images/kali/scripts/vk_mcp_client.py` are **deleted**.
5. The renderer's `_lifecycle_label` knows about dependencies and projects a new `vk-blocked` label for phases whose `depends_on` predecessors aren't complete. Labels stop lying.
6. The cross-repo orchestration duplication between legacy `sync_issue` and the v2 `_McpAdapter.create_card` is consolidated into ONE canonical dispatch implementation.

## Multi-repo concerns (cross-repo dispatch)

A plan's `_meta.target_repo` and a phase's `tracking_issue` repo CAN differ. Concrete in-use example from `willikins/docs/superpowers/plans/2026-05-03-agent-followup-sweep`:

- `target_repo: derio-net/superpowers-for-vk`
- Phases 1–4, 6 tracked on `derio-net/willikins`

This shape isn't an edge case — it's how operators decompose plans whose work spans repos. **The bridge rebuild treats multi-repo as a first-class concern** because it touches every migrated module:

| Module | Multi-repo concern |
|---|---|
| `vk.render` (dep gating, lifecycle projection) | The dep referenced by `phase.depends_on=[N]` is itself a phase — its observation comes from gh-side observation of its own `tracking_issue`, on whatever repo that points at |
| `vk.diff` (RepoLabelEnsure, label changes) | Label ensures must group by destination repo; per-issue label/state/body mutations must route to `parse_issue_url(phase.tracking_issue).repo` |
| `vk.bridge.dispatch` | The workspace branches off the repo of the phase's tracking issue, not `target_repo` |
| `vk.bridge.lifecycle` | Issue close fires on the phase's repo |
| `vk.bridge.pr_state` | PR observation queries the phase's repo |
| `vk.bridge.workspaces` | Workspace name keyed by `gh#<N>` — repo info elsewhere |
| `vk.bridge.prompt` | Prompt's `issue_url` already carries the repo (no change needed) |

### Routing rule

- **Per-phase mutations** (IssueLabelChange, IssueStateChange, IssueBodyChange, IssueClose, workspace creation, vk-synced add): repo is `parse_issue_url(phase.tracking_issue).repo`. The existing code at `src/vk/diff.py:134-171` already does this for the diff-emitted mutations; the rebuild ensures every NEW module follows the same rule.
- **Repo-wide concerns** (RepoLabelEnsure): group by destination repo. Union of managed labels per repo. Sorted iteration for deterministic mutation order. For undispatched phases (no tracking_issue), the destination falls back to `plan.meta.target_repo` (where their `IssueCreate` will fire).
- **Single-repo plans (the common case):** behavior bit-identical to today — `labels_per_repo` has one key.
- **Fully-cross-repo plans (every phase dispatched on a foreign repo):** `target_repo` receives NO RepoLabelEnsure. Strictly more correct — no phases live there. If an operator later adds an undispatched phase to such a plan, the next `apply()` re-introduces the `target_repo` ensure on its own.

### Folded from the cross-repo `RepoLabelEnsure` spec

This section absorbs the design that previously lived in `docs/superpowers/archived-specs/2026-05-16-cross-repo-label-ensure-design.md` (archived 2026-05-17 via PR #149). The diff() change (group RepoLabelEnsure by destination repo) lands in Phase 1 alongside the dep-gating signature change — both are state-machine projection fixes in the same module surface. Reference tracking issue #132; defused tracking #134.

## Deployment constraints (what stays in agent-images and why)

A pre-implementation feasibility audit (2026-05-17) confirmed the rebuild is technically possible, but surfaced explicit runtime constraints that need to be in the spec — not just in the implementer's head — to avoid the next "we forgot what the bridge actually needed" incident.

### Container-level dependencies the rebuilt bridge still requires

The MCP client (`vk_mcp_client.py`, moving to `vk._mcp_client`) is a **thin Python wrapper around a Node.js subprocess**. It spawns `vibe-kanban-mcp --mode global` (or falls back to `npx vibe-kanban@latest --mcp`) and communicates via JSON-RPC 2.0 over stdin/stdout. This means the rebuilt bridge ONLY runs in environments where:

- **Node.js + npx are installed** and on `PATH`
- The `vibe-kanban` package is installable (or `vibe-kanban-mcp` binary is on `PATH`)
- The MCP server's HTTP backend is reachable via `VIBE_BACKEND_URL` (default `http://localhost:8081`)

These are SYSTEM-LEVEL dependencies provided by the Kali container today. After the rebuild they STILL must be provided by whatever container runs the bridge — the vk package cannot bundle Node.js.

### PEP 668 venv isolation

Debian's apt-managed `python3-click` collides with vk's transitive deps (typer pulls a newer click). The Kali Dockerfile creates `/opt/vk-bridge-venv/` for isolation:

```dockerfile
RUN python3 -m venv /opt/vk-bridge-venv \
    && /opt/vk-bridge-venv/bin/pip install --no-cache-dir \
        'vk @ git+https://github.com/derio-net/superpowers-for-vk@<version>'
```

The rebuild keeps this venv pattern. The wrapper script written by `install.sh --install-bridge` MUST point at `/opt/vk-bridge-venv/bin/python -m vk.bridge` (not at any system Python). This is encoded in the wrapper template — the install path is a config variable, but the interpreter must be the venv's.

### What STAYS in agent-images after the rebuild

| Artifact | Why it stays |
|---|---|
| `kali/Dockerfile` | Container build recipe — sets up venv, installs vk, system tooling (gh, mosh, supercronic, npx, locale) |
| `kali/config-templates/crontab.txt` | Supercronic schedule; bridge cron line points at the new wrapper. Tick frequency unchanged from current `*/2 * * * *`. Supercronic supports sub-minute via a 6th seconds field if needed later. |
| `kali/scripts/*.{sh,py}` (18 other files) | Audit, exercise, guardrails, push-heartbeat, session-manager, wrap-claude, etc. — unrelated to the bridge |
| `kali/etc/cont-init.d/` | Container init scripts (crontab seeding etc.) |
| All env vars (`VK_ORG_ID`, `VK_DERIO_OPS_PROJECT_ID`, `VIBE_BACKEND_URL`, `PUSHGATEWAY_URL`, `MAX_CONCURRENT`) | Deployment config — set by k8s manifests or container env |

### What MOVES to superpowers-for-vk

| File today | After |
|---|---|
| `kali/scripts/vk-issue-bridge.py` (1089 LOC) | DELETED; all logic in `vk.bridge.*` modules |
| `kali/scripts/vk_mcp_client.py` (194 LOC) | DELETED; moved to `vk._mcp_client` |

### The Willikins lifecycle-transition hook is ALREADY silently broken

The current bridge calls `~/repos/willikins/scripts/hooks/vk-lifecycle-transition.sh` from `sync_issue:752` via subprocess. **That script no longer exists in `willikins/scripts/hooks/`** (verified 2026-05-17 — directory contains `exercise-nudge.sh`, `plan-archive-check.sh`, `pre-compact.sh`, etc.; no `vk-lifecycle-transition.sh`). The subprocess fails silently — the try/except logs a warning but continues. The rebuild's `VK_LIFECYCLE_HOOK_SCRIPT` env var defaults to "nothing called" — which is structurally correct (matches today's de-facto behavior) and operator-overridable when a real hook script is needed.

## Bridge inventory (the empirical read that should have happened before any prior spec)

Read of `agent-images/kali/scripts/vk-issue-bridge.py` end-to-end, organized by concern:

| # | Concern | Today's location | Notes |
|---|---|---|---|
| **A** | Repo discovery (fs) | `discover_repos:54-76`, `_run_lib_path:875-942` | Walks `~/repos/*/.git` for plan discovery + `_DISCOVER_PLANS` per repo |
| **A'** | Repo discovery (gh-side) | `gh_list_ready_issues:559-600` | gh-API listing of `vk-ready` Issues for the legacy path |
| **B** | Body-text parsing | `parse_issue_body:105-178`, `parse_dependencies:180-230`, `_parse_issue_url:763-769` | Extracts skill+repos from `## Instruction`/`## Workspace`, deps from `## Dependencies` |
| **C** | Dependency gating | `check_blockers:233-265` | Queries gh per-blocker, fail-loud on unreachable. **Only fires for legacy path.** |
| **D** | Workspace lifecycle | `archive_workspace_for_card:276-308`, `reap_orphan_workspaces:344-399` | Name-prefix join `<simple_id> -> gh#<N>` + sweeper for orphans |
| **E** | Issue lifecycle (close on done) | `close_gh_issue_for_card:311-341` | Belt-and-braces close when PR body lacks `Fixes #N` |
| **F** | PR status polling + state transitions | `poll_pr_status:402-445` | In-progress → In-review → Done; cascades archive + close |
| **G** | **Dispatch orchestration** (the actual work) | `sync_issue:642-760` (legacy), `_McpAdapter.create_card:771-872` (v2). **These two are functional duplicates.** | create card → set status → list repos → start_workspace → link → add `vk-synced` → lifecycle-transition script |
| **H** | Slot accounting | `count_active_ws:459-467`, main loop's slot decrement | `MAX_CONCURRENT` env, only legacy loop enforces |
| **I** | Dedup detection | `fetch_existing_titles:448-456`, `is_dedup` check in main | By card-title equality |
| **J** | Repo allowlist | `fetch_repo_names:470-478` | VK-side validation of `parsed.repos[0]` |
| **K** | Prompt construction | `build_prompt:605-639` | Static template + optional deps preamble (sourced from body text today) |
| **L** | Metrics (Prometheus pushgateway) | `_push_metric:483-495` + 3 `push_*` helpers | failure/success/heartbeat |
| **M** | Error classification | `_classify_gh_error:543-555` | gh-stderr → info vs warn |
| **N** | Willikins lifecycle-transition hook | `sync_issue:752` calls `TRANSITION_SCRIPT` | External script path `~/repos/willikins/scripts/hooks/vk-lifecycle-transition.sh` — willikins-specific path baked in today |
| **O** | Logging | `log:79-80` | Trivial |
| **P** | Domain types | `GhIssue:84-94`, `ParsedBody:98-103` | Trivial |

## Target architecture

```
superpowers-for-vk/src/vk/
├── __init__.py
├── cli.py                      # public CLI (no `bridge` verb exposed)
├── apply.py, render.py,        # state machine (renderer signature changes; see §"Renderer + dep gating")
│   diff.py, parser.py,
│   plan_ops.py
├── git.py, gh.py,              # existing gh / git helpers
│   ghclient.py, real_ghclient.py
├── _mcp_client.py              # NEW: moved from agent-images (private, leading _)
└── bridge/
    ├── __init__.py             # existing public surface: discover_plans, tick, TickResult
    ├── __main__.py             # NEW: `python -m vk.bridge` entry → cli.main()
    ├── cli.py                  # NEW: main() — one tick across all configured repos
    ├── dispatch.py             # NEW: extracted from sync_issue + _McpAdapter.create_card
    ├── workspaces.py           # NEW: archive_workspace_for_card, reap_orphan_workspaces
    ├── lifecycle.py            # NEW: close_gh_issue_for_card + cascade logic
    ├── pr_state.py             # NEW: poll_pr_status + state-machine transitions
    ├── slots.py                # NEW: MAX_CONCURRENT, count_active_ws
    ├── dedup.py                # NEW: fetch_existing_titles, is_dedup
    ├── prompt.py               # NEW: build_prompt (deps preamble sourced from phase.depends_on)
    ├── metrics.py              # NEW: Pushgateway interactions
    └── config.py               # NEW: env vars, repo allowlist via fetch_repo_names
```

`agent-images/kali/scripts/`:
- **DELETED:** `vk-issue-bridge.py` (1089 LOC)
- **DELETED:** `vk_mcp_client.py`
- **POSSIBLY ADDED:** `vk-bridge-run.sh` (1-line wrapper, if not written by `install.sh`)

`agent-images/kali/Dockerfile`:
- Drops the `COPY scripts/vk-issue-bridge.py` line (if present)
- Keeps the venv install of `vk` (now contains the bridge)

`agent-images/kali/tests/`:
- Meaningful bridge unit tests relocate into `superpowers-for-vk/tests/`
- A thin smoke test stays here: "build the Kali image, run `python -m vk.bridge --dry-run`, assert exit 0"

**Net effect:** `agent-images` loses ~1300 LOC of bridge code; `superpowers-for-vk` gains ~1000 LOC (less than what's deleted because the legacy path retires and dispatch dedup saves ~100 LOC).

## Migration table (per concern → new home)

| From inventory | After rebuild |
|---|---|
| **A** repo discovery (fs) | `vk.bridge.cli` (calls existing `vk.bridge.discover_plans` per repo) |
| **A'** gh ready-issue list | **DELETED** (legacy path retired) |
| **B** body-text parsing | **DELETED for dispatch.** `phase.depends_on` is the only source. Body text stays human-readable but is no longer parsed by any code path. |
| **C** dep gating | `vk.render._lifecycle_label` extended (signature change — see next section). Returns `VK_BLOCKED` for phases with unsatisfied deps. The renderer becomes the gate. |
| **D** workspace lifecycle | `vk.bridge.workspaces` |
| **E** issue close on done | `vk.bridge.lifecycle` (also reflected in `vk.render` projection — see §"State-machine surface gains" below) |
| **F** PR polling + transitions | `vk.bridge.pr_state` (consumes `vk.render` for transition decisions, talks to MCP for updates) |
| **G** dispatch orchestration | `vk.bridge.dispatch` — ONE canonical implementation; both old call sites collapse into it |
| **H** slot accounting | `vk.bridge.slots` (`vk.bridge.tick` gains slot enforcement — closes the "v2 path doesn't enforce slots" Phase-1-was-acceptable-tech-debt note) |
| **I** dedup | `vk.bridge.dedup` |
| **J** repo allowlist | `vk.bridge.config.fetch_repo_names()` |
| **K** prompt construction | `vk.bridge.prompt` (deps preamble derived from `phase.depends_on`, NOT from body text) |
| **L** metrics | `vk.bridge.metrics` |
| **M** gh-stderr classification | `vk.gh._classify_error` (or stays internal in `vk._gh_internal`) — utility |
| **N** willikins lifecycle hook | Configurable via `VK_LIFECYCLE_HOOK_SCRIPT` env var (default: nothing). willikins-specific path stops being baked into the bridge. |
| **O** logging | `vk.bridge.cli` uses standard `logging` module — daemon configures it |
| **P** domain types | `GhIssue` already has v2-shaped equivalents in `vk.parser.Plan` etc. `ParsedBody` deleted with the body-parsing retirement. |

## Renderer + dep gating change

The bug at `src/vk/render.py:51-72` — `_lifecycle_label(phase, obs)` cannot see deps because of its signature.

New signature:

```python
def _lifecycle_label(
    phase: PhaseDoc,
    obs: PhaseObservation | None,
    plan: Plan,                                # NEW
    observed: GhState,                         # NEW
) -> LabelDef | None:
    if _phase_complete(phase, obs):
        return None
    if phase.phase.tag == "manual":
        return MANUAL
    if not _deps_satisfied(phase, plan, observed):   # NEW
        return VK_BLOCKED                            # NEW lifecycle label
    if obs is None:
        return VK_READY
    # ... existing PR/assignee logic unchanged
```

New helper:

```python
def _deps_satisfied(phase: PhaseDoc, plan: Plan, observed: GhState) -> bool:
    """True iff every phase in `phase.depends_on` is complete."""
    phase_by_number = {p.phase.number: p for p in plan.phases}
    for dep_n in phase.phase.depends_on:
        dep_phase = phase_by_number.get(dep_n)
        if dep_phase is None:
            return False  # bad reference; conservative — treat as blocked
        if not _phase_complete(dep_phase, observed.phases.get(dep_n)):
            return False
    return True
```

New lifecycle label in `vk.labels`:

```python
VK_BLOCKED = LabelDef(
    name="vk-blocked",
    color="aaaaaa",  # dim grey — distinct from vk-ready's blue
    description="Blocked on dependency — waiting for predecessor phase(s) to complete",
)
```

### Behavior of dep-completion transitions

When phase 1 finishes (Issue closes, PR merges), the next bridge tick re-runs `render()`. Phase 2's `_deps_satisfied` returns True now → projection switches from `VK_BLOCKED` to `VK_READY` → diff emits a label change (remove `vk-blocked`, add `vk-ready`) → apply executes it → next tick syncs phase 2 to VK.

The renderer becomes the **single source of truth for "is this phase ready."** No more body-text dep parsing anywhere. The bridge stops needing `check_blockers`.

### State-machine surface gains

The rebuild folds two concerns currently in the bridge into the renderer's projection model:

- **Issue close on done** (E in inventory): `vk.render` already projects `state: CLOSED` when a phase is complete. `vk.diff` already emits `IssueStateChange`. `vk.apply` already executes it. **The legacy `close_gh_issue_for_card` is therefore mostly redundant** — it exists as a belt-and-braces close when the agent's PR body omits `Fixes #N`. In the rebuild, this is captured by the v2 path's existing close-on-complete; the belt-and-braces becomes a config-driven "force-close-on-card-Done" option in `vk.bridge.lifecycle` for the rare case.
- **PR state → card status** (F in inventory): currently legacy polls in-progress/in-review cards. In the rebuild, `vk.observe` already reads `linked_prs`; `vk.render._lifecycle_label` already projects `IN_PROGRESS`/`PR_READY` from PR state. The bridge's job becomes "project card status from rendered phase status," not "poll PRs independently." The PR state machine is collapsed into the existing renderer.

### Label removal is automatic via the existing diff layer

The renderer returns a SINGLE lifecycle label per phase from `_lifecycle_label` (or `None` for complete phases). The renderer's main loop combines it with static labels (`plan:*`, `spec:*`, `phase:N`) into a set. The diff layer at `src/vk/diff.py:138-150` then computes:

```python
rendered_managed = frozenset(ld.name for ld in ri.labels if _is_managed(ld.name))
observed_managed = frozenset(lbl for lbl in obs.issue_labels if _is_managed(lbl))
to_add = rendered_managed - observed_managed
to_remove = observed_managed - rendered_managed
```

So when a dep completes and `_lifecycle_label` switches from `VK_BLOCKED` to `VK_READY`:

- `rendered_managed` contains `vk-ready` but not `vk-blocked`
- `observed_managed` contains `vk-blocked` but not `vk-ready`
- Diff emits `IssueLabelChange(add={vk-ready}, remove={vk-blocked})`

Adding `VK_BLOCKED` to the lifecycle vocabulary therefore only requires the renderer change — the diff layer handles all transitions automatically because `vk-blocked` starts with `vk-` (already in `MANAGED_LABEL_PREFIXES`). The same auto-management applies to every lifecycle transition (vk-ready ↔ vk-blocked, vk-ready → in-progress, in-progress → pr-ready, pr-ready → closed).

**One special case: `vk-synced`** is bridge-owned, not renderer-projected. The renderer explicitly preserves it from observed labels (`render.py:288-289`) so diff doesn't strip it. The rebuild keeps this pattern — `vk-synced` is added by `vk.bridge.dispatch` after MCP card creation, preserved by the renderer's projection, never managed by `_lifecycle_label`.

## Bridge log shape (operator-facing)

Every tick's FIRST log line is a timestamped version banner:

```
[bridge] - v2.1.7 - 2026-05-17 14:32:00 UTC - tick
```

Format: `[bridge] - v<vk.__version__> - <YYYY-MM-DD HH:MM:SS UTC> - tick`. UTC timestamp (avoids timezone confusion when operators tail logs from anywhere). Uses Python's standard `datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")`.

Implemented in `vk.bridge.cli.main()` at the top, before any other work. The version comes from `vk.__version__` (already exposed via `importlib.metadata.version("vk")`), so the banner auto-updates with releases. Subsequent log lines stay as-is (the existing `log(...)` helper becomes a stdlib-logging configuration).

Why first thing per tick: when operators investigate a "what was the bridge doing at 14:30?" question, the per-tick banner is the index. Today the existing legacy bridge has only `[bridge] starting — dry_run=False`, no version, no timestamp — incident debugging requires correlating against cron's own logging.

## VK card title and description format

Today the dispatch builds:

- Title: `gh#{N}: {gh_issue_title}` — where `gh_issue_title` is the full renderer-built `[repo] slug · Phase N/M · subject`
- Description: just `{issue_url}`

Result: the VK board's title column is overwhelmed by the long gh issue title, while the description field contains only a URL.

The rebuilt `vk.bridge.dispatch` builds:

- Title: `gh#{N}: [{repo}]` — minimal identifier (issue number + repo)
- Description (multi-line):
  ```
  {plan.meta.plan}
  Phase {phase.phase.number}/{len(plan.phases)}
  {phase.phase.title}
  {issue_url}
  ```

Concrete example:

| Field | Today | After rebuild |
|---|---|---|
| Title | `gh#272: [derio-net/frank] 2026-05-17--orch--paperclip-litellm-agents · Phase 2/6 · opencode_local — declarative wiring` | `gh#272: [derio-net/frank]` |
| Description | `https://github.com/derio-net/frank/issues/272` | `2026-05-17--orch--paperclip-litellm-agents`<br>`Phase 2/6`<br>`opencode_local — declarative wiring`<br>`https://github.com/derio-net/frank/issues/272` |

Why: the title becomes scannable in the VK board (just identifies which issue, on which repo); the description carries the full structured context that operators need to understand the phase without clicking through to gh.

Data sourcing: `vk.bridge.dispatch.dispatch_phase` already has access to the `Plan` and the specific `PhaseDoc` (the function signature takes both). `len(plan.phases)` gives the total phase count. `repo` comes from `parse_issue_url(phase.tracking_issue).repo`. The gh issue title (today's source of the long card title) is no longer needed for the card — `dispatch_phase` builds the card's title + description from plan structure directly.

The gh issue title itself stays unchanged — the renderer still produces `[repo] slug · Phase N/M · subject` via `vk.render._build_title`. Operators reading gh see the full context; operators reading VK get the minimal card.

## CLI / install / cron shape

**Public CLI:** unchanged. `vk` retains all existing commands. NO `vk bridge` verb.

**Hidden entry:** `python -m vk.bridge` runs `src/vk/bridge/__main__.py` which calls `vk.bridge.cli.main()`. One tick across all configured repos.

**Wrapper script** (`/opt/vk-bridge/run.sh`, written by `install.sh --install-bridge`):

```bash
#!/bin/bash
# Wrapper for cron / supercronic / systemd. Stable invocation path
# independent of the venv layout.
exec /opt/vk-bridge-venv/bin/python -m vk.bridge "$@"
```

(Path `/opt/vk-bridge/run.sh` is the default; `VK_BRIDGE_WRAPPER_PATH` env var overrides for non-standard deployments.)

**install.sh `--install-bridge` flag:**

1. Verify `uv tool install vk` (or `pip install vk`) has already happened.
2. Resolve the active `vk` Python interpreter path.
3. Write the wrapper script to `${VK_BRIDGE_WRAPPER_PATH:-/opt/vk-bridge/run.sh}`.
4. Print (NOT write) the recommended cron line to stdout for the operator:
   ```
   To schedule the bridge, add to your cron config:
   */2 * * * * /opt/vk-bridge/run.sh
   ```

The actual crontab edit stays a deployment-time operation — `install.sh` doesn't mess with cron files.

**Cron in agent-images:** kali's supercronic config gets `*/2 * * * * /opt/vk-bridge/run.sh` (replacing today's invocation of `/opt/vk-bridge-venv/bin/python /opt/scripts/vk-issue-bridge.py`).

## agent-images impact (complete delta)

**Deleted:**
- `kali/scripts/vk-issue-bridge.py` (1089 LOC)
- `kali/scripts/vk_mcp_client.py`
- `kali/scripts/__pycache__/vk-issue-bridge.cpython-*.pyc` (auto-cleaned)

**Modified:**
- `kali/Dockerfile`: drop the `COPY` line for `vk-issue-bridge.py` (if present); confirm `vk` venv install still produces a runnable `python -m vk.bridge`
- `kali/supercronic.conf` (or equivalent): cron line points at the wrapper
- `kali/tests/test_vk_issue_bridge.py`, `kali/tests/test_vk_bridge_integration.py`: meaningful test cases relocate to `superpowers-for-vk/tests/`; agent-images keeps only a smoke test
- `kali/scripts/__init__.py` (if it exists for imports): cleaned up

**Added (optional):**
- `kali/scripts/vk-bridge-run.sh`: the wrapper, IF you'd rather have it tracked in agent-images instead of written by install.sh. (Default is install.sh writes it — simpler, single source of truth.)

## Testing strategy

**Unit tests** (`superpowers-for-vk/tests/unit/`):
- `test_render_deps.py`: extensive coverage of `_deps_satisfied` and the new `_lifecycle_label` signature
- `test_bridge_dispatch.py`: `vk.bridge.dispatch` happy path + failure modes, using a new `FakeMcpClient`
- `test_bridge_workspaces.py`, `test_bridge_lifecycle.py`, `test_bridge_pr_state.py`, `test_bridge_slots.py`, `test_bridge_dedup.py`, `test_bridge_metrics.py`, `test_bridge_prompt.py`, `test_bridge_config.py`: one file per new module
- `test_mcp_client.py`: covers the wire protocol (extracted from agent-images tests)

**Integration tests** (`superpowers-for-vk/tests/integration/`):
- `test_bridge_e2e.py`: full tick using `FakeGhClient` + `FakeMcpClient` + real `discover_plans` against a tmp_path fixture plan
- Existing `test_v2_apply_e2e.py` stays and grows a dep-gating case

**Smoke test** (`agent-images/kali/tests/`):
- `test_bridge_smoke.py`: build/import-only — assert `python -m vk.bridge --dry-run` exits 0 inside the Kali container (no MCP / gh access required for dry-run)

## Process change (codify "read the bridge first")

Add to `CLAUDE.md` (project-level) AND to `~/.claude/rules/vk-plan-override.md` (user-level):

> **Bridge audit rule.** For any brainstorm, spec, or plan touching dispatch / sync / cron / VK card / workspace / GitHub Issue label-lifecycle surfaces, the brainstorm MUST start by reading the active bridge implementation (today: `agent-images/kali/scripts/vk-issue-bridge.py` until the v2 rebuild ships, then `superpowers-for-vk/src/vk/bridge/`). Confabulating what the bridge does without reading it is the root cause documented in [#147](https://github.com/derio-net/superpowers-for-vk/issues/147).

After the rebuild ships, the rule simplifies — "read `vk.bridge.*`" is just one repo's code, easier to enforce.

Also: every spec should include an explicit "Architectural ownership" section naming the SINGLE file/function responsible for each contract-level invariant. If that file doesn't take enough context in its signature to enforce the invariant, fix the signature in the same spec. (The dep-gating bug existed precisely because `_lifecycle_label`'s signature couldn't see deps, and no spec ever said "the renderer owns this" — so the missing parameter was invisible.)

## Phased delivery sketch

Detail belongs in the plan (vk-plan after this spec is approved). Rough shape:

- **Phase 1 — Renderer dep gating + cross-repo RepoLabelEnsure fix** (smallest, most contained — both are state-machine / projection-layer changes)
  - Signature change to `_lifecycle_label` (accepts plan + observed)
  - New `VK_BLOCKED` label
  - `_deps_satisfied` helper
  - **Group RepoLabelEnsure by destination repo** in `vk.diff` (the cross-repo `#132` fix, folded from the archived cross-repo spec)
  - **`v2_plan_cross_repo` fixture** under `tests/unit/fixtures/`
  - **FakeGhClient tightening** (label-must-exist-on-repo rule, regression guard)
  - Tests cover both dep gating AND cross-repo routing
  - Version bump + ships independently
  - Validates the labels-now-honest assumption AND closes the cross-repo silent-failure mode end-to-end

- **Phase 2 — `vk._mcp_client` + `vk.bridge.dispatch`**
  - Move MCP wire client into vk package
  - Extract dispatch dedup from `sync_issue` + `_McpAdapter.create_card`
  - Add `FakeMcpClient`
  - agent-images legacy still runs unchanged; we're building the new home in parallel

- **Phase 3 — Workspaces + lifecycle + PR state**
  - `vk.bridge.workspaces`, `vk.bridge.lifecycle`, `vk.bridge.pr_state`
  - Migrate D, E, F (some folded into renderer projection)

- **Phase 4 — Slots + dedup + metrics + prompt + config**
  - `vk.bridge.slots`, `vk.bridge.dedup`, `vk.bridge.metrics`, `vk.bridge.prompt`, `vk.bridge.config`
  - Migrate H, I, K, L, J, M

- **Phase 5 — `vk.bridge.cli` + `__main__.py` + wrapper + install.sh flag**
  - Wire everything together
  - New entry usable in parallel with legacy bridge
  - `--install-bridge` flag in install.sh

- **Phase 6 — Cutover**
  - Update agent-images Dockerfile + cron to call the new entry
  - Delete `vk-issue-bridge.py` + `vk_mcp_client.py`
  - Relocate tests
  - Verify cron tick produces same end-to-end behavior

Each phase is one PR (per the repo's "one phase = one PR" convention). Phase 6 spans both repos and is the only cross-repo phase.

## Out of scope

- **Multi-version coexistence of the bridge.** Hard cutover — once Phase 6 lands, only the v2 path runs. (v1 was already retired in PR #129; no compat shim needed.)
- **Changes to the public `vk` CLI surface.** Existing operator commands stay. No `vk bridge` verb. No flag rename across existing commands.
- **Changes to the plan-as-folder format** (`_meta.yaml`, `_prose.md`, `NN.yaml`). Schema stays.
- **Re-design of the workspace ↔ card join key.** Today uses `<simple_id> -> gh#<N>` name-prefix matching. Migration preserves the convention; if the join is fragile we file separately.
- **Re-design of the metrics shape.** Pushgateway URL, label names, counter names all stay identical. Migration is mechanical.
- **Changes to the VK MCP API.** Wire protocol stays as-is.
- **The willikins lifecycle-transition script itself.** Just becomes configurable; the script's content / location is the operator's concern.
- **Dispatch-reachability gate** (`docs/superpowers/specs/2026-05-17-dispatch-reachability-gate-design.md` — already shipped via PR #146). Orthogonal; stays as-is.
- **`vk plan create` non-transactional bug** (#133). Orthogonal.
- **Shared-PV stale-checkout auto-pull** (drift class 2 from the now-archived kali-pv spec). Folded into Phase 5's `vk.bridge.cli` — the tick can `git fetch && git checkout main` per managed repo as a precondition. Out-of-scope for explicit design here but the implementation will handle it.

## Architectural ownership (the missing section pattern this spec introduces)

Each invariant gets one owner. If the owner's signature can't enforce the invariant, that's the bug to fix in the same spec.

| Invariant | Owner (after rebuild) | Signature must accept |
|---|---|---|
| "vk-ready means this phase is actually ready to dispatch (deps satisfied, no PR/assignee, not complete)" | `vk.render._lifecycle_label` | `(phase, obs, plan, observed)` — extended from today's `(phase, obs)` |
| "vk-synced means a VK card exists for this Issue" | `vk.bridge.dispatch` (sets the label after MCP confirms card creation) | The MCP-create response |
| "Only one workspace exists per phase Issue" | `vk.bridge.dispatch` (dedup-via-title check before `start_workspace`) | The existing-titles set + the proposed card title |
| "Workspaces archive when their card reaches Done" | `vk.bridge.workspaces` (driven by `vk.bridge.pr_state` cascade) | Card status + workspace list |
| "Orphaned workspaces are reaped" | `vk.bridge.workspaces.reap_orphans` | Live card set + workspace list |
| "MAX_CONCURRENT workspaces never exceeded" | `vk.bridge.slots` (gate at `vk.bridge.tick`) | Current `count_active_ws` + max from config |
| "Bridge tick is idempotent (re-running yields same end state)" | `vk.bridge.tick` (delegates to `apply()` for label/state, and to `dispatch` which dedups) | Plan + observed state |
| "Plan + spec are reachable to dispatch consumers" | `vk.commands.apply_cmd._check_plan_reachable_on_origin_head` (already shipped) | Plan + repo_root |
| "Per-phase mutations route to the phase's `tracking_issue` repo (not `target_repo`)" | `vk.diff` (existing per-issue routing at `diff.py:134-171`) + `vk.bridge.dispatch` (workspace branch repo) | The full `Plan` object (so each emitter can resolve per-phase repos) |
| "Repo-wide concerns (label ensure) group by destination repo" | `vk.diff` (one `RepoLabelEnsure` per distinct destination repo, union of managed labels) | `Plan` + projected labels per phase |

## Verification checklist (apply during execution)

- [ ] Renderer `_lifecycle_label` accepts plan + observed in its signature
- [ ] `VK_BLOCKED` label exists in `vk.labels` and is part of `MANAGED_LIFECYCLE_LABELS`
- [ ] Dep-gating tests: phase with unsatisfied deps projects `vk-blocked`; phase with satisfied deps projects `vk-ready`; transitions both directions
- [ ] `RepoLabelEnsure` groups by destination repo (cross-repo `#132` fix folded into Phase 1)
- [ ] `tests/unit/fixtures/v2_plan_cross_repo/` exists with at least one phase on a foreign repo
- [ ] `FakeGhClient.edit_issue_labels` and `create_issue` raise when add-labels aren't pre-ensured on the destination repo (regression guard)
- [ ] `vk.bridge.dispatch` exists; `sync_issue` and `_McpAdapter.create_card` are deleted; both old call sites use `vk.bridge.dispatch`
- [ ] `vk._mcp_client` exists; `agent-images/.../vk_mcp_client.py` deleted
- [ ] `python -m vk.bridge --dry-run` exits 0 (no side effects) when run inside the Kali container
- [ ] `python -m vk.bridge` (real run) produces the same end-state as the legacy bridge for a known fixture: same VK cards created, same labels added, same workspaces started
- [ ] `agent-images/kali/scripts/vk-issue-bridge.py` deleted
- [ ] `install.sh --install-bridge` writes the wrapper script and prints the cron-line recommendation
- [ ] All concerns A-P from the inventory map cleanly to one module each
- [ ] No body-text parsing for dispatch decisions anywhere (only renderer-derived state drives dispatch)
- [ ] CLAUDE.md updated with the bridge-audit rule
- [ ] Version bump applied; `uv.lock` updated

## Acceptance tests (BDD-style, executable as pytest)

The complete feature spectrum, framed as capabilities. Each capability becomes one (or a small handful of) executable pytest test(s) with a Given/When/Then docstring. Phase annotations (`implementation: Phase N`) are implementation-tracking comments only — they do not change what's asserted.

Test discovery convention: each capability lives at the indicated test file path. CI runs all of these on every PR; an acceptance test failing means the rebuild has regressed against its specced behavior.

### Group A — Renderer + dep gating

#### A1: Phase with unsatisfied deps projects `vk-blocked`
<!-- implementation: Phase 1 -->

**Location:** `tests/unit/test_render_deps.py::test_phase_with_unsatisfied_deps_projects_vk_blocked`

```python
def test_phase_with_unsatisfied_deps_projects_vk_blocked(tmp_path):
    """
    GIVEN a plan with two phases — phase 1 (depends_on=[]) and phase 2
          (depends_on=[1]) — neither dispatched
    WHEN  render(plan, observed=empty) is called
    THEN  rendered.issue_per_phase[1].labels contains 'vk-ready'
    AND   rendered.issue_per_phase[2].labels contains 'vk-blocked'
    AND   rendered.issue_per_phase[2].labels does NOT contain 'vk-ready'
    """
```

#### A2: Phase with satisfied deps projects `vk-ready`
<!-- implementation: Phase 1 -->

**Location:** `tests/unit/test_render_deps.py::test_phase_with_satisfied_deps_projects_vk_ready`

```python
def test_phase_with_satisfied_deps_projects_vk_ready(tmp_path):
    """
    GIVEN a plan with phases 1 (depends_on=[]) and 2 (depends_on=[1])
    AND   phase 1's tracking_issue is observed as CLOSED with a merged PR
    AND   phase 1's state.completion.at is set
    WHEN  render(plan, observed) is called
    THEN  rendered.issue_per_phase[2].labels contains 'vk-ready'
    AND   does NOT contain 'vk-blocked'
    """
```

#### A3: Blocked→ready transition when dep completes
<!-- implementation: Phase 1 -->

**Location:** `tests/unit/test_render_deps.py::test_blocked_to_ready_transition_when_dep_completes`

```python
def test_blocked_to_ready_transition_when_dep_completes(tmp_path):
    """
    GIVEN phase 2 currently labelled vk-blocked (because phase 1 was incomplete)
    WHEN  phase 1 completes (observed: closed + merged PR; state.completion.at set)
    AND   diff(rendered, observed, plan) is computed
    THEN  the mutation list contains an IssueLabelChange that removes
          'vk-blocked' AND adds 'vk-ready' on phase 2's tracking issue
    """
```

#### A4: Fan-in DAG — phase blocked until ALL deps complete
<!-- implementation: Phase 1 -->

**Location:** `tests/unit/test_render_deps.py::test_fan_in_phase_blocked_until_all_deps_complete`

```python
def test_fan_in_phase_blocked_until_all_deps_complete(tmp_path):
    """
    GIVEN a plan where phase 4 has depends_on=[1, 2, 3]
    AND   phases 1 and 2 are complete; phase 3 is in-progress
    WHEN  render(plan, observed) is called
    THEN  rendered.issue_per_phase[4].labels contains 'vk-blocked'

    GIVEN the same state but with phase 3 now complete
    WHEN  render(plan, observed) is called again
    THEN  rendered.issue_per_phase[4].labels contains 'vk-ready'
    """
```

#### A5: Manual phase unaffected by dep gating
<!-- implementation: Phase 1 -->

**Location:** `tests/unit/test_render_deps.py::test_manual_phase_unaffected_by_dep_gating`

```python
def test_manual_phase_unaffected_by_dep_gating():
    """
    GIVEN a manual-tagged phase with depends_on=[1] and phase 1 incomplete
    WHEN  render() is called
    THEN  the phase projects 'manual' lifecycle label (not 'vk-blocked')
    """
```

#### A6: Bad dep reference treated as blocked
<!-- implementation: Phase 1 -->

**Location:** `tests/unit/test_render_deps.py::test_bad_dep_reference_treated_as_blocked`

```python
def test_bad_dep_reference_treated_as_blocked(tmp_path):
    """
    GIVEN a plan with phase 2 having depends_on=[99] (no phase 99 exists)
    WHEN  render(plan, observed) is called
    THEN  rendered.issue_per_phase[2].labels contains 'vk-blocked'
          (conservative: bad reference = treat as never-satisfiable)
    """
```

### Group B — Dispatch consolidation + MCP move

#### B1: `vk.bridge.dispatch` is the single canonical dispatcher
<!-- implementation: Phase 2 -->

**Location:** `tests/unit/test_bridge_dispatch.py::test_dispatch_creates_card_and_workspace`

```python
def test_dispatch_creates_card_and_workspace():
    """
    GIVEN a vk-ready phase with tracking_issue set, no existing VK card
    AND   a FakeMcpClient configured to record calls
    WHEN  vk.bridge.dispatch.dispatch_phase(phase, plan, mcp_client, ...) is called
    THEN  mcp_client received a create_issue call with title 'gh#<n>: <phase title>'
    AND   mcp_client received an update_issue call setting status 'In progress'
    AND   mcp_client received a list_repos call
    AND   mcp_client received a start_workspace call with executor='CLAUDE_CODE'
          and the correct branch
    AND   mcp_client received a link_workspace_issue call
    AND   the function returned a DispatchResult with card_id and workspace_id
    """
```

#### B2: Both legacy and v2 call sites use the same dispatch implementation
<!-- implementation: Phase 2 -->

**Location:** `tests/unit/test_bridge_dispatch.py::test_no_duplicate_dispatch_implementations`

```python
def test_no_duplicate_dispatch_implementations():
    """
    GIVEN the rebuilt codebase
    WHEN  grep for VK MCP orchestration sequences (create_issue → update_issue →
          list_repos → start_workspace → link_workspace_issue)
    THEN  only one such sequence exists, in vk.bridge.dispatch
    (Regression guard: the duplication between sync_issue and _McpAdapter.create_card
    in the legacy bridge is what motivated the consolidation.)
    """
```

#### B3: MCP client lives in vk package
<!-- implementation: Phase 2 -->

**Location:** `tests/unit/test_mcp_client.py::test_mcp_client_importable_from_vk`

```python
def test_mcp_client_importable_from_vk():
    """
    GIVEN the rebuilt vk package
    WHEN  importing vk._mcp_client
    THEN  the VkMcpClient class is available
    AND   the VkMcpError exception is available
    AND   agent-images/kali/scripts/vk_mcp_client.py no longer exists
    """
```

#### B4: FakeMcpClient exists for tests
<!-- implementation: Phase 2 -->

**Location:** `tests/unit/fakes.py::FakeMcpClient` (existence test)

```python
def test_fake_mcp_client_implements_protocol():
    """
    GIVEN FakeMcpClient from tests/unit/fakes.py
    THEN  it implements vk.bridge.VkMcpClient Protocol (create_card, update_card)
    AND   it records all calls in a `calls` list
    AND   it supports configurable failure injection (fail_on_call=N)
    """
```

### Group C — Workspace lifecycle + PR state

#### C1: Workspace archives when card reaches Done
<!-- implementation: Phase 3 -->

**Location:** `tests/unit/test_bridge_workspaces.py::test_workspace_archives_on_card_done`

```python
def test_workspace_archives_on_card_done():
    """
    GIVEN a FakeMcpClient with workspace 'ws-1' linked to card 'card-1'
          whose name follows the bridge convention '<simple_id> -> gh#<N>'
    AND   card 'card-1' has just transitioned to status 'Done'
    WHEN  vk.bridge.workspaces.archive_for_card(client, simple_id) is called
    THEN  client.update_workspace('ws-1', archived=True) was called
    """
```

#### C2: Orphan workspace reaping
<!-- implementation: Phase 3 -->

**Location:** `tests/unit/test_bridge_workspaces.py::test_reap_orphans_archives_workspaces_with_no_live_card`

```python
def test_reap_orphans_archives_workspaces_with_no_live_card():
    """
    GIVEN three workspaces named '5 -> gh#100', '6 -> gh#101', '7 -> gh#102'
    AND   cards exist for simple_ids 5 and 6 (5 is In-progress, 6 is Done);
          no card exists for simple_id 7
    AND   no workspace is pinned
    WHEN  vk.bridge.workspaces.reap_orphans(client) is called
    THEN  workspaces for simple_ids 6 (card Done) and 7 (no card) are archived
    AND   workspace for simple_id 5 (card In-progress) is NOT archived
    """
```

#### C3: PR open → card In-progress → In-review
<!-- implementation: Phase 3 -->

**Location:** `tests/unit/test_bridge_pr_state.py::test_in_progress_transitions_to_in_review_when_pr_opens`

```python
def test_in_progress_transitions_to_in_review_when_pr_opens():
    """
    GIVEN a VK card currently 'In progress'
    AND   the card's latest_pr_status is 'open' (non-draft PR exists)
    WHEN  vk.bridge.pr_state.tick(client) is called
    THEN  client.update_issue(card_id, status='In review') was called
    """
```

#### C4: PR merged → card In-review → Done, cascades archive + close
<!-- implementation: Phase 3 -->

**Location:** `tests/unit/test_bridge_pr_state.py::test_in_review_transitions_to_done_when_pr_merges`

```python
def test_in_review_transitions_to_done_when_pr_merges():
    """
    GIVEN a VK card currently 'In review'
    AND   the card's latest_pr_status is 'merged'
    WHEN  vk.bridge.pr_state.tick(client) is called
    THEN  client.update_issue(card_id, status='Done') was called
    AND   client.update_workspace(linked_ws_id, archived=True) was called
    AND   a gh issue close request was made for the linked Issue (if PR body
          omitted Fixes #N; otherwise gh auto-close fired earlier)
    """
```

#### C5: Phase complete → renderer projects CLOSED state → diff emits IssueStateChange
<!-- implementation: Phase 3 (folds bridge's belt-and-braces close into renderer) -->

**Location:** `tests/unit/test_render.py::test_complete_phase_projects_closed_state`

```python
def test_complete_phase_projects_closed_state():
    """
    GIVEN a phase with state.completion.at set, all steps ticked,
          and observed: 1 merged PR, no open non-draft PRs
    WHEN  render(plan, observed) is called
    THEN  rendered.issue_per_phase[N].state == 'CLOSED'

    GIVEN diff(rendered, observed_with_open_issue, plan) is computed
    THEN  an IssueStateChange(repo=..., issue_number=N, new_state='CLOSED')
          mutation is emitted
    """
```

### Group D — Operational concerns

#### D1: Tick respects MAX_CONCURRENT
<!-- implementation: Phase 4 -->

**Location:** `tests/unit/test_bridge_slots.py::test_tick_defers_excess_phases_when_slots_exhausted`

```python
def test_tick_defers_excess_phases_when_slots_exhausted(monkeypatch):
    """
    GIVEN MAX_CONCURRENT=2 and 3 currently-active workspaces (slots = 0)
    AND   a plan with 2 vk-ready phases (none synced yet)
    WHEN  vk.bridge.tick(plan, gh, mcp_client) is called
    THEN  no create_card calls were made
    AND   TickResult.skipped >= 2 (or 'deferred', depending on naming)

    GIVEN the same setup but MAX_CONCURRENT=5 (slots = 2)
    WHEN  tick() is called
    THEN  exactly 2 create_card calls were made
    """
```

#### D2: Tick dedups by card title
<!-- implementation: Phase 4 -->

**Location:** `tests/unit/test_bridge_dedup.py::test_existing_card_just_stamps_vk_synced`

```python
def test_existing_card_just_stamps_vk_synced():
    """
    GIVEN a vk-ready Issue #42 with title fragment 'gh#42: Foo'
    AND   a VK card already exists with title 'gh#42: Foo' (somehow created
          out-of-band, e.g. manual)
    WHEN  vk.bridge.tick(plan, gh, mcp_client) is called
    THEN  NO create_card call was made (dedup detected by title)
    AND   the Issue was labelled 'vk-synced' (idempotency stamp)
    """
```

#### D3: Metrics emit on success / failure / heartbeat
<!-- implementation: Phase 4 -->

**Location:** `tests/unit/test_bridge_metrics.py`

```python
def test_metrics_emit_on_dispatch_success(monkeypatch):
    """
    GIVEN a fake Pushgateway HTTP endpoint that records pushed metrics
    WHEN  vk.bridge.tick() successfully syncs one phase
    THEN  exactly one 'willikins_vk_bridge_sync_total' increment was pushed
    """

def test_metrics_emit_on_dispatch_failure(monkeypatch):
    """
    GIVEN a FakeMcpClient configured to fail on create_card
    WHEN  vk.bridge.tick() attempts to sync one phase and fails
    THEN  a 'willikins_vk_bridge_failure_total' metric was pushed with
          reason matching the failure mode
    """

def test_heartbeat_pushed_at_end_of_tick():
    """
    GIVEN a successful tick
    THEN  a 'willikins_heartbeat_last_success_timestamp' gauge was pushed
    """
```

#### D4: Unknown-repo phases skipped with metric
<!-- implementation: Phase 4 -->

**Location:** `tests/unit/test_bridge_config.py::test_unknown_repo_skipped_with_metric`

```python
def test_unknown_repo_skipped_with_metric(monkeypatch):
    """
    GIVEN VK's known repos = {'frank', 'willikins'}
    AND   a plan with target_repo='unknown-repo' AND a phase with vk-ready
    WHEN  vk.bridge.tick() runs
    THEN  no MCP calls were made for that phase
    AND   a 'willikins_vk_bridge_failure_total{reason="unknown_repo"}' metric
          was pushed
    """
```

#### D5: Configurable lifecycle hook
<!-- implementation: Phase 4 -->

**Location:** `tests/unit/test_bridge_lifecycle.py::test_lifecycle_hook_invoked_when_configured`

```python
def test_lifecycle_hook_invoked_when_configured(tmp_path, monkeypatch):
    """
    GIVEN VK_LIFECYCLE_HOOK_SCRIPT=/path/to/hook.sh (a test script that
          records its args)
    WHEN  vk.bridge.dispatch successfully creates a card
    THEN  the hook script was invoked with args (issue_url, 'in-progress')

    GIVEN VK_LIFECYCLE_HOOK_SCRIPT is unset
    WHEN  vk.bridge.dispatch successfully creates a card
    THEN  no external script was invoked
    """
```

### Group E — CLI + install

#### E1: vk public CLI has no `bridge` verb
<!-- implementation: Phase 5 -->

**Location:** `tests/unit/test_cli.py::test_no_bridge_verb_exposed`

```python
def test_no_bridge_verb_exposed():
    """
    GIVEN the public vk CLI
    WHEN  invoking `vk --help`
    THEN  'bridge' does NOT appear in the command list
    (Bridge is invoked via `python -m vk.bridge` from a wrapper, never as
    a public verb.)
    """
```

#### E2: `python -m vk.bridge --dry-run` exits 0
<!-- implementation: Phase 5 -->

**Location:** `tests/integration/test_bridge_entry_point.py::test_python_dash_m_dry_run_exits_zero`

```python
def test_python_dash_m_dry_run_exits_zero():
    """
    GIVEN the rebuilt vk package installed
    WHEN  subprocess.run(['python', '-m', 'vk.bridge', '--dry-run']) is invoked
          in an env with no MCP / gh access (purely import-only)
    THEN  the process exits 0
    AND   no GH/MCP side effects occurred
    """
```

#### E3: install.sh `--install-bridge` writes wrapper + prints cron line
<!-- implementation: Phase 5 -->

**Location:** `tests/integration/test_install_bridge.py::test_install_bridge_flag_writes_wrapper`

```python
def test_install_bridge_flag_writes_wrapper(tmp_path, monkeypatch):
    """
    GIVEN a temp HOME with vk already installed via `uv tool install`
    AND   VK_BRIDGE_WRAPPER_PATH=/tmp/test-wrapper/run.sh
    WHEN  bash scripts/install.sh --install-bridge is run
    THEN  /tmp/test-wrapper/run.sh exists and is executable
    AND   its contents exec the active vk venv's `python -m vk.bridge "$@"`
    AND   stdout contains a recommended crontab line referencing the wrapper path
    """
```

#### E4: Stale-checkout auto-pull before plan read
<!-- implementation: Phase 5 (folds in drift-class-2 from the now-archived kali-pv spec) -->

**Location:** `tests/integration/test_bridge_cli.py::test_tick_pulls_managed_repos_before_discover`

```python
def test_tick_pulls_managed_repos_before_discover(tmp_path):
    """
    GIVEN a managed repo checkout at <tmp>/repos/foo whose origin/main is
          ahead by 2 commits (the local working tree is stale)
    AND   the new commits add a plan dir docs/superpowers/plans/new-plan/
    WHEN  vk.bridge.cli.main() runs a tick
    THEN  before discover_plans(repo='foo', ...) is called, the bridge ran
          `git fetch && git checkout main && git pull --ff-only` (or equivalent)
          in <tmp>/repos/foo
    AND   discover_plans then finds the new-plan/ directory
    """
```

### Group F — End-to-end + cutover

#### F1: Full tick produces same end-state as legacy bridge for a known fixture
<!-- implementation: Phase 6 -->

**Location:** `tests/integration/test_bridge_e2e.py::test_tick_end_state_matches_legacy_for_fixture`

```python
def test_tick_end_state_matches_legacy_for_fixture(tmp_path):
    """
    GIVEN a fixture multi-phase plan with mixed depends_on shape
    AND   a FakeMcpClient + FakeGhClient pre-loaded with the dispatched Issues
    WHEN  vk.bridge.tick() runs one tick
    THEN  the resulting label state on every Issue matches the documented
          expectation:
          - root phases (depends_on=[]) → vk-ready + vk-synced
          - blocked phases (deps not done) → vk-blocked (no vk-ready, no vk-synced)
          - completed phases → no lifecycle label, state CLOSED
          - manual phases → manual label
    AND   the resulting workspace count == count of root phases just synced
    """
```

#### F2: agent-images bridge files no longer exist
<!-- implementation: Phase 6 -->

**Location:** `tests/integration/test_cutover.py::test_agent_images_bridge_files_deleted`

```python
def test_agent_images_bridge_files_deleted():
    """
    GIVEN a clean checkout of derio-net/agent-images at origin/main HEAD
    WHEN  checking the file system
    THEN  kali/scripts/vk-issue-bridge.py does NOT exist
    AND   kali/scripts/vk_mcp_client.py does NOT exist
    (Test runs cross-repo via `gh api repos/derio-net/agent-images/contents/...`
    in CI; locally falls back to checking a pinned ref via git.)
    """
```

#### F3: Kali container smoke test
<!-- implementation: Phase 6 -->

**Location:** `agent-images/kali/tests/test_bridge_smoke.py::test_python_m_vk_bridge_dry_run_in_container`

```python
def test_python_m_vk_bridge_dry_run_in_container():
    """
    GIVEN the kali Docker image just built
    WHEN  invoking `docker run --rm <kali-image> python -m vk.bridge --dry-run`
    THEN  the process exits 0
    AND   stdout contains 'vk.bridge: dry-run complete' (or equivalent sentinel)
    """
```

#### F4: Idempotency — re-running tick yields no further mutations
<!-- implementation: spans Phase 1 + Phase 6 -->

**Location:** `tests/integration/test_bridge_e2e.py::test_tick_is_idempotent`

```python
def test_tick_is_idempotent():
    """
    GIVEN a plan in a steady-state (all phases dispatched, labels match
          renderer projection)
    WHEN  vk.bridge.tick() runs once
    AND   vk.bridge.tick() runs again immediately after
    THEN  the second run made no MCP mutations
    AND   the second run made no GH label changes
    AND   the second run made no GH Issue state changes
    """
```

#### F5: Legacy body-text-driven dispatch retired
<!-- implementation: Phase 6 -->

**Location:** `tests/integration/test_bridge_e2e.py::test_standalone_vk_ready_issue_without_plan_is_ignored`

```python
def test_standalone_vk_ready_issue_without_plan_is_ignored():
    """
    GIVEN a vk-ready GitHub Issue that is NOT backed by any v2 plan
          (manual `gh issue create --label vk-ready` outside the plan workflow)
    AND   no plan in any managed repo references it as tracking_issue
    WHEN  vk.bridge.tick() runs
    THEN  no MCP calls were made for this Issue
    AND   no labels were changed on this Issue
    (Legacy bridge would have parsed the body and dispatched; new bridge ignores.)
    """
```

### Group H — Multi-repo (cross-repo dispatch)

This group folds in the acceptance surface previously specced under the now-archived `docs/superpowers/archived-specs/2026-05-16-cross-repo-label-ensure-design.md` (archived 2026-05-17 via PR #149). The capabilities below cover both the `RepoLabelEnsure` bug fix and the broader multi-repo architectural rule that every per-phase mutation routes to `parse_issue_url(phase.tracking_issue).repo`.

#### H1: `RepoLabelEnsure` groups by destination repo
<!-- implementation: Phase 1 (folded from #132 / archived cross-repo spec) -->

**Location:** `tests/unit/test_v2_diff.py::test_diff_emits_ensure_per_destination_repo`

```python
def test_diff_emits_ensure_per_destination_repo(tmp_path):
    """
    GIVEN a plan with target_repo='derio-net/repo-a'
    AND   phase 1 has tracking_issue='https://github.com/derio-net/repo-b/issues/100'
    AND   phase 2 has no tracking_issue (undispatched)
    WHEN  diff(rendered, observed, plan) is computed
    THEN  exactly two RepoLabelEnsure mutations are emitted
    AND   one targets 'derio-net/repo-a' (for phase 2's projected IssueCreate)
    AND   one targets 'derio-net/repo-b' (for phase 1's existing tracking issue)
    """
```

#### H2: Per-issue mutations route to `tracking_issue.repo` (regression guard)
<!-- implementation: Phase 1 (locks down already-correct behavior at diff.py:134-171) -->

**Location:** `tests/unit/test_v2_diff.py::test_diff_routes_per_issue_mutations_to_tracking_repo`

```python
def test_diff_routes_per_issue_mutations_to_tracking_repo(tmp_path):
    """
    GIVEN a plan with target_repo='derio-net/repo-a'
    AND   phase 1 dispatched to 'derio-net/repo-b' with a drifted body, vk-ready,
          and an extra stale label
    WHEN  diff(rendered, observed, plan) is computed
    THEN  every IssueLabelChange / IssueStateChange / IssueBodyChange for phase 1
          carries repo='derio-net/repo-b' (NEVER 'derio-net/repo-a')
    (Regression guard: the per-issue routing at diff.py:134-171 is already
    correct; this pins it so no future refactor regresses to target_repo-only.)
    """
```

#### H3: Single-repo plans produce one ensure (regression guard)
<!-- implementation: Phase 1 -->

**Location:** `tests/unit/test_v2_diff.py::test_diff_single_repo_plan_emits_one_ensure`

```python
def test_diff_single_repo_plan_emits_one_ensure(tmp_path):
    """
    GIVEN a single-repo plan (target_repo == every phase's tracking_issue repo)
    WHEN  diff(rendered, observed, plan) is computed
    THEN  exactly one RepoLabelEnsure mutation is emitted
    AND   its repo == plan.meta.target_repo
    (Common-case regression guard — the rebuild must not change single-repo behavior.)
    """
```

#### H4: Fully-cross-repo plans don't ensure on `target_repo`
<!-- implementation: Phase 1 -->

**Location:** `tests/unit/test_v2_diff.py::test_diff_fully_cross_repo_plan_skips_target_repo_ensure`

```python
def test_diff_fully_cross_repo_plan_skips_target_repo_ensure(tmp_path):
    """
    GIVEN a plan where every phase is dispatched on a foreign repo
          (none on plan.meta.target_repo) and no phases are undispatched
    WHEN  diff(rendered, observed, plan) is computed
    THEN  no RepoLabelEnsure mutation targets plan.meta.target_repo
    AND   one RepoLabelEnsure exists per distinct foreign destination repo
    (Strictly more correct than today: no phases live on target_repo, so no
    labels are needed there.)
    """
```

#### H5: `FakeGhClient` tightening — label must exist on repo before applying
<!-- implementation: Phase 1 (regression-prevention test infrastructure) -->

**Location:** `tests/unit/test_fakes.py::test_fake_gh_client_rejects_unensured_labels`

```python
def test_fake_gh_client_rejects_unensured_labels():
    """
    GIVEN a FakeGhClient that has NOT received an `ensure_labels` call for
          a given label on a given repo
    WHEN  edit_issue_labels(repo, number, add={label}) is invoked
    THEN  FakeGhError is raised with a 'label not found' message

    GIVEN the same setup
    WHEN  create_issue(repo, ..., labels={label}) is invoked
    THEN  FakeGhError is raised similarly
    (Models real gh's actual constraint. Without this, the cross-repo bug
    would not be unit-test-catchable — labels would 'just work' in tests
    even though prod would fail.)
    """
```

#### H6: `apply()` end-to-end cross-repo execution
<!-- implementation: Phase 1 -->

**Location:** `tests/unit/test_v2_apply.py::test_apply_executes_cross_repo_mutations_through_correct_repo`

```python
def test_apply_executes_cross_repo_mutations_through_correct_repo(tmp_path):
    """
    GIVEN the v2_plan_cross_repo fixture
    AND   FakeGhClient preloaded with foreign-repo issue OPEN + vk-ready
    WHEN  diff() and apply() run end-to-end
    THEN  no apply failures occurred (labels ensured on the right repo first)
    AND   the foreign repo's issue is now CLOSED in the fake's state
    AND   the foreign repo's body was updated (no stale body)
    AND   the FakeGhClient.calls log shows the mutations targeted the
          tracking_issue repo, not target_repo
    """
```

#### H7: Cross-repo bridge tick — `vk-synced` lands on tracking-issue repo
<!-- implementation: Phase 6 (full bridge tick, supersedes the earlier F6) -->

**Location:** `tests/integration/test_bridge_e2e.py::test_cross_repo_phase_dispatches_to_correct_repo`

```python
def test_cross_repo_phase_dispatches_to_correct_repo():
    """
    GIVEN a plan with target_repo='derio-net/foo' and a phase with
          tracking_issue='https://github.com/derio-net/bar/issues/100'
    WHEN  vk.bridge.tick() runs
    THEN  vk.bridge.dispatch is called with workspace branch repo='derio-net/bar'
    AND   the vk-synced label is added on derio-net/bar#100 (NOT derio-net/foo)
    AND   the workspace name follows '<simple_id> -> gh#100' convention
    """
```

#### H9: VK card title and description follow the new format
<!-- implementation: Phase 2 (vk.bridge.dispatch) -->

**Location:** `tests/unit/test_bridge_dispatch.py::test_card_title_is_minimal_and_description_is_structured`

```python
def test_card_title_is_minimal_and_description_is_structured():
    """
    GIVEN a plan with meta.plan='2026-05-17--orch--paperclip-litellm-agents'
    AND   phase 2 of 6 with title='opencode_local — declarative wiring'
    AND   tracking_issue='https://github.com/derio-net/frank/issues/272'
    WHEN  vk.bridge.dispatch.dispatch_phase(plan, phase, ...) calls create_card
    THEN  the MCP create_issue call's title argument equals:
          'gh#272: [derio-net/frank]'
    AND   the description argument equals (newline-joined):
          '2026-05-17--orch--paperclip-litellm-agents'
          'Phase 2/6'
          'opencode_local — declarative wiring'
          'https://github.com/derio-net/frank/issues/272'
    """
```

#### H8: Cross-repo fixture present
<!-- implementation: Phase 1 (fixture infrastructure) -->

**Location:** `tests/integration/test_repo_invariants.py::test_v2_plan_cross_repo_fixture_exists`

```python
def test_v2_plan_cross_repo_fixture_exists():
    """
    GIVEN the repo
    THEN  tests/unit/fixtures/v2_plan_cross_repo/_meta.yaml exists
    AND   at least one phase yaml has tracking_issue pointing at a
          repo different from _meta.target_repo
    AND   at least one phase yaml has tracking_issue=null (undispatched)
    (Without this fixture, multi-repo tests have no canonical input.)
    """
```

### Group G — Cross-cutting / contract

#### G1: Logging uses standard `logging` module
<!-- implementation: Phase 5 -->

**Location:** `tests/unit/test_bridge_cli.py::test_logging_uses_stdlib_logging`

```python
def test_logging_uses_stdlib_logging(caplog):
    """
    GIVEN vk.bridge.cli configured with logging at INFO level
    WHEN  the tick runs and emits a status message
    THEN  caplog.records contains the message (proving stdlib logging is used,
          not bare print)
    """
```

#### G2: CLAUDE.md contains the bridge-audit rule
<!-- implementation: Phase 6 (or earlier — docs-only sub-task) -->

**Location:** `tests/integration/test_repo_invariants.py::test_claude_md_has_bridge_audit_rule`

```python
def test_claude_md_has_bridge_audit_rule():
    """
    GIVEN CLAUDE.md in the repo root
    WHEN  searching its content
    THEN  it contains a section/paragraph mentioning 'bridge audit rule'
          AND references vk.bridge.* as the canonical read-target post-rebuild
    """
```

#### G3: Architectural ownership section in this spec (regression guard for the pattern)
<!-- implementation: docs-only, validated in this spec itself -->

**Location:** `tests/integration/test_repo_invariants.py::test_v2_bridge_rebuild_spec_has_architectural_ownership_section`

```python
def test_v2_bridge_rebuild_spec_has_architectural_ownership_section():
    """
    GIVEN this spec doc on disk
    WHEN  searching for the '## Architectural ownership' section
    THEN  the section exists
    AND   contains a table mapping every contract-level invariant to one
          owner module + the signature that lets it enforce
    (Regression guard so the pattern isn't dropped from future specs that
    copy this one as a template.)
    """
```

#### G5: Bridge tick log shape (timestamped version banner)
<!-- implementation: Phase 5 -->

**Location:** `tests/unit/test_bridge_cli.py::test_tick_first_log_line_has_version_and_timestamp`

```python
def test_tick_first_log_line_has_version_and_timestamp(caplog):
    """
    GIVEN vk.bridge.cli.main() is invoked
    WHEN  the tick starts
    THEN  the first log line matches the regex:
          ^\[bridge\] - v\d+\.\d+\.\d+ - \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC - tick$
    AND   the version equals vk.__version__
    AND   the timestamp is within the last second when the test runs
    """
```

#### G4: All inventory concerns A-P map to a new home (no orphans)
<!-- implementation: Phase 6 (verification step) -->

**Location:** `tests/integration/test_cutover.py::test_all_inventory_concerns_have_a_new_home`

```python
def test_all_inventory_concerns_have_a_new_home():
    """
    GIVEN the bridge inventory in this spec (concerns A through P)
    AND   the migration table mapping each to a new location (or DELETED)
    WHEN  iterating the migration table after Phase 6 lands
    THEN  every non-DELETED concern's new home module is importable
    AND   every DELETED concern is genuinely absent (no dead code shim)
    """
```

### Group I — Operational resilience

End-to-end failure modes the bridge must survive without manual operator intervention. Surfaced during the 2026-05-17 feasibility audit as gaps in the original capability list.

#### I1: MCP subprocess startup failure → loud exit
<!-- implementation: Phase 5 (vk.bridge.cli) -->

**Location:** `tests/integration/test_bridge_resilience.py::test_bridge_exits_loud_when_mcp_subprocess_fails_to_start`

```python
def test_bridge_exits_loud_when_mcp_subprocess_fails_to_start(monkeypatch):
    """
    GIVEN an environment where `vibe-kanban-mcp` and `npx` are both missing
    WHEN  vk.bridge.cli.main() attempts to construct the MCP client
    THEN  process exits non-zero
    AND   stderr contains a message naming the missing binary AND the install
          fix ('apt install nodejs npm' OR 'npm install -g vibe-kanban')
    (Don't silently spin; fail loud so the operator knows the container is
    misconfigured rather than discovering it via stuck cards 30 minutes later.)
    """
```

#### I2: MCP subprocess crash mid-tick → tick aborts cleanly
<!-- implementation: Phase 5 -->

**Location:** `tests/integration/test_bridge_resilience.py::test_tick_aborts_cleanly_on_mcp_subprocess_death`

```python
def test_tick_aborts_cleanly_on_mcp_subprocess_death(monkeypatch):
    """
    GIVEN an MCP client whose subprocess dies after the first call_tool
          (simulated via FakeMcpClient that raises BrokenPipeError on the
          second call)
    WHEN  vk.bridge.tick() is mid-iteration and the next MCP call fails
    THEN  the tick aborts cleanly (no half-state)
    AND   a failure metric is pushed with reason='mcp_subprocess_died'
    AND   no GH labels were added that the workspace creation didn't finish
    (Next tick re-runs from a clean state.)
    """
```

#### I3: gh rate-limit response → backoff
<!-- implementation: Phase 5 -->

**Location:** `tests/integration/test_bridge_resilience.py::test_tick_backs_off_on_gh_rate_limit`

```python
def test_tick_backs_off_on_gh_rate_limit(monkeypatch):
    """
    GIVEN a FakeGhClient that returns HTTP 403 with 'API rate limit exceeded'
          on the next call
    WHEN  vk.bridge.tick() encounters the error
    THEN  the tick logs a backoff message AND returns (does not proceed)
    AND   no MCP mutations were attempted
    AND   a failure metric is pushed with reason='gh_rate_limited'
    (Tick frequency is `*/2 * * * *` today and we're keeping it. Even at this
    frequency, peak load can briefly burst above the per-hour rate limit for
    repos with many vk-ready issues. Backoff prevents the bridge from
    hammering when it should yield.)
    """
```

#### I4: Tick overlap prevention (lock file)
<!-- implementation: Phase 5 -->

**Location:** `tests/integration/test_bridge_resilience.py::test_second_concurrent_tick_aborts_early`

```python
def test_second_concurrent_tick_aborts_early(tmp_path):
    """
    GIVEN a long-running tick (simulated via a sleep in dispatch) holds the
          bridge lock file at /var/run/vk-bridge.lock (or operator-configured
          path via VK_BRIDGE_LOCK_PATH)
    WHEN  a second `python -m vk.bridge` is invoked while the first is still
          running
    THEN  the second invocation logs 'tick already in progress, skipping'
    AND   exits 0 (not an error — just a no-op)
    AND   no MCP mutations are attempted by the second invocation
    (Even with 2-minute cron, a slow tick could overlap. Lock file is cheap
    insurance.)
    """
```

#### I5: Card created without workspace → reverse-reap on next tick
<!-- implementation: Phase 3 (extends workspace reaping) -->

**Location:** `tests/integration/test_bridge_resilience.py::test_card_without_workspace_logged_and_recoverable`

```python
def test_card_without_workspace_logged_and_recoverable():
    """
    GIVEN a VK card exists matching the bridge's title convention
          (gh#<N>: [...]) but no workspace is linked to it
    WHEN  vk.bridge.tick() runs and dispatch sees the duplicate-title
          condition
    THEN  dispatch logs a warning ('card without workspace: <simple_id>')
    AND   either re-creates the workspace (if VK_BRIDGE_RECOVER_ORPHAN_CARDS=1)
          OR leaves the card alone with vk-synced already on the gh issue
    (Today's bridge has reap_orphan_workspaces but no inverse — orphan cards
    without workspaces are silently stuck.)
    """
```

#### I6: Plan deleted between ticks → in-flight cards left intact, logged
<!-- implementation: Phase 5 -->

**Location:** `tests/integration/test_bridge_resilience.py::test_plan_deletion_between_ticks_does_not_purge_cards`

```python
def test_plan_deletion_between_ticks_does_not_purge_cards():
    """
    GIVEN a plan was discovered in tick N and produced VK cards
    AND   the plan dir is deleted from disk before tick N+1
    WHEN  vk.bridge.tick() runs at N+1
    THEN  discover_plans no longer returns the plan
    AND   existing cards for that plan's phases are NOT auto-archived
    AND   a warning is logged once per missing plan: 'plan <slug> no longer
          on disk; cards left intact for manual review'
    (Conservative: never delete operator's work via missing-input inference.)
    """
```

#### I7: Operator manually changes a managed label → renderer reverses
<!-- implementation: Phase 1 (renderer projection is the source of truth) -->

**Location:** `tests/integration/test_bridge_resilience.py::test_renderer_reverses_manual_label_change`

```python
def test_renderer_reverses_manual_label_change():
    """
    GIVEN a phase whose Issue has been observed in steady state with vk-ready
    AND   an operator manually removes vk-ready via `gh issue edit`
    WHEN  vk.bridge.tick() runs next
    THEN  the renderer projects vk-ready (state-machine says it's still ready)
    AND   the diff layer emits IssueLabelChange(add={vk-ready})
    AND   apply restores the label
    (Renderer projection IS the source of truth. If operators want a phase
    out of the dispatch queue, they update plan state — not labels.)
    """
```

#### I8: `vk apply` and `vk.bridge.tick` racing for the same plan → idempotent
<!-- implementation: Phase 6 (verification step) -->

**Location:** `tests/integration/test_bridge_resilience.py::test_concurrent_apply_and_tick_are_idempotent`

```python
def test_concurrent_apply_and_tick_are_idempotent():
    """
    GIVEN a plan with steady-state Issues
    WHEN  an operator runs `vk apply --yes` simultaneously with the bridge's
          tick (both call apply() on overlapping mutations)
    THEN  the final gh state matches what either path alone would produce
    AND   no Issue ends up with duplicate labels
    AND   no Issue ends up with conflicting state
    (Both paths use the same render → diff → apply chain; apply() is
    idempotent by construction. This test is a regression guard.)
    """
```

### Running the acceptance suite

Locally (during development of any phase):

```
uv run pytest tests/unit/test_render_deps.py tests/unit/test_bridge_*.py tests/integration/test_bridge_*.py tests/integration/test_cutover.py -v
```

In CI: included in the standard `uv run pytest -q --no-cov` invocation. The acceptance tests are NOT marked or gated separately — they're first-class unit/integration tests that happen to map 1:1 to spec capabilities.

Test traceability: each capability's test docstring repeats the Given/When/Then. `pytest -v` output then reads like a BDD report; `grep -r "implementation: Phase N" tests/` lists every test associated with a given delivery phase, so you can confirm a phase's tests are landing alongside the phase's code.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-05-17-v2-bridge-rebuild | `derio-net/superpowers-for-vk` | `docs/superpowers/plans/2026-05-17-v2-bridge-rebuild/` | — |
| 2026-05-17-v2-bridge-cutover | `derio-net/agent-images` | `docs/superpowers/plans/2026-05-17-v2-bridge-cutover/` | `2026-05-17-v2-bridge-rebuild` (`v2.2.0` tag) |
