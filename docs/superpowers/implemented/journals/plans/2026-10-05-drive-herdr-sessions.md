# Journal: 2026-10-05-drive-herdr-sessions

<!-- fr:journal kind=decision scope=plan id=plan-two-phases created=2026-10-05T11:59:39+00:00 -->
### plan-two-phases · decision · Two agentic phases, one per member issue

Phase 1 (#919, skeleton) wave workspaces R1-R5; phase 2 (#918) closing R6-R10, depends on phase 1's group hint. No member issue is a tracking_issue.

<!-- fr:journal kind=discovery scope=plan id=p1-closeout-item-group-optional created=2026-10-05T12:19:38+00:00 phase=1 -->
### p1-closeout-item-group-optional · discovery · _closeout_item keeps group optional (phase 1)

Making `group` a required kwarg of `_closeout_item` broke tests/unit/test_fr_herdr_closeout.py (two callers); it is `str | None = None` and the payload key is added only when set, matching `_work_item`.

<!-- fr:journal kind=discovery scope=plan id=p1-flaky-install-atomic created=2026-10-05T12:19:38+00:00 phase=1 -->
### p1-flaky-install-atomic · discovery · test_install_atomic flaked once under -n auto (phase 1)

tests/integration/test_install_atomic.py::test_fr_stays_runnable_throughout_a_reinstall failed once in a loaded full run and passed alone and on the rerun; wall-clock-tight, unrelated to this phase.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-10-05T12:19:38+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

fixture capture, nothing to refactor

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-05T12:19:38+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

fragment and matrix row only, nothing to refactor

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-05T12:24:09+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · _Driver._existing builds close-out probes without payload group, so herdr's preflight refuses them with HERDR_WORKSPACE_ID unset (phase 1)

triage_batch_cmd.py `_existing`: the drive would exit 2 at close-out time although the grouped close-out item itself passes preflight (spec §D: probes carry the wave group).

<!-- fr:journal kind=review scope=plan id=p1-review-r1 created=2026-10-05T12:24:09+00:00 phase=1 -->
### p1-review-r1 · review · Phase 1 code review: 1 finding (p1-r1, in scope) (phase 1)

Dispatched reviewer (separate context) checked R1-R5 against runner.py, batch_drive.py,
triage_batch_cmd.py, work_item.py, fixtures and tests. Raised p1-r1 (in). Noted below-threshold
observations: no driver-level no-wave test (added: test_a_driven_batch_with_no_wave_opens_in_the_no_wave_group),
a malformed workspace-create response would skip cleanup (live capture has the field), and a
prefix with surrounding spaces is not stripped (cosmetic).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-05T12:24:09+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: _Driver._existing builds close-out probes without payload group, so herdr's preflight refuses them with HERDR_WORKSPACE_ID unset (phase 1)

The probe payload now carries group=self.group_of(b); test_the_closeout_probe_carries_the_same_group_as_the_closeout pins it (red before the fix, commit f28e1fcdf).

<!-- fr:journal kind=discovery scope=plan id=p2-d1 created=2026-10-05T12:33:43+00:00 phase=2 -->
### p2-d1 · discovery · closing is best effort, so a runner load failure is caught as typer.Exit (phase 2)

load_runner _fails (prints, Exit 2) and tests replace it wholesale; _try_runner catches typer.Exit, caches the failure and prints one warning. A raised close or busy outcome is deduplicated per batch and cause via the driver's warned set; a repeat returns an empty outcome and run_pass stays quiet.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-10-05T12:33:43+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

docstrings only; protocol and contract are one small function each, nothing duplicated

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-10-05T12:33:43+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

_sessions and _existing build different probes (batch+closeout items vs due close-outs) and differ in failure policy (exit 2 vs skip); sharing a grouping helper would have blurred that

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t5 created=2026-10-05T12:33:43+00:00 phase=2 -->
### no-refactor-p2-t5 · discovery · no-refactor-because P2.T5 (phase 2)

prose, mirrors and matrix rows only; no code to clean

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-05T12:39:25+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · _try_runner caught only typer.Exit: an adapter's ImportError or from_env() failure crashed the drive, and a caught refusal printed a red error plus a warning (phase 2)

triage_batch_cmd.py `_Driver._try_runner`; fr_dispatch.registry.load_runner does not wrap `.load()`/`factory()`. Breaks R10 (a runner that cannot be loaded is reported once and skipped).

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-05T12:39:25+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · Busy/failed close dedup key was the whole outcome line, so the same cause re-reported once a sibling closed or an exception message changed (phase 2)

triage_batch_cmd.py `_close_sessions`/`_report_cause`; spec §D asks for one report per batch and cause.

<!-- fr:journal kind=review scope=plan id=p2-review-r1 created=2026-10-05T12:39:25+00:00 phase=2 -->
### p2-review-r1 · review · Phase 2 code review: 2 findings (p2-r1, p2-r2, in scope) (phase 2)

Dispatched reviewer (separate context) checked R6-R10 against protocols.py, testing.py,
fr_herdr/runner.py, batch_drive.py, triage_batch_cmd.py, the fr-triage skill and mirrors, the
close tests and matrix rows. Verified correct: busy never closed, the R9 lone-tab rule,
recorded-runner probing skipping `hand`, did=False/no failed_write, is_finished shared by
steps 3 and 5, --keep-sessions and no probing without --yes, vk/cncd and Runner untouched.
Raised p2-r1 and p2-r2, both in scope.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-05T12:39:25+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: _try_runner caught only typer.Exit: an adapter's ImportError or from_env() failure crashed the drive, and a caught refusal printed a red error plus a warning (phase 2)

`_try_runner` captures `load_runner`'s refusal output and catches any exception, printing ONE warning with the reason; tests test_a_runner_whose_load_raises_is_skipped_with_one_warning (ImportError, RuntimeError) and test_a_runner_load_refusal_prints_one_warning_not_an_error (commit 8ec21f775).

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-05T12:39:25+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: Busy/failed close dedup key was the whole outcome line, so the same cause re-reported once a sibling closed or an exception message changed (phase 2)

Causes key on (batch, item, busy | exception type); a line whose causes are all reported prints only what closed. Tests test_a_busy_cause_is_not_reported_again_when_a_sibling_closed and test_a_failed_close_is_reported_once_whatever_its_message (commit 8ec21f775).
