# Split the free functions out of `isolation/local.py`

## Background

`packages/fr/src/fr/isolation/local.py` is 3,171 lines (budget 3,200 in
`tests/unit/test_tripwire_module_budget.py:27`). The architecture review for #1318 (§5.3 of
`docs/superpowers/audits/2026-11-16-architecture-review.md`) found it mixes four groups of
module-level free functions with the one class that drives a workspace,
`LocalWorktreeDevcontainerTarget` (`local.py:1203` to the end). Issue #1517 plans the four
groups out into their own modules. This change does all four in one pull request, one plan
phase per module.

Measured at `da66accc5` (the branch base), the groups and what reads them:

| Group | Lines | Holds | Read by |
|---|---|---|---|
| runner | 50-171 | `Runner`, `_BASE32`, `devcontainer_id`, `_missing_binary`, `subprocess_runner`, `_home`, `GcSpawner`, `_detached_gc_spawn`, `_noop_gc_spawn` | the class; branchrefs and landing need `Runner` |
| reap | 172-297 | `MergeVerification`, `GcWorkspace`, `_forge_refused`, `GcAction`, `ReapHazard`, `ReapRefused`, `_merged_before`, `_hazard_detail` | the class; landing reads `MergeVerification` |
| landing | 303-318, 328-838 | `_ARCHIVED_KINDS`, `_SUPERPOWERS` (read only by landing), `_archived_path` … `branch_changes_present`, `recorded_start` | the class (`branch_changes_present`, `recorded_start`) |
| branchrefs | 839-1172 | `_realpath`, `_main_worktree_root`, `RemoteView`, `BranchDecision`, `_NETWORK_TIMEOUT_S`, `_BATCH_SSH`, `network_env`, `fetch_placement`, `run_network`, `_forge_runner`, `resolve_branch_refs`, `_why`, `_short`, `_plural`, `_local_row`, `classify_branch` | the class; landing reads `_main_worktree_root` |

The dependency graph between the groups has no cycle: runner and reap are leaves (reap imports
only `fr.isolation.types` for `IsolationError`/`IsolationState` and `fr.artifacts.paths` for
`KIND_DIRS`, plus stdlib), branchrefs imports runner, and landing imports runner, reap and
branchrefs. What stays in `local.py`: `_UP_REMEDY` (`local.py:301`) and `_FR_OWNED_EXCLUDES`
(`:325`), which sit inside #1517's reap line range but are read only by the class
(`:1274, 1553, 1590, 2688, 2695, 2710`; `:2932`), so they stay beside their reader; the VK
profile refusal with its leading comment (`local.py:1174-1202`); and the class.

Callers outside `local.py`: `fr/isolation/routing.py:19`, `external.py:28`, `hostworktree.py:20`,
`fr/commands/isolation_cmd.py:23`, `fr/commands/archive_cmd.py:56`, `fr/triage/gitseam.py:1458`,
`fr-herdr/src/fr_herdr/runner.py:118` (the private `_main_worktree_root`), and 23 test files.
`tests/scenarios/fr-ops-gate-{probes,stage}.sh` import the module but patch only `client_for`,
which stays, so they need no edit. Tests that patch a name on the module: `tests/unit/test_isolation.py:1473` (`"fr.isolation.local.branch_changes_present"`,
read by the class, so it stays valid), `test_isolation_gc_routing.py:129,146`
(`local_mod.subprocess.Popen` — the shared `subprocess` module object, so the patch holds
wherever `_detached_gc_spawn` lives; only its import at `:20` moves), and
`test_forge_host_trust.py:293` / `test_isolation_forge_refusal.py:46,129` (`client_for`,
read only by the class, `local.py:3027,3169`).

Two guards name the file: `tests/unit/test_isolation_network_timeouts.py:249`
(`test_local_py_holds_no_forge_cli_argv`, an AST scan of `local.py` for a `gh`/`glab`/`tea`
argv) and `tests/unit/test_vk_compat_removed.py:59` (`REMEDY_FILES`, no bare
`fr isolation up` remedy; `_UP_REMEDY` stays in `local.py`, so no new module holds a remedy
string). The VK allowlist entries (`test_vk_compat_removed.py:263-274`) name lines that stay
in `local.py`.

Docs currency: seven pages cover a path this change edits — `docs/explainers/fr-isolation.md`
(`isolation/**`), `docs/explainers/fr-dispatch.md` and `docs/reference/dispatch-lifecycle.md`
(`fr_herdr/runner.py`), `docs/herdr-control-sessions.md` (`fr-herdr/src/**`),
`docs/explainers/fr-progress.md` (`archive_cmd.py`), `docs/explainers/fr-triage.md`
(`triage/**`) and `docs/reference/cli.md` (`commands/*.py`). None names a moved function or
`local.py`, so each stays true and needs only its `reviewed` stamp.

## Requirements

R1. The runner group moves to `fr/isolation/runner.py`, the reap group to `fr/isolation/reap.py`,
the landing group to `fr/isolation/landing.py` and the branchrefs group to
`fr/isolation/branchrefs.py`, each name unchanged and each body byte-identical apart from imports.
R2. No new module imports `fr.isolation.local`; the four modules import each other only along the
graph in Background.
R3. Every caller, in `packages/*/src`, `tests/` and `tests/scenarios/`, imports a moved name from
its new module. `local.py` imports only the names its own code uses and keeps no re-export list.
R4. A test that patches a moved name patches it where the code that reads it now looks it up;
no test changes otherwise, and no assertion changes.
R5. The forge-argv tripwire scans `local.py` and each new module; `REMEDY_FILES` lists each new
module that holds a remedy string (none, as `_UP_REMEDY` stays); the VK allowlist still matches
lines that exist.
R6. `local.py`'s line budget is lowered in the same diff to within the tripwire's headroom of its
new line count, and `local.py` stays a held module.
R7. Nothing in `LocalWorktreeDevcontainerTarget` changes: the teardown order in
`_down_worktree_tail` and its early return when the worktree path exists are untouched.
R8. No user-observable behaviour changes; the change fragment is a `patch`; every docs page
whose `covers:` matches an edited path gets its `reviewed` stamp moved with a "still true" note,
so `fr docs check` passes.

## Design

Four phases, in dependency order, each a pure move followed by its caller migration:

1. **runner** — `runner.py` gets lines 50-171. `local.py` imports what the class uses.
   `test_isolation_gc_routing.py` only moves its `_detached_gc_spawn` import; its
   `local_mod.subprocess` patch is the shared module and needs no edit (R4).
2. **reap** — `reap.py` gets lines 172-297 (imports `IsolationError`, `IsolationState` from
   `fr.isolation.types` and `KIND_DIRS` from `fr.artifacts.paths`). `_UP_REMEDY` and
   `_FR_OWNED_EXCLUDES` stay in `local.py`.
3. **branchrefs** — `branchrefs.py` gets lines 839-1172 (imports `Runner` from `runner`,
   `CommandRunner` from `fr.ghclient`). `fr_herdr/runner.py` imports `_main_worktree_root`
   from it. `branchrefs.py` joins the forge-argv scan.
4. **landing** — `landing.py` gets lines 303-318 (`_ARCHIVED_KINDS`, `_SUPERPOWERS`) and 328-838
   (imports from `runner`, `reap`, `branchrefs`). The class keeps calling
   `branch_changes_present` through `local`'s own global, so
   `"fr.isolation.local.branch_changes_present"` stays a valid patch target. This phase lowers
   the budget to the final count (R6); each earlier phase lowers it as far as the 400-line
   headroom rule requires. The same phase moves the `reviewed` stamp of the seven covered
   pages in Background (R8).

Each new module carries a docstring naming what it holds and pointing at #1517.
`AGENTS.md`'s module-budget paragraph needs no edit (the five held modules do not change).

## Design shape

```
packages/fr/src/fr/isolation/
  local.py        ~2000 lines: imports + VK refusal + LocalWorktreeDevcontainerTarget (unchanged)
+ runner.py       Runner, devcontainer_id, subprocess_runner, _home, gc spawners
+ reap.py         MergeVerification, GcWorkspace, GcAction, ReapHazard, ReapRefused, _hazard_detail
+ branchrefs.py   network_env, run_network, fetch_placement, resolve_branch_refs, classify_branch …
+ landing.py      branch_changed_paths, branch_changes_present, recorded_start, _fork_point …

imports (arrow = "imports from"):
  local ──▶ runner, reap, branchrefs, landing
  landing ──▶ reap, branchrefs, runner
  branchrefs ──▶ runner
  reap ──▶ types, artifacts.paths   (runner and reap are leaves; no new module imports local)
```

## Verification

strategy: none
- isolation-local-split-guards: none — the forge-argv, remedy and budget tripwires run in this PR's CI, with the whole unit suite unchanged in behaviour
gate: developer

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-27-isolation-local-split | `derio-net/super-fr` | `2026-11-27-isolation-local-split` | — |
