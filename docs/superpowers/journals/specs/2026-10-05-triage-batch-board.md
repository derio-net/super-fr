# Journal: 2026-10-05-triage-batch-board

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-05T20:19:20+00:00 input=true -->
### operator-brief · discovery · Operator brief (verbatim)

I would like an extension for the Triage pages, the Wave Driver and the herdr dispatcher.. A new artifact that shows the state of all prepared/dispatched issues as a Kanban board, is refreshed via the state changes (or timer) and can be used to quickly jump to a corresponding herdr session (e.g. clicking on a button copies the herdr command that can be used to jump to the correct session). Each item should be expanded to show more information about it

<!-- fr:journal kind=decision scope=spec id=d1-card-unit created=2026-10-05T20:19:20+00:00 -->
### d1-card-unit · decision · One card per batch

A batch is one session, one branch, one PR; member issues appear inside the expanded card. (Q1, recommended option chosen.)

<!-- fr:journal kind=decision scope=spec id=d2-columns created=2026-10-05T20:19:20+00:00 -->
### d2-columns · decision · Lifecycle columns

Proposed, Waiting, Running, PR open, Closing out, Done; cancelled/abandoned/partial sit in Done with a pill. (Q2, recommended.)

<!-- fr:journal kind=decision scope=spec id=d3-artifact created=2026-10-05T20:19:20+00:00 -->
### d3-artifact · decision · Separate board.html via `fr triage board`

Written beside triage.html in the triage state dir; triage.html links to it. (Q3, recommended.)

<!-- fr:journal kind=decision scope=spec id=d4-refresh created=2026-10-05T20:19:20+00:00 -->
### d4-refresh · decision · Drive re-renders each pass, page reloads on a timer

Drive writes board.html after every acting pass; the page reloads itself (default 30s) keeping expanded cards and scroll; `fr triage board --watch` re-collects and re-renders when no drive runs. (Q4, recommended.)

<!-- fr:journal kind=decision scope=spec id=d5-jump-command created=2026-10-05T20:19:20+00:00 -->
### d5-jump-command · decision · Jump copies a new fr verb

The button copies `fr triage batch focus <batch-id>`, which resolves the session by label through the runner at run time and focuses it. (Q5, recommended.)

<!-- fr:journal kind=decision scope=spec id=d6-live-status created=2026-10-05T20:19:20+00:00 -->
### d6-live-status · decision · Live session status read at render

Render asks each batch's runner for session status through an optional capability; failures show `unknown`, never fail. Blocked sessions are highlighted. (Q6, recommended.)

<!-- fr:journal kind=decision scope=spec id=d7-expanded-content created=2026-10-05T20:19:20+00:00 -->
### d7-expanded-content · decision · Expanded card content

Members + PR + CI, lifecycle details, event timeline with close-out jump, and a next-action hint. (Q7, all four options chosen.)

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-10-05T20:25:45+00:00 -->
### spec-review-1 · review · independent spec review: 11 findings

Findings sr-1..sr-11, all in scope; decisions d1-d7 honoured. Load-bearing: sr-1 import direction, sr-2 hints, sr-3 offline close-out state, sr-5 drive render hook.

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-10-05T20:25:45+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · §C/§E import fr_dispatch from forbidden modules and set up a command-module cycle

Uses fr_dispatch.SessionStatus inside fr.triage.board (tests/unit/test_import_direction.py:17-25,31), and triage_batch_cmd <-> board command cycle.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-10-05T20:25:45+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · R6 hints cannot come from drive_pass alone; most cards would read 'nothing to do'

drive_pass emits no action for running, draft/pending, merely-unmerged deps, not-yet-due close-out (batch_drive.py:384,399-404,520-534,480-481,499-506); selection/cap differ from the drive (triage_batch_cmd.py:1375-1380).

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-10-05T20:25:45+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · is_finished from facts is false: drive_snapshot reads no archives

views.py:104-114 builds no archives; batch_drive.py:346-355; use closeout_state (batch.py:308) and state the offline limit.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-10-05T20:25:45+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · partial in Done but the driver still runs its close-out; R3 hides its jump button

LANDED includes partial (batch_drive.py:41; triage_batch_cmd.py:1603).

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-10-05T20:25:45+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · R11 hook: every pass vs when acting, stale judgements, missing scope args

triage_batch_cmd.py:1920-1948 loads before acting; _Driver keeps only target (:1469).

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-10-05T20:25:45+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · _session_statuses failure modes misnamed: load_runner exits via typer.Exit; probe needs payload.group

triage_batch_cmd.py:180-199, :1515-1536 _try_runner; fr_herdr/runner.py:120 preflight.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-10-05T20:25:45+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · Close-outs recorded with runner 'hand' not handled by R4/R7/R8

triage_batch_cmd.py:1977-1985 adopt writes runner hand; :1827 _sessions skips it.

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-10-05T20:25:45+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · --watch checks the drive lock only at start

drive_lock serialises drivers only (triage_batch_cmd.py:1269-1320); collect writes facts.json non-atomically.

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-10-05T20:25:45+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · herdr focus verbs have no captured evidence in the repo

No tab focus/workspace focus fixture under tests/fixtures/herdr/.

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-10-05T20:25:45+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · Copied command echoes --dir unquoted

R5/R14/§E: free-text --dir path in a pasted shell command.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-10-05T20:25:45+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · Ambiguities: R4 harness/model source, R13 dead link, untested R1/R10/R12/R13, --open not in requirements

model.py:264-274, :423-431; triage_batch_cmd.py:1910-1916.

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-10-05T20:25:45+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: §C/§E import fr_dispatch from forbidden modules and set up a command-module cycle

§C: fr.triage.board declares its own BoardStatus pinned equal by test; §E: all fr_dispatch contact moves into one new soft point triage_board_cmd.py (added to _SOFT_POINTS) importing only triage_cmd; triage_batch_cmd imports write_board one-way.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-10-05T20:25:45+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: R6 hints cannot come from drive_pass alone; most cards would read 'nothing to do'

R6 rewritten: blocked override, then drive_pass with the drive's default selection (new pure batch_drive.default_selection shared with _chosen) at the default cap, then a defined per-column fallback (incl. 'not driven'); tests listed per fallback.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-10-05T20:25:45+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: is_finished from facts is false: drive_snapshot reads no archives

R2/§C split merged by closeout_state == archived (reads the merged chore/closeout PR from facts); merged with no closeout event stays in Closing out with 'close-out not recorded', limit stated; fixtures listed.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-10-05T20:25:45+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: partial in Done but the driver still runs its close-out; R3 hides its jump button

R3/R4 jump button now shown whenever a dispatch (or runner close-out) exists and the session status is not 'no session', independent of column, so a partial card keeps its buttons, status and hint.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-10-05T20:25:45+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: R11 hook: every pass vs when acting, stale judgements, missing scope args

R11 and §F: render at the end of every --yes pass, acting or not; write_board reloads judgements.yaml; one-pass lag of forge effects stated; _Driver carries scope args incl. whether --dir was given; tests for non-acting pass and new events.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-10-05T20:25:45+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: _session_statuses failure modes misnamed: load_runner exits via typer.Exit; probe needs payload.group

§E session_statuses: _try_runner capture pattern (err_console.capture, typer.Exit and Exception), probes built as _sessions does with payload.group; R7 says no error is printed; tests assert no error: output.

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-10-05T20:25:45+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: Close-outs recorded with runner 'hand' not handled by R4/R7/R8

R4/R7/R8/§E: hand close-outs have no session, are never probed, show no close-out button, and focus --closeout refuses with a specific reason; fixture listed.

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-10-05T20:25:45+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: --watch checks the drive lock only at start

R12/§E: --watch re-checks the lock every iteration and skips collect+render while held (said once); collect is the one fr triage collect performs; test listed.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-10-05T20:25:45+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: herdr focus verbs have no captured evidence in the repo

Background/§B: herdr --help for both verbs read this session (tab focus <tab_id>, workspace focus <workspace_id>); §B requires capturing live output fixtures (focusing the already-focused tab/workspace) before building.

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-10-05T20:25:45+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: Copied command echoes --dir unquoted

R5/R14/§D: command built with shlex.join over validated id + scope args, then HTML-escaped; hostile --dir fixture listed.

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-10-05T20:25:45+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: Ambiguities: R4 harness/model source, R13 dead link, untested R1/R10/R12/R13, --open not in requirements

R4: harness/model from stored launch, else facts.config_for(repo).defaults.launch marked (default), else —; R13 link only when board.html exists; R1 states --open; tests added for R1 no-batches, R10 timestamps, R12 interval, R13 link.
