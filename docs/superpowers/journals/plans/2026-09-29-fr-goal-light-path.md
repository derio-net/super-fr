# Journal: 2026-09-29-fr-goal-light-path

<!-- fr:journal kind=decision scope=plan id=p1-chain-commits-per-iteration created=2026-09-29T07:59:39+00:00 phase=1 -->
### p1-chain-commits-per-iteration · decision · _advance_chain gives each iteration its own _RunWrites, so a chained advance still commits once per step (phase 1)

`advance_cmd` is now a thin wrapper over `_advance_chain`, which runs
`_advance_once` inside a fresh `_RunWrites(verb="advance")` per iteration
and commits it in `finally`. The subjects are exactly what one
`fr run advance` per step used to write (`advance c1 done`, `advance b running`).
`resolve --record` calls the same chain after `apply_record`'s commit has
landed, so the apply commit and each advance commit stay separate (spec §B
"Commits"). `_advance_once` maps `typer.Exit(1)` to `cli-failed` and every
other exit to `refused`; prints are unchanged. The orchestrator-model notice
moved from the per-step body to once per chain.

<!-- fr:journal kind=decision scope=plan id=p1-refused-chain-after-record created=2026-09-29T07:59:39+00:00 phase=1 -->
### p1-refused-chain-after-record · decision · a refusal in the advance after an applied record exits 2 and says the record is applied (phase 1)

Spec §B names exit 1 for a chained cli failure (`record applied; <step> failed
(exit N)`) but no code for a refusal inside the chained advance (for example
the next unit already held). It exits 2 with `record applied; the advance after
it was refused (above)` so nobody re-applies the record.

<!-- fr:journal kind=discovery scope=plan id=p1-group-inline-completion-chains created=2026-09-29T07:59:39+00:00 phase=1 -->
### p1-group-inline-completion-chains · discovery · _advance_group's inline group completion returns cli-done, so the chain goes on (phase 1)

`_advance_group` completes a group with nothing left to dispatch (units
resolved before members were learned) and moves the cursor without a brief.
That is the same cursor move as a passed cli step, so it returns `cli-done` and
`_advance_chain` continues to the next step instead of stopping silently.

<!-- fr:journal kind=discovery scope=plan id=p1-record-on-last-step-does-not-advance created=2026-09-29T07:59:39+00:00 phase=1 -->
### p1-record-on-last-step-does-not-advance · discovery · resolve --record on the run's last step skips the advance (phase 1)

A `deliver` record already prints the closeout handoff; advancing a finished
run would hit `advance`'s run-complete branch and print it a second time.
`_advance_after_record` returns early when the cursor step is done and has no
successor.

<!-- fr:journal kind=discovery scope=plan id=p1-fixture-walks-take-the-chained-brief created=2026-09-29T07:59:39+00:00 phase=1 -->
### p1-fixture-walks-take-the-chained-brief · discovery · test walks that advanced past plan-review / journal-check now take the brief from the same call (phase 1)

`_drive_to_implement` (integration) and `_fr_goal_at_implement` (unit) now
return the implement-phase brief printed by the plan-review advance; their
callers stop issuing a second advance (which is refused as held). Tests about
the record apply alone (`test_record_apply._resolve`,
`test_run_evidence_visual._resolve`) pass `--no-advance`; `_at_deliver` relies
on the one-call resolve. The idle-guard test moved to a two-agent shape and the
teardown test gates its second cli step, because a cli-only shape now runs to
its end in one advance.

<!-- fr:journal kind=finding scope=plan id=p1-skill-prose-still-advances-after-record created=2026-09-29T07:59:39+00:00 phase=1 state=open review_scope=in -->
### p1-skill-prose-still-advances-after-record · finding [open] (reviewer: in scope) · fr-goal skill still says `fr run advance` after `resolve --record`; that advance is now refused as held (phase 1)

With R4 a done record already briefs the next unit, so the skill's
"then `fr run advance <run-id>` again to brief `review-phase`" (pinned by
`test_run_resolve_requires_advance.py::test_the_skill_describes_the_sequence_fr_now_enforces`)
now exits 2 (ALREADY HELD) if followed literally. Spec §B's last line ("The skill
prose drops every then `fr run advance` that follows a `resolve --record`") is
owed by the prose phase (phase 3, R7); left untouched here as out of this
phase's task list.
