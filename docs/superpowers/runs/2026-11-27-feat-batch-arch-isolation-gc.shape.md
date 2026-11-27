# Shape of the change — isolation gc moves to GcSweeper (#1521)

```
packages/fr/src/fr/isolation/
  local.py   2084 → 1688 lines   LocalWorktreeDevcontainerTarget
               gc(dry_run)  ──→  GcSweeper(self).gc(dry_run)        (only delegation left)
               stays: _spawn_gc, _teardown_container, _labelled_containers,
                      _sweep_dangling_images, _stale_state_reapable,
                      _label_reap, _vsc_images, _referenced_images, _pr_from, _reap_hazard
             - 14 gc methods leave (no forwarding methods)
+ gc.py      466 lines           GcSweeper(target)      local imported under TYPE_CHECKING only
               gc(dry_run): flock → [_gc_one_guarded(rec) for rec in _discover_workspaces()]
                            + target._sweep_dangling_images + 3 hygiene sweeps
               _acquire_gc_lock  _gc_one_guarded  _gc_one  _reap_or_classify
               _gc_stale_state   _merged_by_content (sibling: type(self._target)(...))
               _discover_workspaces  _repo_states  _worktree_dirs  _resolve_state
               _empty_repo_dirs  _sweep_empty_repo_dirs  _sweep_stale_sessions
               _sweep_agent_worktrees
               ── through self._target: _labelled_containers, _sweep_dangling_images,
                  _label_reap, _pr_from, run, repo_root
  hostworktree.py                HostWorktreeTarget overrides             (unchanged)

tests/unit/
  test_isolation.py (6), test_isolation_gc_routing.py (1), test_isolation_preserve.py (2)
                                 receiver: target._m(...) → GcSweeper(target)._m(...)
+ test_isolation_gc_sweeper.py   host-mode record: HostWorktree sweep sends no docker;
                                 devcontainer sweep sends the labelled `docker ps -a`;
                                 `python -P -c "import fr.isolation.gc"` exits 0
  test_isolation_network_timeouts.py   ISOLATION_MODULES += fr.isolation.gc
  test_vk_compat_removed.py            REMEDY_FILES += isolation/gc.py
  test_tripwire_module_budget.py       local.py budget 2125 → 1735
.changes/feat-batch-arch-isolation-gc.yaml   patch
docs/explainers/fr-isolation.md              reviewed stamp only
```
