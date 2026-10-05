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
