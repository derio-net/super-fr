<!-- fr:journal-schema=2 -->
# Journal: 2026-10-11-driver-resilience

<!-- fr:journal kind=discovery scope=plan id=p1-d1-single-pass-guard-fallout created=2026-10-11T20:56:45+00:00 phase=1 -->
### p1-d1-single-pass-guard-fallout · discovery · the single-pass guard changed 30 existing --once --yes tests (phase 1)

Every host test whose --once --yes plan dispatches now needs --single-pass (30 tests across drive_cmd, disruption, driver_adapter, driver_pass). Three asserted the last output line, which is now the warning, so they read a new _summary() helper. The cloud pass is untouched by construction (it never passes single_pass).

<!-- fr:journal kind=discovery scope=plan id=p1-d2-gitseam-tripwire created=2026-10-11T20:56:45+00:00 phase=1 -->
### p1-d2-gitseam-tripwire · discovery · batch modules may not import the gitseam module whole (phase 1)

The loop command needs the default checkout's toplevel; gitseam.toplevel is off limits to batch modules (test_forge_adapter_batch_ops), so the command asks make_checkout(None).path, and only when the scope is a single repo with no --checkout.

<!-- fr:journal kind=discovery scope=plan id=p1-d3-suite-flakes-under-load created=2026-10-11T20:56:45+00:00 phase=1 -->
### p1-d3-suite-flakes-under-load · discovery · three timing tests failed in a full local run under host load, pass alone (phase 1)

With the host load average above 500, a full local run failed test_fails_open_when_fr_hangs..., test_a_record_commit_gives_up_on_a_stuck_index_lock_quickly and test_a_named_script_that_was_run_passes; each passes alone. Unrelated to this change; evidence is CI per operator instruction (local full run stopped).

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-11T21:15:09+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · single-pass warning test is tautological; no exit-code/ordering or planned-but-not-started case (R4) (phase 1)

tests/unit/test_triage_batch_single_pass.py asserted only `assert last`.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-11T21:15:09+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · refusal test's lease release is a call spy, not an observable lease/board check (R2) (phase 1)

release_lease returns early with no state repo, so the spy passes even if the release never works.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-11T21:15:09+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · blanket --single-pass on the edited --once --yes tests may mask R5 (phase 1)

Every pre-existing --once --yes test gained the flag; R5 pinned by one test.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-11T21:15:09+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · R9 (state export) and R11 (no caching) have no named test (phase 1)

Both held only by construction.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-10-11T21:15:09+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · restart-on-skip test uses a stub driver, not a real post_merge + skipped save_pass (phase 1)

tests/unit/test_triage_drive_visibility_retry.py:206-223.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-10-11T21:15:09+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · restart_to now also applies to non-visibility ForgeReadError skips; the spec describes only visibility (phase 1)

triage_batch_cmd.py _host_loop ForgeReadError branch.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-10-11T21:15:09+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · loop_command resolves checkout symlinks; _default_toplevel catches only TriageError (phase 1)

triage_batch_cmd.py loop_command / _default_toplevel.

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-10-11T21:15:09+00:00 phase=1 state=open review_scope=out -->
### p1-r8 · finding [open] (reviewer: out of scope) · guard_write mid-pass VisibilityUnreadable still ends a looping driver (phase 1)

R8 scopes the skip to take_lease/save_pass.

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-10-11T21:15:09+00:00 phase=1 -->
### p1-review-1 · review · phase 1 code review: 8 findings (7 in, 1 out), no Critical/Important (phase 1)

Dispatched general-purpose reviewer over 1248d439..c914fe30 against spec R1–R13 and plan 01.yaml; ran the three new/edited test files (81 passed). Raised p1-r1..p1-r8. Verified each against the code: r1–r4 fixed with tests in a6735b7f (r1 exposed a real gap: a preflight refusal under --single-pass skipped the warning, fixed via _Driver.warn_single_pass); r6 fixed in the spec (behaviour kept, R8 wording widened); r5 and r7 refuted; r8 out of scope.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-11T21:15:09+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: single-pass warning test is tautological; no exit-code/ordering or planned-but-not-started case (R4) (phase 1)

a6735b7f: ordering + exit-code assertions; a planned dispatch that fails under --single-pass still warns (exit 1), and its twin without the flag is refused (exit 2). It exposed and fixed a missing warning on a refusal-ended pass (_Driver.warn_single_pass).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-11T21:15:09+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: refusal test's lease release is a call spy, not an observable lease/board check (R2) (phase 1)

a6735b7f: leased fixture with a state repo; asserts load_lease is None after the refusal, no lease on the remote tip, no board.html, no dispatch, no merge.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-11T21:15:09+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: blanket --single-pass on the edited --once --yes tests may mask R5 (phase 1)

a6735b7f: dropped the flag from every edited invocation and re-ran each file alone. 31 invocations needed it (the single-pass refusal); 3 that plan no dispatch had it removed and now pin R5.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-11T21:15:09+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: R9 (state export) and R11 (no caching) have no named test (phase 1)

a6735b7f: state export with unreadable visibility exits 2 (R9); guard_state calls repo_visibility on every call (R11).

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-10-11T21:15:09+00:00 phase=1 state=refuted resolves=p1-r5 -->
### p1-r5-resolved · finding [refuted] · resolves p1-r5: restart-on-skip test uses a stub driver, not a real post_merge + skipped save_pass (phase 1)

The stub test pins _host_loop's restart-on-skip branch; that a post_merge sets restart_to is already pinned in tests/unit/test_triage_batch_drive_restart.py. The composition adds cost without a new failure mode.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-10-11T21:15:09+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: restart_to now also applies to non-visibility ForgeReadError skips; the spec describes only visibility (phase 1)

Behaviour is the intended one (gh#998: never run another pass on stale code); spec R8 now says any skipped pass restarts when restart_to is set.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-10-11T21:15:09+00:00 phase=1 state=refuted resolves=p1-r7 -->
### p1-r7-resolved · finding [refuted] · resolves p1-r7: loop_command resolves checkout symlinks; _default_toplevel catches only TriageError (phase 1)

Resolving symlinks is deliberate: the printed command must be an absolute path valid from any pane, and the real path is that. gitseam.toplevel returns None rather than raising, so catching TriageError covers the failure surface.

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-10-11T21:15:09+00:00 phase=1 state=open resolves=p1-r8 out_of_scope=true -->
### p1-r8-resolved · finding [out-of-scope] · resolves p1-r8: guard_write mid-pass VisibilityUnreadable still ends a looping driver (phase 1)

Not caused by this change and inert in the driver: spec-review showed guard_write returns early for the driver's event-only writes (added_keys empty), so no driver pass reaches it.

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved-2 created=2026-10-11T22:34:38+00:00 state=open resolves=p1-r8 tracked_by=https://github.com/derio-net/super-fr/issues/1145 -->
### p1-r8-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1145] · resolves p1-r8: guard_write mid-pass VisibilityUnreadable still ends a looping driver

Filed at archive as https://github.com/derio-net/super-fr/issues/1145.
