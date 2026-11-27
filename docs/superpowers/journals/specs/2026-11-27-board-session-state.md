<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-board-session-state

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-27T19:57:09+00:00 input=true -->
### brief · discovery · Operator brief (batch board-session-state, derio-net/super-fr#1731)

Batch `board-session-state` of derio-net/super-fr: 1 issues, delivered as ONE pull request.
Batch title: Batches page: session state, lane owners, time per column
super-fr#1731: Batches page: show who each session waits for (session state within the columns), lane owners, and dwell time per column.
Batches page: session state within the existing columns (who waits for whom), an owner per Needs-you lane, and time per column and state. Builds on `fr_herdr.restart.has_background_work`; columns stay decided by `lanes.lane_of`.
Note: Works without Stations; helps orchestrating today.
Why these belong together: Operator-requested: shows who each session waits for, and where waves lose time; needed to orchestrate waves now.
Delivery rules: branch feat/batch-board-session-state; draft PR with "Closes derio-net/super-fr#1731"; run started with --issue 1731; no member issue as a phase tracking_issue; the wave driver owns mergeability and CI (no fr pr settle loop); never add approved-fr.

<!-- fr:journal kind=decision scope=spec id=q1-wait-parties created=2026-11-27T19:57:09+00:00 decided_by=operator -->
### q1-wait-parties · decision · A card names one of six parties it waits for

Operator chose the six-party set: you (with lane role), agent, background (via has_background_work, one herdr screen read per idle session per render), ci, queue/driver, dependency. Recommended option.

<!-- fr:journal kind=decision scope=spec id=q2-lane-owners created=2026-11-27T19:57:09+00:00 decided_by=operator -->
### q2-lane-owners · decision · Lane owners come from each repo's .fr/triage.yaml

Operator chose a new `lane_owners` key in `.fr/triage.yaml` read at the default branch; unset lane shows 'owner: unassigned'; shown in the lane header and on the card; per repo when a multi-repo scope differs. Recommended option.

<!-- fr:journal kind=decision scope=spec id=q3-dwell-ledger created=2026-11-27T19:57:09+00:00 decided_by=operator -->
### q3-dwell-ledger · decision · Dwell time is measured by a dwell ledger in the state directory

Operator chose `dwell.json` in the scope's state directory, carried by the state ref, updated by every board render and driver pass; precision is the cadence. Recommended option.

<!-- fr:journal kind=decision scope=spec id=q4-display created=2026-11-27T19:57:09+00:00 decided_by=operator -->
### q4-display · decision · Cards carry a dwell line, waves a time summary

Operator chose per-card 'in <column> <t> · waits for <party> <t>' plus a per-wave summary of time per column and per wait party naming the slowest batch per column. Recommended option.

<!-- fr:journal kind=decision scope=spec id=q5-verification created=2026-11-27T19:57:09+00:00 decided_by=operator -->
### q5-verification · decision · Verified by CI unit tests and browser checks, gate developer

Operator chose strategy none per row (CI unit tests plus fr-goal's browser checks at review and deliver over a fixture-rendered page), gate developer; the live herdr background read is a post-merge Test Plan row. Recommended option.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-11-27T20:05:04+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Wait rule 1 hides the wait on Tester/DevOps lane, Closing-out and Obsolete cards

Row 1 (terminal) was checked before needs_you, so merged lane cards, close-out cards and obsolete cards showed no wait.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-11-27T20:05:04+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · Background rule checks the batch's item id though the front may be the close-out

Row 5 read the batch's own item id even when Card.front is the close-out.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-11-27T20:05:04+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · Row 7 maps awaiting and unselected proposed batches to queue

Awaiting waits for the operator's approved-fr; an unselected proposed batch is never driven.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-11-27T20:05:04+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · Precedence table leaves done/absent/None statuses, dead dependencies and None checks undecided

done/absent/None fell to queue implicitly; dependency rule used 'merged'; checks may be None.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-11-27T20:05:04+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · The dwell ledger has no single writer and an unpushed dwell.json makes fetches refuse

One-shot renders could overwrite the driver's ledger; a local dwell.json would clash on fetch.

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-11-27T20:05:04+00:00 state=open review_scope=in -->
### s6 · finding [open] (reviewer: in scope) · 'The driver writes the page every pass' is false

Essential-only passes and non-collecting watch iterations do not render.

<!-- fr:journal kind=finding scope=spec id=s7 created=2026-11-27T20:05:04+00:00 state=open review_scope=in -->
### s7 · finding [open] (reviewer: in scope) · Ledger semantics underspecified

Interval start, first-seen reset, closed-interval first-seen, cap in R5, wave-less batches.

<!-- fr:journal kind=finding scope=spec id=s8 created=2026-11-27T20:05:04+00:00 state=open review_scope=in -->
### s8 · finding [open] (reviewer: in scope) · No docs pages named though four pages cover touched paths

fr docs check would fail at deliver.

<!-- fr:journal kind=finding scope=spec id=s9 created=2026-11-27T20:05:04+00:00 state=open review_scope=in -->
### s9 · finding [open] (reviewer: in scope) · lane_owners guarded status unstated; strict refusal of a display-only key costs the whole config

A typo would refuse the repo's triage config.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-11-27T20:05:04+00:00 -->
### spec-review · review · independent spec review: 9 findings, all in scope

fr-spec-reviewer checked the spec against decisions q1-q5 and the code (file:line for every cited symbol); 9 in-scope findings s1-s9, each fixed in the spec.

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-27T20:05:04+00:00 lens=errors step=spec-review -->
### lens-errors-1 · lens · the ledger's unreadable, concurrent-writer and state-ref paths and per-pane read failures can fail quietly

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-11-27T20:05:04+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Wait rule 1 hides the wait on Tester/DevOps lane, Closing-out and Obsolete cards

R1 now says only a Done-column card has no wait; §A row 1 is column done, obsolete maps to you (row 3).

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-11-27T20:05:04+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: Background rule checks the batch's item id though the front may be the close-out

§A now names the front session's item id (closeout_item_id when the front is the close-out) and requires close-out-front tests.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-11-27T20:05:04+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: Row 7 maps awaiting and unselected proposed batches to queue

§A rows 4 (awaiting → you, reviewer) and 7 (unselected proposed → you).

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-11-27T20:05:04+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: Precedence table leaves done/absent/None statuses, dead dependencies and None checks undecided

§A gives explicit rows 5/6 in dependency_state terms (dead → you), 12 (idle/done → agent), 13 (absent/unknown/None → queue), and a null-safe checks read.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-11-27T20:05:04+00:00 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: The dwell ledger has no single writer and an unpushed dwell.json makes fetches refuse

R5 and §D: one writer (no live drive.lock, or the driver itself with writer=True); others observe in memory; fetch_state adopts the ref's dwell.json and never counts it as a clash.

<!-- fr:journal kind=finding scope=spec id=s6-resolved created=2026-11-27T20:05:04+00:00 state=fixed resolves=s6 -->
### s6-resolved · finding [fixed] · resolves s6: 'The driver writes the page every pass' is false

§D states the real cadence with file:line and Risks names late dating under pacing.

<!-- fr:journal kind=finding scope=spec id=s7-resolved created=2026-11-27T20:05:04+00:00 state=fixed resolves=s7 -->
### s7-resolved · finding [fixed] · resolves s7: Ledger semantics underspecified

R5/R7 and §D define start = max(since), cleared first-seen on restart, per-interval first_seen, truncated flag, the 200 cap, ≥ totals and a no-wave block.

<!-- fr:journal kind=finding scope=spec id=s8-resolved created=2026-11-27T20:05:04+00:00 state=fixed resolves=s8 -->
### s8-resolved · finding [fixed] · resolves s8: No docs pages named though four pages cover touched paths

Design shape now names fr-triage.md, fr-dispatch.md, dispatch-lifecycle.md and herdr-control-sessions.md with what each says.

<!-- fr:journal kind=finding scope=spec id=s9-resolved created=2026-11-27T20:05:04+00:00 state=fixed resolves=s9 -->
### s9-resolved · finding [fixed] · resolves s9: lane_owners guarded status unstated; strict refusal of a display-only key costs the whole config

R4/§C: display-only, not in GUARDED_TRIAGE_KEYS; unknown lane keys go to `ignored` and a page note, never a refusal.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-27T20:05:08+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  batch-background-live: tester
  batch-card-background-wait: none
  batch-card-dwell-line: none
  batch-card-waits-for: none
  batch-dwell-ledger: none
  batch-lane-owners: none
  batch-wave-time-summary: none
row_kinds:
  batch-background-live: live
  batch-card-background-wait: none
  batch-card-dwell-line: none
  batch-card-waits-for: none
  batch-dwell-ledger: none
  batch-lane-owners: none
  batch-wave-time-summary: none
run_gate: developer
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-board-session-state-p2 created=2026-11-27T20:07:50+00:00 -->
### phase-split-2026-11-27-board-session-state-p2 · decision · ask: the dwell ledger and its displays (R5-R7) are an ask of their own, built on phase 1's Card.wait
