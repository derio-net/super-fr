# Journal: 2026-07-24-isolation-host-modes

<!-- fr:journal kind=discovery scope=plan id=spec-row-manual-repair created=2026-07-24T11:48:52 -->
### spec-row-manual-repair · discovery · Spec table row hand-added — _append_spec_row false-idempotency (known bug)

fr plan create reported success but wrote no Implementation Plans row: the idempotence guard scans the whole spec and the plan slug is a substring of the spec's own filename. Row added manually; separate bugfix PR already owed from the hermes archival session.

<!-- fr:journal kind=discovery scope=plan id=p1-down-teardown-container-seam created=2026-07-24T12:02:45 phase=1 -->
### p1-down-teardown-container-seam · discovery · down() refactored via _teardown_container hook, not a single tail helper (phase 1)

local.down's docker block sits BETWEEN the PR guard and the worktree-remove tail, so the plan's single _down_worktree_tail(state,force) could not wrap both ends around it. Resolved with a template-method: _down_worktree_tail(state,force) = PR guard + _teardown_container(state) hook + verified worktree removal + marker/state retirement; parent _teardown_container does the docker probe/stop/rm/image reclaim, HostWorktreeTarget overrides it to a no-op. Parent down() = _down_worktree_tail + _spawn_gc; host down() = _down_worktree_tail only. All 126 existing local-target down tests stayed green (byte-identical parent behavior).

<!-- fr:journal kind=discovery scope=plan id=p1-integration-already-wired created=2026-07-24T12:03:05 phase=1 -->
### p1-integration-already-wired · discovery · Task 4 integration test passed without any Task-4 code change (phase 1)

test_hostworktree_lifecycle.py (FR_ISOLATION_TARGET=worktree → _target → up/exec/down, base clone untouched, no docker/devcontainer argv) passed on first run. Tasks 1-3 (up/exec/down + selection) fully satisfied the end-to-end walk, so P1.T4.S2's 'fix whatever the integration surfaces' was a no-op as the plan anticipated (no new features). Selection routes through the single isolation_cmd._target() site with _runner/_gc_spawner monkeypatched.

<!-- fr:journal kind=finding scope=plan id=p1-target-error-uncaught-in-some-cmds created=2026-07-24T12:03:26 phase=1 state=open -->
### p1-target-error-uncaught-in-some-cmds · finding [open] · Bogus FR_ISOLATION_TARGET raises uncaught in exec/status (traceback, not exit 2) (phase 1)

isolation_cmd.exec (raise typer.Exit(_target(repo).exec(...))) and status (target = _target(root)) call _target OUTSIDE a try/except, so an unknown FR_ISOLATION_TARGET surfaces as a Python traceback instead of the _fail() exit-2 UX. up() and restart() DO wrap it. Low practical impact: the var is a host-level declaration validated at the first up(). Out of Phase 1 scope (T3 only specified _target raising); flagging for a follow-up wrap if the orchestrator wants uniform exit-2 mapping across all isolation subcommands.
