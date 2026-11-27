<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-isolation-gc-sweeper

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-27T14:26:14+00:00 input=true -->
### brief · discovery · Operator brief (batch arch-isolation-gc, issue super-fr#1521)

Batch `arch-isolation-gc` of derio-net/super-fr: 1 issue, delivered as ONE pull request.
Batch title: #1318: isolation/local.py garbage collection moves to a collaborator.
super-fr#1521 — isolation/local.py: move garbage collection to a collaborator that keeps
the subclass override points. Refactor slice from the #1318 review.
Issue body (summary): a collaborator `GcSweeper(target)`; `LocalWorktreeDevcontainerTarget.gc`
delegates to it; not a mixin. Moves ~370 lines (_acquire_gc_lock, _gc_one_guarded, _gc_one,
_reap_or_classify, _gc_stale_state, _merged_by_content, _discover_workspaces, _repo_states,
_worktree_dirs, _resolve_state, _empty_repo_dirs, _sweep_empty_repo_dirs,
_sweep_stale_sessions, _sweep_agent_worktrees). Stays: gc (delegating), _spawn_gc, the four
HostWorktreeTarget overrides, _vsc_images, _referenced_images, _label_reap. Tests follow the
move, no forwarding methods; nine call sites change their receiver only. One new test shows
a HostWorktreeTarget sweep calls its own overrides. Guards: forge-argv scan and the
test_vk_compat_removed path list gain the new module; lower the line budget. After #1517.
Delivery rules: branch feat/batch-arch-isolation-gc, draft PR with `Closes derio-net/super-fr#1521`,
run started with --issue 1521, no member issue as a phase tracking_issue, no fr pr settle loop,
never add approved-fr.

<!-- fr:journal kind=decision scope=spec id=d-rows created=2026-11-27T14:26:14+00:00 decided_by=operator -->
### d-rows · decision · No acceptance rows

Operator chose no rows — a pure refactor with no product behaviour change; the guards are tests, not business claims (same as

<!-- fr:journal kind=decision scope=spec id=d-verification created=2026-11-27T14:26:14+00:00 decided_by=operator -->
### d-verification · decision · Verification: strategy none, gate developer

Operator chose strategy none and gate developer — the unit suite in CI proves the refactor; nothing holds the close-out; no Test Plan.

<!-- fr:journal kind=decision scope=spec id=d-shape created=2026-11-27T14:26:14+00:00 decided_by=operator -->
### d-shape · decision · Run on fr-goal-light

Operator chose the light shape — the move fits one agentic phase.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-isolation-gc-sweeper-p1 created=2026-11-27T14:28:06+00:00 -->
### phase-split-2026-11-27-isolation-gc-sweeper-p1 · decision · review-size: the whole move (~900 diff lines, R1-R8) is one reviewable phase; it links no rows because the operator chose none for this refactor (d-rows)

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-11-27T14:33:35+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · R5 credits the stale-state retirement to the sweeper's target, but `_gc_stale_state` asks the workspace's recorded mode

target: spec. `_gc_stale_state` builds its owner from the record's recorded mode (local.py:1287-1298, routing.py:32-34), so R5's claim about `_stale_state_reapable` cannot be proven through the sweeper's target. The overrides reached through the target are `_labelled_containers` / `_sweep_dangling_images`.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-11-27T14:33:35+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · Plan P1.T1.S1 does not set the saved state's mode, so Case 1 fails or passes for the wrong reason

target: plan. A devcontainer-mode record routes to a LocalWorktreeDevcontainerTarget owner that runs `docker ps -q`; the step must save `profile="host", target="worktree"` and Case 2 must assert the `_labelled_containers` call.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-11-27T14:33:35+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · R7 (no gc -> local import cycle) has no lasting guard; the existing split-module guard would reject the planned TYPE_CHECKING import

target: spec|plan. Only a one-off import smoke checked R7; `test_split_modules_never_import_local` flags TYPE_CHECKING imports too.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-11-27T14:33:35+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · Background says REMEDY_FILES lists the modules split out of local.py; it lists none of them

target: spec. test_vk_compat_removed.py:58-65 lists remedy-emitting files, not split modules.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-11-27T14:33:35+00:00 -->
### spec-review · review · independent spec+plan review: 4 findings, all in scope

Reviewer verified every named file:line (local.py gc span :1077-1575, the fourteen methods, hostworktree.py:107-135 overrides, isolation_cmd.py:1128, the nine test sites, ISOLATION_MODULES :249, REMEDY_FILES :58, budget :30), the import graph (no cycle at module level), and that no test patches a moved method or a name only moved code reads. Decisions d-rows, d-verification, d-shape honoured. Findings s1-s4.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-11-27T14:33:35+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: R5 credits the stale-state retirement to the sweeper's target, but `_gc_stale_state` asks the workspace's recorded mode

R5 and the Design's Tests section now save a host-mode record (profile host, target worktree), credit the docker-less retirement to routing, and name `_labelled_containers` / `_sweep_dangling_images` as the overrides reached through the target.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-11-27T14:33:35+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: Plan P1.T1.S1 does not set the saved state's mode, so Case 1 fails or passes for the wrong reason

P1.T1.S1 now saves profile="host", target="worktree" and Case 2 asserts the `docker ps -a --filter label=devcontainer.local_folder` call.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-11-27T14:33:35+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: R7 (no gc -> local import cycle) has no lasting guard; the existing split-module guard would reject the planned TYPE_CHECKING import

R7 now owns a lasting test (a subprocess imports fr.isolation.gc first and expects exit 0); Background says why gc.py does not join test_split_modules_never_import_local; P1.T1.S1 adds Case 3.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-11-27T14:33:35+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: Background says REMEDY_FILES lists the modules split out of local.py; it lists none of them

Background reworded — ISOLATION_MODULES lists the split modules; REMEDY_FILES lists remedy-emitting files and gc.py joins because the moved code carries remedy text; R6 states that reason.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-27T14:33:37+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates: {}
row_kinds: {}
run_gate: developer
run_kind: none
```
