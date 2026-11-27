# isolation/local.py: garbage collection moves to a `GcSweeper` collaborator

Issues: derio-net/super-fr#1521.

## Background

The architecture review for #1318 (`docs/superpowers/audits/2026-11-16-architecture-review.md`,
section 6.3) proposed moving the host-wide gc out of `LocalWorktreeDevcontainerTarget`. #1517
already moved the module's free functions out (`runner`, `reap`, `branchrefs`, `landing`), and
`isolation/local.py` is 2084 lines at `afe87adca` with a budget of 2125
(`tests/unit/test_tripwire_module_budget.py:30`). Every location below was checked there.

The gc span is `packages/fr/src/fr/isolation/local.py:1077-1575`. `gc` (`:1079`) takes a
host-wide flock, classifies every discovered workspace, then runs four sweeps. It is reached
from `fr isolation gc` through `_gc_ops(target).gc(...)` (`commands/isolation_cmd.py:1128`).
`_spawn_gc` (`:1066`) is called by `up` (`:219`), `down` (`:921`) and `hostworktree.py:62`.

`HostWorktreeTarget` (`isolation/hostworktree.py:106-136`) overrides four methods to make gc
docker-less: `_teardown_container`, `_labelled_containers`, `_sweep_dangling_images` and
`_stale_state_reapable`. The gc code already asks other targets for some answers:
`_reap_or_classify` (`:1228-1231`) and `_gc_stale_state` (`:1291-1295`) build a sibling target
from the workspace's recorded mode, and `_merged_by_content` (`:1354`) builds
`type(self)(state.repo_root, ...)`.

These methods move. None is overridden, and none is called from outside the gc span except
by the tests listed under R4: `_acquire_gc_lock` (`:1110`), `_gc_one_guarded` (`:1129`),
`_gc_one` (`:1139`), `_reap_or_classify` (`:1181`), `_gc_stale_state` (`:1264`),
`_merged_by_content` (`:1326`), `_discover_workspaces` (`:1366`), `_repo_states` (`:1412`),
`_worktree_dirs` (`:1441`), `_resolve_state` (`:1453`), `_empty_repo_dirs` (`:1519`),
`_sweep_empty_repo_dirs` (`:1534`), `_sweep_stale_sessions` (`:1547`) and
`_sweep_agent_worktrees` (`:1564`).

These stay on the target: `gc` (delegating), `_spawn_gc`, the four overridden methods,
`_label_reap` (`:1461`, which drives the target's docker reclaim methods), and the image
helpers only `_sweep_dangling_images` uses, `_vsc_images` (`:1501`) and `_referenced_images`
(`:1510`). `_pr_from` (`:2070`) and `_reap_hazard` (`:733`) stay too: other target methods use
them.

Tests call moved methods on a target at nine sites: `_reap_or_classify` at
`tests/unit/test_isolation.py:1960`, `test_isolation_gc_routing.py:90`,
`test_isolation_preserve.py:421` and `:440`; `_discover_workspaces` at `test_isolation.py:1728`,
`:1776` and `:2125`; `_acquire_gc_lock` at `test_isolation.py:2367`; `_merged_by_content` at
`test_isolation.py:4301`. No test patches a moved method, and no test patches a module-level
name that only the moved code looks up in `fr.isolation.local`. (`test_isolation.py:1468`
patches `fr.isolation.local.branch_changes_present`, but for `_reap_hazard`, which stays.)

Two guards list the modules split out of `local.py`: `ISOLATION_MODULES` in
`tests/unit/test_isolation_network_timeouts.py:249` (no forge CLI argv) and `REMEDY_FILES` in
`tests/unit/test_vk_compat_removed.py:58` (no bare `fr isolation up` remedy).

## Requirements

R1. A new module, `packages/fr/src/fr/isolation/gc.py`, defines `GcSweeper(target)`. It holds
the fourteen moved methods under their current names, and `GcSweeper.gc(dry_run)` holds the
current body of `LocalWorktreeDevcontainerTarget.gc`. `LocalWorktreeDevcontainerTarget.gc`
keeps its signature and docstring summary and returns `GcSweeper(self).gc(dry_run)`. None of
the fourteen methods remains on the target, and no forwarding method is left.
R2. The sweeper calls every target-owned step through its target: `_labelled_containers`,
`_sweep_dangling_images`, `_label_reap`, `_pr_from`, `run` and `repo_root`. So a
`HostWorktreeTarget` sweep uses that class's docker-less overrides. The sibling rules do not
change: `_reap_or_classify` and `_gc_stale_state` route through `target_for_state`, and
`_merged_by_content` builds `type(target)(state.repo_root, runner=target.run,
gc_spawner=_noop_gc_spawn)`.
R3. gc behaves exactly as before: the same `GcAction` list in the same order, the same
host-wide flock (a second sweep still returns `[]`), and the same per-workspace failure
isolation (one workspace's error is recorded and the sweep goes on).
R4. The nine test call sites change their receiver from the target to `GcSweeper(<that
target>)` and nothing else. Every other gc and host-worktree test passes unchanged.
R5. One new test shows that a `GcSweeper` over a `HostWorktreeTarget` calls that class's own
overrides: the sweep sends no `docker` command, and a state record whose worktree is gone is
retired with no docker query (`_stale_state_reapable` is the override's `True`).
R6. `fr.isolation.gc` is added to `ISOLATION_MODULES` and
`packages/fr/src/fr/isolation/gc.py` to `REMEDY_FILES`. The `isolation/local.py` budget in
`tests/unit/test_tripwire_module_budget.py` is lowered to at most 50 lines above the module's
new length, with a comment naming #1521.
R7. `fr.isolation.gc` does not import `fr.isolation.local` at module level, so the two modules
form no import cycle. `local.py` imports `GcSweeper` at module level.
R8. A `patch` change fragment, `.changes/feat-batch-arch-isolation-gc.yaml`, records the move.
The `reviewed` stamp of `docs/explainers/fr-isolation.md`, which covers
`packages/fr/src/fr/isolation/**`, gets a note that this is a refactor with no reader-visible
change.

## Design shape

```
packages/fr/src/fr/isolation/
  local.py                  LocalWorktreeDevcontainerTarget
                              gc(dry_run)              → GcSweeper(self).gc(dry_run)
                              _spawn_gc                  (stays)
                              _teardown_container        (stays; HostWorktree overrides)
                              _labelled_containers       (stays; HostWorktree overrides)
                              _sweep_dangling_images     (stays; HostWorktree overrides)
                              _stale_state_reapable      (stays; HostWorktree overrides)
                              _label_reap, _vsc_images, _referenced_images  (stay)
                            - _acquire_gc_lock … _sweep_agent_worktrees   (14 methods leave)
+ gc.py                     GcSweeper(target)
                              gc(dry_run)   flock → [_gc_one_guarded(rec) …] + 4 sweeps
                              _acquire_gc_lock, _gc_one_guarded, _gc_one,
                              _reap_or_classify, _gc_stale_state, _merged_by_content,
                              _discover_workspaces, _repo_states, _worktree_dirs,
                              _resolve_state, _empty_repo_dirs, _sweep_empty_repo_dirs,
                              _sweep_stale_sessions, _sweep_agent_worktrees
                              ── calls back through self._target for:
                                 _labelled_containers, _sweep_dangling_images,
                                 _label_reap, _pr_from, run, repo_root
  hostworktree.py           HostWorktreeTarget(LocalWorktreeDevcontainerTarget)   (unchanged)

tests/unit/
  test_isolation.py, test_isolation_gc_routing.py, test_isolation_preserve.py
                            9 call sites: target._m(...) → GcSweeper(target)._m(...)
+ test_isolation_gc_sweeper.py   R5: host-worktree sweep uses its own overrides
  test_isolation_network_timeouts.py   ISOLATION_MODULES += fr.isolation.gc
  test_vk_compat_removed.py            REMEDY_FILES += isolation/gc.py
  test_tripwire_module_budget.py       local.py budget lowered
```

## Design

### The sweeper (R1–R3, R7)

`GcSweeper.__init__(self, target: LocalWorktreeDevcontainerTarget)` stores `self._target`.
The annotation is a string under `TYPE_CHECKING`, so `gc.py` imports `local` only for type
checking. The moved bodies change only their receivers: `self.run` becomes `self._target.run`,
`self.repo_root` becomes `self._target.repo_root`, and a call to a method that stays becomes
`self._target.<method>(...)`. A call between moved methods stays on `self`. The comments and
docstrings move with their code. Section comments that described target overrides now say that
the sweeper calls the target. The function-local imports (`routing`, `external`, `sessions`,
`agent_worktrees`) stay function-local, because `routing` imports `hostworktree`, which imports
`local`.

The `cast("LocalWorktreeDevcontainerTarget", ...)` calls keep their string form. The
`_merged_by_content` sibling becomes `type(self._target)(...)`, so a host-worktree sweep still
builds a `HostWorktreeTarget` sibling.

`local.py` drops the imports that only the moved code used (`errno`, `fcntl`, `shutil`, `IO`,
and any of `_realpath`, `_git_common_dir`, `list_states`, `delete_state`, `_merged_before`,
`branch_changes_present` and `_preserve` that nothing else in the module uses). `ruff` and
`mypy` confirm the list.

### Tests (R4–R6)

The nine call sites import `GcSweeper` from `fr.isolation.gc` and change the receiver. The new
test module builds a `HostWorktreeTarget` over a `FakeRunner` (`tests/unit/test_isolation.py`)
with a saved state record whose worktree does not exist. It runs `GcSweeper(target).gc()`,
checks that no recorded call starts with `docker` and that the record was retired with verdict
`orphan`, action `reaped`. A second case runs the same sweep on a
`LocalWorktreeDevcontainerTarget` and checks that `docker ps` was called, so the test tells the
two classes apart.

## Verification

strategy: none
gate: developer

This is a refactor with no behaviour change. The unit suite in this PR's CI proves it: the
existing gc and host-worktree tests, the nine receiver changes and the new override test. It
adds no acceptance rows (operator decision): no product behaviour changes, and the guards are
tests, not business claims.
