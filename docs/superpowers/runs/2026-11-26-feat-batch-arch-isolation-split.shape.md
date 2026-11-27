```
packages/fr/src/fr/isolation/
  local.py        ~ 3171 -> 2084 lines: imports + _UP_REMEDY, _FR_OWNED_EXCLUDES
                    + VK refusal + LocalWorktreeDevcontainerTarget (bodies untouched)  R7
+ runner.py         137  Runner, devcontainer_id, subprocess_runner, _home, gc spawners    R1
+ reap.py           143  MergeVerification, GcWorkspace, GcAction, ReapHazard, ReapRefused R1
+ branchrefs.py     354  network_env, run_network, fetch_placement, resolve_branch_refs,
                         classify_branch, _main_worktree_root …                          R1
+ landing.py        546  branch_changed_paths, branch_changes_present, recorded_start,
                         _fork_point, _landed_at …                                       R1

imports (arrow = "imports from"; none of the four imports local)                         R2
  local ──▶ runner, reap, branchrefs, landing
  landing ──▶ runner, reap, branchrefs, types
  branchrefs ──▶ runner, types, ghclient
  reap ──▶ types, artifacts.paths        runner ──▶ stdlib

callers ~ import from the new module, no shim in local                                   R3
  isolation/{routing,external,hostworktree,agent_worktrees}.py, commands/{isolation,archive}_cmd.py,
  triage/gitseam.py (lazy), closeout.py, fr_herdr/runner.py, ~20 test files (imports only)  R4
tests/unit/test_isolation_network_timeouts.py
                  ~ forge-argv scan parametrized over ISOLATION_MODULES (all five)       R5
                  + no new isolation module imports fr.isolation.local                   R2
tests/unit/test_tripwire_module_budget.py   ~ local.py 3200 -> 2125                      R6
docs (7 pages)    ~ reviewed stamps only, still true                                     R8
.changes/feat-batch-arch-isolation-split.yaml  + bump: patch                             R8
```
