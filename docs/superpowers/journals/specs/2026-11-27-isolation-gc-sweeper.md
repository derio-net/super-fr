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
