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
