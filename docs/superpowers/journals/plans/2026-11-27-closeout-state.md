<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-closeout-state

<!-- fr:journal kind=discovery scope=plan id=p1-dedupe-key created=2026-11-27T12:21:20+00:00 phase=1 -->
### p1-dedupe-key · discovery · The take-back's words must stay out of _dispatch_failed's dedupe key (phase 1)

A runner error with no `code` keys the dedupe on the whole message, so appending the take-back error to it re-said the stop every pass. `_dispatch_failed` takes the take-back text as a separate `also` that is said with the first report and never keyed.

<!-- fr:journal kind=discovery scope=plan id=p1-module-budget created=2026-11-27T12:21:20+00:00 phase=1 -->
### p1-module-budget · discovery · triage_batch_cmd.py sits at its 8300-line budget (phase 1)

The shared take-back wording lives in `fr.triage.drive_errors.takeback_failed` (beside `fail_text`) so the module stays within budget (8299).
