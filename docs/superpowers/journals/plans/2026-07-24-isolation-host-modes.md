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

<!-- fr:journal kind=discovery scope=plan id=p2-external-target-methods-frontloaded created=2026-07-24T12:12:33 phase=2 -->
### p2-external-target-methods-frontloaded · discovery · exec/down/restart/stats/status implemented at module creation (protocol completeness), so T3 was GREEN on first run (phase 2)

ExternalTarget implements the Target protocol DIRECTLY (no devcontainer inheritance), so the class is only well-formed once every protocol method exists. T1.S2 GREEN therefore shipped exec/down/restart/stats/status alongside up() rather than stubbing them. The T3.S1 tests (exec verbatim+capture=False+rc passthrough; down retires fr state + clears marker branch but leaves marker file & checkout; restart/stats refuse; status reports mode/toplevel/branch) passed on first run — they codify already-correct behavior. Mirrors Phase 1's p1-integration-already-wired: the RED->GREEN staging landed a step early, not skipped.

<!-- fr:journal kind=discovery scope=plan id=p2-target-widen-worktree-ops-cast created=2026-07-24T12:23:15 phase=2 -->
### p2-target-widen-worktree-ops-cast · discovery · Widening _target to -> Target broke 3 local-only call sites; resolved with a cast helper, not a Protocol change (phase 2)

ExternalTarget is NOT a LocalWorktreeDevcontainerTarget subclass (spec: implements Target directly), so _target's return type had to widen from LocalWorktreeDevcontainerTarget to the Target protocol. That surfaced push_check / verify_merge / gc as methods absent from the Target protocol (they live only on the local class). Adding them to the Protocol is blocked by a circular import — gc returns GcAction, defined in local.py which imports from types.py. Chose a cast helper _worktree_ops(target)->LocalWorktreeDevcontainerTarget over an isinstance guard because the gc/verify-merge CLI tests drive those commands through duck-typed StubTarget doubles monkeypatched over _target; a nominal isinstance guard rejected the stubs (5 tests red). cast() is erased at runtime, preserving the doubles. Trade-off: under a REAL external marker, status --push-check / verify-merge / gc would AttributeError rather than refuse cleanly — same category as the existing p1-target-error-uncaught finding, and out of Phase 2 scope (external is not wired into those three commands).

<!-- fr:journal kind=discovery scope=plan id=p3-hermes-green-shared-lib created=2026-07-24T12:29:02 phase=3 -->
### p3-hermes-green-shared-lib · discovery · Hermes external-marker case GREEN on first run — entrypoint sources the shared lib, no separate copy (phase 3)

Both entrypoints (Claude hooks/fr-isolation-required.sh, Hermes hooks/hermes/fr-isolation-required.sh) source the SAME lib/fr-isolation-decision.sh (Hermes via ../lib/); there is no hermes/lib/ copy. So the one _fr_marker_valid mode-branch edit covered both harnesses and the Hermes end-to-end external case (P3.T2.S1) passed immediately — it documents the guarantee rather than driving new code. The hooks-sync tripwire (test_tripwire_hermes_hooks_sync.py) pins the .hermes snippet's command->script mapping, not a lib copy, so it stayed green with no re-sync needed. External branch: after the shared toplevel-match check, case on mode: worktree->linked-worktree check (unchanged), external->container evidence ([ -f /.dockerenv ] || [ -f /run/.containerenv ] || [ -n KUBERNETES_SERVICE_HOST ]), *->return 1 (fail closed). Kept POSIX-sh (case, not bashism).

<!-- fr:journal kind=discovery scope=plan id=p4-bun-test-output created=2026-07-24T12:33:48 phase=4 -->
### p4-bun-test-output · discovery · OpenCode plugin external-mode port GREEN; host bun (devcontainer has no bun) (phase 4)

Ported Phase-3 semantics to packages/fr-opencode-plugin/src/marker.ts hasValidIsolationMarker: shared toplevel-match check hoisted before a mode switch — worktree->gitDirsDiffer (linked-worktree, unchanged), external->hasContainerEvidence (existsSync('/.dockerenv')||existsSync('/run/.containerenv')||!!process.env.KUBERNETES_SERVICE_HOST), default->false (fail closed). Package is OUTSIDE the uv workspace and NOT in CI, so bun test is a manual checklist item. bun (v1.3.11) is absent inside the devcontainer; ran on the HOST at packages/fr-opencode-plugin. Baseline before: 12 pass 0 fail. RED after adding 3 external tests: 14 pass 1 fail (the 'valid with evidence' case — the two invalid cases passed vacuously since pre-edit code rejected all non-worktree modes). GREEN after marker.ts edit: FULL OUTPUT ->\nbun test v1.3.11 (af24e281)\n\n 15 pass\n 0 fail\n 16 expect() calls\nRan 15 tests across 2 files. [4.20s]\n\nTest env note: external evidence on the Mac host is controllable only via KUBERNETES_SERVICE_HOST (the two container files are absent); tests save/restore that env var in beforeEach/afterEach.
