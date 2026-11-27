<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-board-session-state

<!-- fr:journal kind=discovery scope=plan id=p1-wrap created=2026-11-27T20:36:26+00:00 phase=1 -->
### p1-wrap · discovery · The wait pill overflowed a narrow card (phase 1)

The first render put the long pill 'waits for you · reviewer (@a, @b)' on white-space: nowrap, so it overflowed the card at desktop width and clipped at 390px. The wait pills now wrap (overflow-wrap: anywhere); re-shot after the fix.

<!-- fr:journal kind=discovery scope=plan id=p1-collapsed-owners created=2026-11-27T20:36:26+00:00 phase=1 -->
### p1-collapsed-owners · discovery · Empty Needs-you columns hide their owner line (phase 1)

A collapsed (empty) column is a vertical strip, so its owners line is hidden with the column body. owner: unassigned shows once a lane holds a card.

<!-- fr:journal kind=discovery scope=plan id=p1-headless-width created=2026-11-27T20:36:26+00:00 phase=1 -->
### p1-headless-width · discovery · Headless Chrome clips the right edge at 390px (phase 1)

The 390 px screenshots clip the right edge of the page: headless Chrome's minimum window is wider than 390, and the existing page layout (not this change) is wider than the viewport. The wait pills wrap inside the visible cards.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-27T20:36:26+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

wait_of is one small pure function written straight from the table; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-27T20:36:26+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the protocol and the runner method are new and minimal, sharing the existing _list_tabs/_status_of helpers

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-27T20:36:26+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

LaneOwners and the column owners are new, minimal code beside existing models

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-27T20:45:35+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · The R2 background test built boards with statuses={}, so background never changed a wait (phase 1)

The R2 background test built boards with statuses={}, so background never changed a wait

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-27T20:45:35+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · A null lane_owners, a lone string or a null lane refused the repo's whole triage.yaml; a user-written ignored key faked a note (phase 1)

A null lane_owners, a lone string or a null lane refused the repo's whole triage.yaml; a user-written ignored key faked a note

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-27T20:45:35+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · A lane card with no owners showed no (unassigned) while its header did (phase 1)

A lane card with no owners showed no (unassigned) while its header did

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-27T20:45:35+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · Gated PR cards in Tester/DevOps lanes rendered no wait or owners (phase 1)

Gated PR cards in Tester/DevOps lanes rendered no wait or owners

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-27T20:45:35+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · A wrapped wait pill kept its full radius, turning a long owner list into a circle (phase 1)

A wrapped wait pill kept its full radius, turning a long owner list into a circle

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-27T20:45:35+00:00 phase=1 -->
### review-p1 · review · phase 1 review: 5 in-scope findings, all fixed (phase 1)

Independent reviewer (separate context) checked waits.py against spec §A row by row, SessionActivity, read_sessions, LaneOwners, escaping, docs and tests; raised p1-r1..p1-r5, all in scope, all fixed in 35b795095 with tests (384 targeted tests pass).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-27T20:45:35+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: The R2 background test built boards with statuses={}, so background never changed a wait (phase 1)

test_background_never_moves_a_column_or_a_hint now uses idle statuses, asserts a wait differs, then that columns and hints are equal.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-27T20:45:35+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: A null lane_owners, a lone string or a null lane refused the repo's whole triage.yaml; a user-written ignored key faked a note (phase 1)

LaneOwners' before-validator normalises null/str/null-list, drops non-strings into the note, treats a user `ignored:` as unknown (stored as fr_ignored_keys); four parse_triage_config tests, post_merge survives.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-27T20:45:35+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: A lane card with no owners showed no (unassigned) while its header did (phase 1)

_wait always names owners or (unassigned) for a role wait in a Needs-you column, never outside one; two tests.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-27T20:45:35+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: Gated PR cards in Tester/DevOps lanes rendered no wait or owners (phase 1)

_gated_card renders the lane's wait pill and owners; two tests.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-27T20:45:35+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: A wrapped wait pill kept its full radius, turning a long owner list into a circle (phase 1)

Owners moved to a muted span.wait-owners line under a short pill; test_the_owners_never_sit_inside_the_pill.

<!-- fr:journal kind=decision scope=plan id=p2-done-unmeasured created=2026-11-27T21:05:29+00:00 phase=2 -->
### p2-done-unmeasured · decision · Time per wave leaves out the Done column (phase 2)

A Done batch's open interval is time since it finished and grows without bound, so
wave_time skips intervals in Done (dwell.UNMEASURED). The time a Done batch spent in
earlier columns still counts. The card itself still shows "in Done <d>" (R6). A wave
whose batches only sat in Done shows "No time measured outside Done."

<!-- fr:journal kind=decision scope=plan id=p2-open-interval created=2026-11-27T21:05:29+00:00 phase=2 -->
### p2-open-interval · decision · The open state counts from the later since, like a closed interval (phase 2)

Consecutive intervals partition a batch's time (each starts at max(column_since,
wait_since)), so wave_time counts the open state as (column, wait, max(sinces), now).
Counting column time from column_since would double-count the closed intervals of the
same column after a wait-only change.

<!-- fr:journal kind=discovery scope=plan id=p2-ref-without-ledger created=2026-11-27T21:05:29+00:00 phase=2 -->
### p2-ref-without-ledger · discovery · A moved ref with no dwell.json removes the local one (phase 2)

fetch_state's existing loop deletes REF_FILES entries the ref no longer carries; with
dwell.json exempt from clashes, a moved ref written by an older fr (no ledger) drops a
local ledger rather than refusing. Times start over; tested.

<!-- fr:journal kind=discovery scope=plan id=p2-vis-layout created=2026-11-27T21:05:29+00:00 phase=2 -->
### p2-vis-layout · discovery · Time per wave sits above the cutoff toggle, and its table cells are tight (phase 2)

Per spec §E the section follows the queue section, which places it above the board's
"last 30 days" toggle. In the screenshots the table.grid.narrow cells sit close together
(e.g. "1h 15m mins 1h 15m") but stay legible at desktop and 390px. Left as is.

<!-- fr:journal kind=discovery scope=plan id=p2-zsh-modifier created=2026-11-27T21:05:29+00:00 phase=2 -->
### p2-zsh-modifier · discovery · zsh reads $R:t in a level ref as a modifier (phase 2)

Writing --level unit=$R:tests/... in zsh applies the :t (tail) modifier and produced
"super-frests/..."; fr refused the ref. Brace the variable (${R}:tests/...).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-27T21:05:29+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

the tally helpers were cleaned in place (a mutable [secs, mark] list became a (secs, mark) tuple and the tie-break for the longest batch became batch-id order); nothing further to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-27T21:05:29+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

the change is one exemption tuple in fetch_state and one keyword argument per writer; nothing to clean

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-27T21:18:35+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · The one-writer rule failed across hosts: a render beside a cloud/other-host driver stored dwell.json and pushed the state ref (phase 2)

The one-writer rule failed across hosts: a render beside a cloud/other-host driver stored dwell.json and pushed the state ref

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-27T21:18:35+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · Naive datetimes in dwell.json passed load and crashed observe/card_dwell (phase 2)

Naive datetimes in dwell.json passed load and crashed observe/card_dwell

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-27T21:18:35+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · Time per wave left out Done against R7's per column (phase 2)

Time per wave left out Done against R7's per column

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-27T21:18:35+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · The wave table overflowed at 390px with a 40-char id and its cells had no padding (phase 2)

The wave table overflowed at 390px with a 40-char id and its cells had no padding

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-27T21:18:35+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · fr-triage.md claimed two processes never race on the ledger (phase 2)

fr-triage.md claimed two processes never race on the ledger

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-11-27T21:18:35+00:00 phase=2 state=open review_scope=out -->
### p2-r6 · finding [open] (reviewer: out of scope) · docs/triage/README.md's export sentence was already inaccurate before this change (phase 2)

docs/triage/README.md's export sentence was already inaccurate before this change

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-11-27T21:18:35+00:00 phase=2 -->
### review-p2 · review · phase 2 review: 5 in-scope findings fixed, 1 out of scope (phase 2)

Independent reviewer checked dwell.py against §D case by case, fetch_state's exemption, the single writer, load/store, durations, wave_time, cutoff, escaping, budget, tests and docs; raised p2-r1..p2-r6; p2-r1..r5 fixed (HEAD 727ab9cd4) with tests (371 targeted pass), p2-r6 out of scope.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-27T21:18:35+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: The one-writer rule failed across hosts: a render beside a cloud/other-host driver stored dwell.json and pushed the state ref (phase 2)

write_board stores only with no live drive.lock and no unexpired lease (an unreadable lease counts as a driver); four tests incl. non-writer leaves the bytes untouched; spec R5/§D amended.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-27T21:18:35+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: Naive datetimes in dwell.json passed load and crashed observe/card_dwell (phase 2)

AwareDatetime on every time field; load gives an empty ledger plus its note; two tests.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-27T21:18:35+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: Time per wave left out Done against R7's per column (phase 2)

Spec R7 and §E amended in this PR: Done is left out because its open interval only grows.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-27T21:18:35+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: The wave table overflowed at 390px with a 40-char id and its cells had no padding (phase 2)

Cell padding, id in its own span with overflow-wrap, table in an overflow-x:auto wrapper; two tests.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-27T21:18:35+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: fr-triage.md claimed two processes never race on the ledger (phase 2)

Reworded to the real rule and its one-lost-observation limit.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-11-27T21:18:35+00:00 phase=2 state=open resolves=p2-r6 out_of_scope=true -->
### p2-r6-resolved · finding [out-of-scope] · resolves p2-r6: docs/triage/README.md's export sentence was already inaccurate before this change (phase 2)

Export copying only DURABLE files predates this change; this PR only named dwell.json in the existing sentence.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-27T21:25:22+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · One failed pane read lost every background mark

One failed pane read lost every background mark

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-27T21:25:22+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · An unguarded dwell.store failure failed the whole Batches render

An unguarded dwell.store failure failed the whole Batches render

<!-- fr:journal kind=finding scope=plan id=l-errors-r3 created=2026-11-27T21:25:22+00:00 state=open review_scope=in -->
### l-errors-r3 · finding [open] (reviewer: in scope) · A non-mapping lane_owners value refused the repo's whole triage config

A non-mapping lane_owners value refused the repo's whole triage config

<!-- fr:journal kind=finding scope=plan id=l-errors-r4 created=2026-11-27T21:25:22+00:00 state=open review_scope=in -->
### l-errors-r4 · finding [open] (reviewer: in scope) · lane_owner_notes worded three different causes as 'not a lane'

lane_owner_notes worded three different causes as 'not a lane'

<!-- fr:journal kind=finding scope=plan id=l-errors-r5 created=2026-11-27T21:25:22+00:00 state=open review_scope=in -->
### l-errors-r5 · finding [open] (reviewer: in scope) · An unusable dwell.json was overwritten without a copy, the note lacked path and loc

An unusable dwell.json was overwritten without a copy, the note lacked path and loc

<!-- fr:journal kind=finding scope=plan id=l-errors-r6 created=2026-11-27T21:25:22+00:00 state=open review_scope=out -->
### l-errors-r6 · finding [open] (reviewer: out of scope) · Supervisor.on_refusal swallows render failures with a bare pass

Supervisor.on_refusal swallows render failures with a bare pass

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-27T21:25:22+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · herdr-control-sessions.md overstated the pane reads

herdr-control-sessions.md overstated the pane reads

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-27T21:25:22+00:00 state=open review_scope=in -->
### l-docs-accuracy-r2 · finding [open] (reviewer: in scope) · fr-triage.md states the writer rule but did not cover its files

fr-triage.md states the writer rule but did not cover its files

<!-- fr:journal kind=review scope=plan id=lens-review created=2026-11-27T21:25:22+00:00 -->
### lens-review · review · lens review: docs-accuracy 2 findings, errors 6 (5 in, 1 out)

One reviewer per lens over the whole diff from 0ba6b3c1; both checked the shape file against the diff (no contradiction). In-scope findings fixed in 39bea405d with tests (438 targeted pass).

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-27T21:25:22+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: One failed pane read lost every background mark

Each pane read is guarded, pane-less agents skipped; test_one_unreadable_pane_never_loses_another_items_background_mark.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-27T21:25:22+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: An unguarded dwell.store failure failed the whole Batches render

OSError becomes the note 'dwell times are not stored'; the page still renders; test added.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3-resolved created=2026-11-27T21:25:22+00:00 state=fixed resolves=l-errors-r3 -->
### l-errors-r3-resolved · finding [fixed] · resolves l-errors-r3: A non-mapping lane_owners value refused the repo's whole triage config

Mapped to empty lanes with cause not-a-mapping; parse_triage_config test, post_merge survives.

<!-- fr:journal kind=finding scope=plan id=l-errors-r4-resolved created=2026-11-27T21:25:22+00:00 state=fixed resolves=l-errors-r4 -->
### l-errors-r4-resolved · finding [fixed] · resolves l-errors-r4: lane_owner_notes worded three different causes as 'not a lane'

Per-cause IgnoredLane records and wording; two tests incl. the facts JSON round trip.

<!-- fr:journal kind=finding scope=plan id=l-errors-r5-resolved created=2026-11-27T21:25:22+00:00 state=fixed resolves=l-errors-r5 -->
### l-errors-r5-resolved · finding [fixed] · resolves l-errors-r5: An unusable dwell.json was overwritten without a copy, the note lacked path and loc

The writer sets it aside as dwell.json.bad (not on the ref); notes name the path and the first error's loc and msg; three tests.

<!-- fr:journal kind=finding scope=plan id=l-errors-r6-resolved created=2026-11-27T21:25:22+00:00 state=open resolves=l-errors-r6 out_of_scope=true -->
### l-errors-r6-resolved · finding [out-of-scope] · resolves l-errors-r6: Supervisor.on_refusal swallows render failures with a bare pass

The bare pass predates this change (supervise.py); this change only passes writer=True into the same render call.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-27T21:25:22+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: herdr-control-sessions.md overstated the pane reads

The section now says reads stop at the first pane with background work and an unreadable pane is skipped.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-27T21:25:22+00:00 state=fixed resolves=l-docs-accuracy-r2 -->
### l-docs-accuracy-r2-resolved · finding [fixed] · resolves l-docs-accuracy-r2: fr-triage.md states the writer rule but did not cover its files

covers now lists triage_kanban_cmd.py and triage_drive_loop.py; the paragraph names dwell.json.bad.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved-2 created=2026-11-27T21:54:45+00:00 phase=2 state=open resolves=p2-r6 tracked_by=https://github.com/derio-net/super-fr/issues/1756 -->
### p2-r6-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1756] · resolves p2-r6: docs/triage/README.md's export sentence was already inaccurate before this change (phase 2)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1756.
