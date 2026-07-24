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

<!-- fr:journal kind=finding scope=plan id=p1-target-error-uncaught-in-some-cmds created=2026-07-24T12:03:26 phase=1 state=fixed -->
### p1-target-error-uncaught-in-some-cmds · finding [fixed] · Bogus FR_ISOLATION_TARGET raises uncaught in exec/status (traceback, not exit 2) (phase 1)

isolation_cmd.exec (raise typer.Exit(_target(repo).exec(...))) and status (target = _target(root)) call _target OUTSIDE a try/except, so an unknown FR_ISOLATION_TARGET surfaces as a Python traceback instead of the _fail() exit-2 UX. up() and restart() DO wrap it. Low practical impact: the var is a host-level declaration validated at the first up().

FIXED in post-review (review-f4): added _target_or_exit(repo) mapping IsolationError -> clean exit 2, wired into exec/status/verify-merge/gc/_down_all. Pinned by test_status_bogus_target_exits_2 / test_gc_bogus_target_exits_2 / test_down_all_bogus_target_exits_2 (assert message + no Traceback).

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

<!-- fr:journal kind=discovery scope=plan id=p5-hidden-hermes-mirrors created=2026-07-24T12:51:51 phase=5 -->
### p5-hidden-hermes-mirrors · discovery · Editing SKILL.md/rules also requires scripts/sync-hermes.py, not just sync-opencode.py (phase 5)

The plan step named only scripts/sync-opencode.py for the .opencode/ mirrors, but plugins/super-fr/skills/*/SKILL.md and plugins/super-fr/rules/*.md are ALSO mirrored into .hermes/skills/fr/ and .hermes/SOUL.d/super-fr-rules.md by scripts/sync-hermes.py. Two tripwires (test_tripwire_hermes_rules_sync.py, test_tripwire_hermes_skills_sync.py) failed in the full gate until I ran sync-hermes.py. Any Phase-5-style skill/rule edit must run BOTH sync scripts and commit both mirror trees.

<!-- fr:journal kind=discovery scope=plan id=p5-skill-120-squeeze created=2026-07-24T12:52:05 phase=5 -->
### p5-skill-120-squeeze · discovery · fr-isolation SKILL.md was already at the 120-line cap; adding the Modes section forced ~13 lines of compression (phase 5)

fr-isolation/SKILL.md sat exactly at 120 lines pre-edit (the test counts len(text.strip().split(chr(10))), == wc -l with a trailing newline). The new '### Modes (FR_ISOLATION_TARGET)' block (+13) was offset by compressing cold-start, credential-boundary, cwd, gc, recovery, and lifecycle bullets back to exactly 120. fr-brainstorming had headroom (84 lines). test_skill_validation.py green.

<!-- fr:journal kind=discovery scope=plan id=p5-acceptance-rows-flipped created=2026-07-24T12:52:21 phase=5 -->
### p5-acceptance-rows-flipped · discovery · Four isolation-* rows flipped not-implemented -> ci by direct YAML edit (add refuses duplicate ids) (phase 5)

fr acceptance add appends only and errors on a duplicate id (acceptance_cmd.py:292), so the four rows born at brainstorm had to be updated by direct matrix.yaml edit. Level keys are unit|api|int|ui (model.py LEVELS) — integration is 'int'. Mapping: isolation-external-adopt -> unit test_isolation_external.py + test_isolation_cmd.py; isolation-host-worktree-e2e -> unit test_isolation_hostworktree.py + test_isolation_cmd.py, int test_hostworktree_lifecycle.py; isolation-no-silent-degradation -> unit test_isolation_cmd.py (unknown target) + test_isolation_decision_core.py (bogus marker mode fail-closed); isolation-external-marker-enforcement -> unit test_isolation_decision_core.py. Notes record post-merge owed: live pod/external walks = spec Test Plan steps 1-3, OpenCode bun suite (15/15) outside CI. fr acceptance check exit=0, no staleness for the new spec.

<!-- fr:journal kind=discovery scope=plan id=p5-bridge-flake-confirmed created=2026-07-24T12:52:34 phase=5 -->
### p5-bridge-flake-confirmed · discovery · test_install_bridge flake reproduced and cleared with --with fr-vk reinstall (phase 5)

The full gate's test_install_bridge_flag_writes_wrapper failure was the documented stale-uv-tool flake: install.sh --install-bridge reported 'cannot import fr_vk.bridge — bridge wrapper not installed'. A plain 'uv tool install --force --from packages/fr fr' did NOT fix it (fr installed without fr_vk); the fix is the install.sh-suggested 'uv tool install --force --with packages/fr-vk packages/fr', after which the test passes. Not a regression.

<!-- fr:journal kind=finding scope=plan id=review-f1 created=2026-07-24T13:20:25 state=fixed -->
### review-f1 · finding [fixed] · Rebase onto origin/main (3.14.1 + #396 plan_ops fix)

Reviewer: branch forked before origin/main advanced (3.14.1 version bump + #396 _append_spec_row scoping). Fixed: rebased feat/isolation-host-modes onto origin/main; every version surface resolved to our 3.15.0 (root+member pyproject.toml, both plugin.json, marketplace.json, package.json); uv.lock regenerated with uv sync. Pinned: uv run --no-project python scripts/bump-version.py --check green; fr --version = 3.15.0.

<!-- fr:journal kind=finding scope=plan id=review-f2 created=2026-07-24T13:20:27 state=fixed -->
### review-f2 · finding [fixed] · fr isolation status crashed in external and host-worktree modes

Reviewer: (a) ExternalTarget.status lacked pr/profile/worktree keys the CLI text renderer reads -> KeyError; (b) HostWorktreeTarget inherited local status -> _container_state -> docker -> FileNotFoundError on a docker-less host. Fixed: ExternalTarget.status now supplies profile='external', worktree=toplevel, pr=None; HostWorktreeTarget overrides status to skip the docker probe (container='n/a (host)'). --stats/--push-check refuse cleanly (exit 2) in both modes. Tests: test_status_external_mode_text_renders/_json_has_keys, test_status_host_worktree_mode_no_docker, test_status_{stats,push_check}_host_mode_refuses, test_status_skips_docker_probe.

<!-- fr:journal kind=finding scope=plan id=review-f3 created=2026-07-24T13:20:30 state=fixed -->
### review-f3 · finding [fixed] · ExternalTarget.detect used passed path verbatim, missed marker from a subdir

Reviewer: detect probed the marker at the passed path, so a command from a subdirectory fell through to devcontainer. Fixed: detect resolves 'git rev-parse --show-toplevel' via the runner first; not-a-repo -> None. Tests: test_target_external_marker_detected_from_subdir (CLI), test_detect_from_subdirectory + test_detect_not_a_repo_returns_none (unit).

<!-- fr:journal kind=finding scope=plan id=review-f4 created=2026-07-24T13:20:58 state=fixed -->
### review-f4 · finding [fixed] · Bogus FR_ISOLATION_TARGET raised uncaught IsolationError in exec/status/verify-merge/gc/down --all

Reviewer: only up/restart/down wrapped _target's IsolationError to exit 2; the rest tracebacked. Fixed: added _target_or_exit(repo) mapping IsolationError -> clean exit 2, wired into exec/status/verify-merge/gc/_down_all. Tests: test_status_bogus_target_exits_2, test_gc_bogus_target_exits_2, test_down_all_bogus_target_exits_2 (assert message + no Traceback).

<!-- fr:journal kind=finding scope=plan id=review-f5 created=2026-07-24T13:21:01 state=fixed -->
### review-f5 · finding [fixed] · External mode not wired into status --push-check / verify-merge / gc (cast AttributeError)

Reviewer: the _worktree_ops cast would AttributeError under a real external marker. Fixed: _refuse_external(target, op) refuses cleanly (IsolationError exit 2, 'not supported in external mode - externally managed') for verify-merge, status --push-check, and gc when the target is ExternalTarget. Tests: test_verify_merge_external_refuses, test_status_push_check_external_refuses, test_gc_external_refuses.

<!-- fr:journal kind=finding scope=plan id=p2-external-worktree-ops-refusal created=2026-07-24T13:21:04 state=fixed -->
### p2-external-worktree-ops-refusal · finding [fixed] · External mode refuses push-check / verify-merge / gc cleanly (closes the p2 cast trade-off)

The Phase-2 discovery p2-external-target-methods-frontloaded flagged that the _worktree_ops cast would AttributeError for status --push-check / verify-merge / gc under a real external marker (external not wired into those three). Now refused up-front via isinstance(target, ExternalTarget) guards in isolation_cmd (_refuse_external), exit 2 with 'externally managed'. Pinned by test_verify_merge_external_refuses / test_status_push_check_external_refuses / test_gc_external_refuses.

<!-- fr:journal kind=finding scope=plan id=review-f6 created=2026-07-24T13:21:29 state=fixed -->
### review-f6 · finding [fixed] · External detect/up required no container evidence — a forged marker on a bare host routed to ExternalTarget

Reviewer: detect adopted any valid marker; up would then git switch -c the base clone on a bare host. Fixed: detect() now additionally requires the evidence triple (/.dockerenv, /run/.containerenv, or non-empty KUBERNETES_SERVICE_HOST) — corroboration of the preparer's claim, not probe-based auto-detection (Non-goals intact). Spec §A Selection updated. Tests: test_detect_without_container_evidence_returns_none + test_target_external_marker_without_container_evidence_falls_through (skip-guarded where /.dockerenv exists, mirroring Phase 3); positive path test_detect_with_container_evidence_returns_target.

<!-- fr:journal kind=finding scope=plan id=review-f7 created=2026-07-24T13:21:31 state=fixed -->
### review-f7 · finding [fixed] · _set_marker_branch did unvalidated json.loads (raw JSONDecodeError after state deleted in down)

Reviewer: down calls _set_marker_branch AFTER delete_state; a corrupt marker raised a raw JSONDecodeError. Fixed: wrapped the parse like _load_marker -> IsolationError('unreadable .fr-isolation marker'). Test: test_down_with_corrupt_marker_raises_isolationerror.

<!-- fr:journal kind=finding scope=plan id=review-f8 created=2026-07-24T13:21:34 state=fixed -->
### review-f8 · finding [fixed] · ExternalTarget never git-excluded the adopted marker

Reviewer: an in-container agent could commit .fr-isolation in a repo lacking a .gitignore entry. Fixed: up() appends '.fr-isolation' to <git-common-dir>/info/exclude if absent (mirrors local._write_isolation_marker). Tests: test_up_git_excludes_marker, test_up_git_exclude_idempotent.

<!-- fr:journal kind=finding scope=plan id=review-f9 created=2026-07-24T13:21:37 state=fixed -->
### review-f9 · finding [fixed] · HostWorktreeTarget.up duplicated ~15 lines of local.up

Reviewer: extract the shared prelude. Fixed: _worktree_up_core(branch, path) on LocalWorktreeDevcontainerTarget covers the .git guard + default worktree-path computation + parent mkdir; both up()s call it. No behavior change — all 115 test_isolation.py + host-worktree tests stayed green.

<!-- fr:journal kind=finding scope=plan id=review-f10 created=2026-07-24T13:21:39 state=fixed -->
### review-f10 · finding [fixed] · fr isolation gc tracebacked (FileNotFoundError) on a docker-less host-worktree host

Reviewer: gc -> _labelled_containers -> docker -> FileNotFoundError. Fixed within finding-4's uniform wrap: when the selected target is HostWorktreeTarget, gc refuses cleanly (exit 2, 'gc requires docker; host-worktree gc is future work'). Test: test_gc_host_mode_refuses (asserts message + no Traceback).
