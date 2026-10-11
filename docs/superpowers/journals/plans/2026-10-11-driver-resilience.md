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
