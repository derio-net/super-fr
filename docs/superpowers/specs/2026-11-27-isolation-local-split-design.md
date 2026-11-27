# Split the free functions out of `isolation/local.py`

## Background

`packages/fr/src/fr/isolation/local.py` is 3,171 lines (budget 3,200 in
`tests/unit/test_tripwire_module_budget.py:25`). The architecture review for #1318 (§5.3 of
`docs/superpowers/audits/2026-11-16-architecture-review.md`) found it mixes four groups of
module-level free functions with the one class that drives a workspace,
`LocalWorktreeDevcontainerTarget` (`local.py:1203` to the end). Issue #1517 plans the four
groups out into their own modules. This change does all four in one pull request, one plan
phase per module.

Measured at `da66accc5` (the branch base), the groups and what reads them:

| Group | Lines | Holds | Read by |
|---|---|---|---|
| runner | 50-171 | `Runner`, `_BASE32`, `devcontainer_id`, `_missing_binary`, `subprocess_runner`, `_home`, `GcSpawner`, `_detached_gc_spawn`, `_noop_gc_spawn` | the class; every other group needs `Runner` |
| reap | 172-302, 319-325 | `MergeVerification`, `GcWorkspace`, `_forge_refused`, `GcAction`, `ReapHazard`, `ReapRefused`, `_merged_before`, `_hazard_detail`, `_UP_REMEDY`, `_FR_OWNED_EXCLUDES` | the class; landing reads `MergeVerification` |
| landing | 303-318, 328-838 | `_ARCHIVED_KINDS`, `_SUPERPOWERS` (read only by landing), `_archived_path` … `branch_changes_present`, `recorded_start` | the class (`branch_changes_present`, `recorded_start`) |
| branchrefs | 839-1176 | `_realpath`, `_main_worktree_root`, `RemoteView`, `BranchDecision`, `_NETWORK_TIMEOUT_S`, `_BATCH_SSH`, `network_env`, `fetch_placement`, `run_network`, `_forge_runner`, `resolve_branch_refs`, `_why`, `_short`, `_plural`, `_local_row`, `classify_branch` | the class; landing reads `_main_worktree_root` |

The dependency graph between the groups has no cycle: runner ← reap ← landing, and
runner ← branchrefs ← landing. The VK profile refusal (`local.py:1177-1202`) and the class stay.

Callers outside `local.py`: `fr/isolation/routing.py:19`, `external.py:28`, `hostworktree.py:20`,
`fr/commands/isolation_cmd.py:23`, `fr/commands/archive_cmd.py:56`, `fr/triage/gitseam.py:1458`,
`fr-herdr/src/fr_herdr/runner.py:118` (the private `_main_worktree_root`), and about 23 test
files plus `tests/scenarios/fr-ops-gate-{probes,stage}.sh`. Tests that patch a name on the
module: `tests/unit/test_isolation.py:1473` (`"fr.isolation.local.branch_changes_present"`,
read by the class, so it stays valid), `test_isolation_gc_routing.py:129,146`
(`local_mod.subprocess.Popen`, read by `_detached_gc_spawn`), and
`test_forge_host_trust.py:293` / `test_isolation_forge_refusal.py:46,129` (`client_for`,
read only by the class, `local.py:3027,3169`).

Two guards name the file: `tests/unit/test_isolation_network_timeouts.py:249`
(`test_local_py_holds_no_forge_cli_argv`, an AST scan of `local.py` for a `gh`/`glab`/`tea`
argv) and `tests/unit/test_vk_compat_removed.py:59` (`REMEDY_FILES`, no bare
`fr isolation up` remedy; `_UP_REMEDY` moves into `reap.py`). The VK allowlist entries
(`test_vk_compat_removed.py:262-270`) name lines that stay in `local.py`.

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
module that holds a remedy string; the VK allowlist still matches lines that exist.
R6. `local.py`'s line budget is lowered in the same diff to within the tripwire's headroom of its
new line count, and `local.py` stays a held module.
R7. Nothing in `LocalWorktreeDevcontainerTarget` changes: the teardown order in
`_down_worktree_tail` and its early return when the worktree path exists are untouched.
R8. No user-observable behaviour changes; the change fragment is a `patch`.

## Design

Four phases, in dependency order, each a pure move followed by its caller migration:

1. **runner** — `runner.py` gets lines 50-171. `local.py` imports what the class uses.
   `test_isolation_gc_routing.py` patches `subprocess.Popen` through the module that holds
   `_detached_gc_spawn` (R4).
2. **reap** — `reap.py` gets the reap group (it imports `IsolationError` from `types`).
   `_UP_REMEDY` moves with it, so `reap.py` joins `REMEDY_FILES`.
3. **branchrefs** — `branchrefs.py` gets lines 839-1176 (imports `Runner` from `runner`,
   `CommandRunner` from `fr.ghclient`). `fr_herdr/runner.py` imports `_main_worktree_root`
   from it. `branchrefs.py` joins the forge-argv scan.
4. **landing** — `landing.py` gets lines 303-318 (`_ARCHIVED_KINDS`, `_SUPERPOWERS`) and 328-838
   (imports from `runner`, `reap`, `branchrefs`). The class keeps calling
   `branch_changes_present` through `local`'s own global, so
   `"fr.isolation.local.branch_changes_present"` stays a valid patch target. This phase lowers
   the budget to the final count (R6); each earlier phase lowers it as far as the 400-line
   headroom rule requires.

Each new module carries a docstring naming what it holds and pointing at #1517.
`AGENTS.md`'s module-budget paragraph needs no edit (the five held modules do not change).

## Design shape

```
packages/fr/src/fr/isolation/
  local.py        ~2000 lines: imports + VK refusal + LocalWorktreeDevcontainerTarget (unchanged)
+ runner.py       Runner, devcontainer_id, subprocess_runner, _home, gc spawners
+ reap.py         MergeVerification, GcWorkspace, GcAction, ReapHazard, ReapRefused, _UP_REMEDY …
+ branchrefs.py   network_env, run_network, fetch_placement, resolve_branch_refs, classify_branch …
+ landing.py      branch_changed_paths, branch_changes_present, recorded_start, _fork_point …

imports (arrow = "imports from"):
  local ──▶ runner, reap, branchrefs, landing
  landing ──▶ reap, branchrefs, runner
  branchrefs ──▶ runner
  reap ──▶ types          (no new module imports local)
```

## Verification

strategy: none
- isolation-local-split-guards: none — the forge-argv, remedy and budget tripwires run in this PR's CI, with the whole unit suite unchanged in behaviour
gate: developer
