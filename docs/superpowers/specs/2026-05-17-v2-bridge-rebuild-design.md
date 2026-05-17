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

- **Phase 1 — Renderer dep gating** (smallest, most contained)
  - Signature change to `_lifecycle_label`
  - New `VK_BLOCKED` label
  - `_deps_satisfied` helper
  - Tests + version bump + ships independently
  - Validates the labels-now-honest assumption end-to-end

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
- **Cross-repo `RepoLabelEnsure` bug** (#132 / PR #140). Orthogonal; re-implementation continues independently.
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

## Verification checklist (apply during execution)

- [ ] Renderer `_lifecycle_label` accepts plan + observed in its signature
- [ ] `VK_BLOCKED` label exists in `vk.labels` and is part of `MANAGED_LIFECYCLE_LABELS`
- [ ] Dep-gating tests: phase with unsatisfied deps projects `vk-blocked`; phase with satisfied deps projects `vk-ready`; transitions both directions
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

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
