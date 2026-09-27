# Journal: 2026-09-27-triage-batch-launch

<!-- fr:journal kind=decision scope=plan id=p-two-phases created=2026-09-27T09:13:53 -->
### p-two-phases · decision · Two agentic phases, one per issue,

Both issues edit render_brief; #687's debug brief is written against the brief #704 leaves behind, so #704 goes first. Both standard tier (~260 and ~320 lines). No manual phase: the herdr run-unit contract is unchanged and CI-pinned, so no live verification is owed.

<!-- fr:journal kind=discovery scope=plan id=p1-acceptance-record-refused created=2026-09-27T09:29:11 phase=1 -->
### p1-acceptance-record-refused · discovery · implement-phase's emits don't allow an `acceptance` record section (phase 1)

The shipped fr-goal manifest's `implement-phase` step emits only `[journal:plan, plan:ticks]`, so `allowed_sections` (fr.record.model) never includes `acceptance` for it — a record naming that section would be refused by `fr run resolve --record` (RecordRefusedError, "section(s) acceptance not allowed"). The step-record template's own comment names the fallback ("or use `fr acceptance set-status` ... and commit the matrix + reports"), so triage-batch-session-model was moved to `ci` that way instead, in its own commit (cc6cacb9a6903e2c5d856c0d6cc46b98a00bedef), rather than through this record's `acceptance:` field.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-09-27T09:29:11 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

render_brief lost only the one subagent-model line and its param; the function was already minimal and needed no further cleanup.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-09-27T09:29:11 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the checkout-before-resolve reorder and the new _orchestrator helper are the smallest shape that carries the precedence; nothing else in triage_batch_cmd.py touches launch resolution.
