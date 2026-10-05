# Journal: 2026-10-05-triage-batch-board

<!-- fr:journal kind=discovery scope=plan id=p1-herdr-focus-capture created=2026-10-05T20:38:15+00:00 phase=1 -->
### p1-herdr-focus-capture · discovery · herdr focus fixtures captured live (phase 1)

Captured with herdr 0.9.1 inside herdr (workspace focus / tab focus on the already-focused ones). workspace focus returns result.type workspace_info; tab focus returns tab_info. Tab label redacted to example-tab-1.

<!-- fr:journal kind=decision scope=plan id=p1-focus-error-shape created=2026-10-05T20:38:15+00:00 phase=1 -->
### p1-focus-error-shape · decision · focus refusals are one line via a local load_runner and _try_load (phase 1)

triage_kanban_cmd keeps its own find_spec-guarded load_runner and _fail (never importing triage_batch_cmd), and _try_load captures err_console so an unloadable runner is one error line with no traceback.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-10-05T20:38:15+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

fixture capture, nothing to refactor

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-10-05T20:38:15+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

the two new protocols share no framing with SessionCloser beyond 'optional, beside Runner'; docstrings are already one line each

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-05T20:38:15+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

close() now shares _tabs_labelled with session_statuses and focus; existing_dispatches builds a label set and reads better as is

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-05T20:38:15+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

probe_item duplicates about ten lines of WorkItem construction from _Driver._sessions, but a shared pure helper would only return constants the caller wraps into a WorkItem anyway; left as is

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-10-05T20:42:39+00:00 phase=1 -->
### review-p1 · review · phase 1 code review: 8 minor findings, all in scope (phase 1)

Independent reviewer approved with minor findings p1-r1..p1-r8 (no Critical/Important); each verified against the code and fixed with a test or direct change.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-05T20:42:39+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · probe_item duplicated _Driver._sessions WorkItem construction (phase 1)

probe_item duplicated _Driver._sessions WorkItem construction

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-05T20:42:39+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · load_runner/_fail/_try_load duplicated triage_batch_cmd's (phase 1)

load_runner/_fail/_try_load duplicated triage_batch_cmd's

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-05T20:42:39+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · focus/load exception text interpolated raw (multi-line, empty) (phase 1)

focus/load exception text interpolated raw (multi-line, empty)

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-05T20:42:39+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · no test for the real load_runner -> _fail -> typer.Exit capture path (phase 1)

no test for the real load_runner -> _fail -> typer.Exit capture path

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-10-05T20:42:39+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · herdr precedence tests did not pin the whole order (phase 1)

herdr precedence tests did not pin the whole order

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-10-05T20:42:39+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · protocol membership test vacuous without __protocol_attrs__ (phase 1)

protocol membership test vacuous without __protocol_attrs__

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-10-05T20:42:39+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · probe annotated Any discarded WorkItem typing (phase 1)

probe annotated Any discarded WorkItem typing

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-10-05T20:42:39+00:00 phase=1 state=open review_scope=in -->
### p1-r8 · finding [open] (reviewer: in scope) · matrix row cited only the focus CLI test (phase 1)

matrix row cited only the focus CLI test

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-05T20:42:39+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: probe_item duplicated _Driver._sessions WorkItem construction (phase 1)

drive now builds its probes with triage_kanban_cmd.probe_item (same group via wave_group(self.workspace_prefix, wave)).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-05T20:42:39+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: load_runner/_fail/_try_load duplicated triage_batch_cmd's (phase 1)

triage_batch_cmd imports _fail and try_load from triage_kanban_cmd; its load_runner is a thin seam delegating to kanban's with its own install hint; _try_runner uses try_load(name, self.runner).

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-05T20:42:39+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: focus/load exception text interpolated raw (multi-line, empty) (phase 1)

one_line(exc) collapses whitespace and falls back to the type name; used for focus failures and try_load; captured _fail text also collapsed. Test: test_a_multi_line_focus_failure_is_one_line.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-05T20:42:39+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: no test for the real load_runner -> _fail -> typer.Exit capture path (phase 1)

test_a_runner_the_registry_cannot_load_is_one_captured_line drives the real registry with an uninstalled runner name.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-10-05T20:42:39+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: herdr precedence tests did not pin the whole order (phase 1)

parametrised test over every adjacent pair of blocked>working>idle>done>unknown in both tab orders.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-10-05T20:42:39+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: protocol membership test vacuous without __protocol_attrs__ (phase 1)

skips explicitly before 3.12 and asserts 'dispatch' is a member so the check reads real members.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-10-05T20:42:39+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: probe annotated Any discarded WorkItem typing (phase 1)

annotation removed; mypy clean.

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-10-05T20:42:39+00:00 phase=1 state=fixed resolves=p1-r8 -->
### p1-r8-resolved · finding [fixed] · resolves p1-r8: matrix row cited only the focus CLI test (phase 1)

fr acceptance set-status added unit=super-fr:tests/unit/test_fr_herdr_runner.py with updated notes.

<!-- fr:journal kind=decision scope=plan id=p2-build-board-no-notes created=2026-10-05T21:09:03+00:00 phase=2 -->
### p2-build-board-no-notes · decision · build_board takes no notes (phase 2)

Page notes belong to the page (spec D passes them to render_board); Board carries scope and collected_at only.

<!-- fr:journal kind=decision scope=plan id=p2-no-forge-url-guess created=2026-10-05T21:09:03+00:00 phase=2 -->
### p2-no-forge-url-guess · decision · a member missing from the facts has no link (phase 2)

Its Member has stage unknown and url None; the forge URL is never guessed.

<!-- fr:journal kind=discovery scope=plan id=p2-hint-partial-closeout-due created=2026-10-05T21:09:03+00:00 phase=2 -->
### p2-hint-partial-closeout-due · discovery · a partial batch can read close-out due in Done (phase 2)

partial is LANDED so drive_pass emits closeout for it; R6 puts the driver's action first, so the Done/partial card shows the action phrase, as specified.

<!-- fr:journal kind=discovery scope=plan id=p2-clipboard-timing created=2026-10-05T21:09:03+00:00 phase=2 -->
### p2-clipboard-timing · discovery · copied appears after the clipboard promise resolves (phase 2)

A capture script must wait for the confirmation before asserting button text; fixed in the script, not the page.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-10-05T21:09:03+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

a one-function extraction; _chosen now calls default_selection, nothing else repeated

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-10-05T21:09:03+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

the column table is already one ordered mapping (COLUMN_TITLES) with a stage map; no branch repeats

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-10-05T21:09:03+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

phrase tables and hint strings are already module constants beside the column table

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-10-05T21:09:03+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

kanban.py is ~370 lines, under the 400 split threshold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t5 created=2026-10-05T21:09:03+00:00 phase=2 -->
### no-refactor-p2-t5 · discovery · no-refactor-because P2.T5 (phase 2)

esc, FONTS and _safe_url are imported from render.py, not copied

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t6 created=2026-10-05T21:09:03+00:00 phase=2 -->
### no-refactor-p2-t6 · discovery · no-refactor-because P2.T6 (phase 2)

scope_args is the one scope-arg builder; focus builds no scope args, so the drive (phase 3) is its second caller

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t7 created=2026-10-05T21:09:03+00:00 phase=2 -->
### no-refactor-p2-t7 · discovery · no-refactor-because P2.T7 (phase 2)

browser check and matrix moves only; no code to clean

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-10-05T21:16:47+00:00 phase=2 -->
### review-p2 · review · phase 2 code + visual review: 5 in-scope low findings, 1 out-of-scope (phase 2)

Independent reviewer approved with minor fixes p2-r1..p2-r5 (fixed) and p2-r6 (out of scope); it drove the page itself in Chrome (light/dark, 375/1000px, scripts off, clipboard removed/denied, close-out copy, auto-refresh) and opened every fresh shot.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-05T21:16:47+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · write_board reload test could never fail (phase 2)

Test now asserts card-b1 sits in the proposed column, then in running (and not proposed) after judgements change on disk, via a _column() section extractor.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-05T21:16:47+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · unknown asserted via note text, not the card pill (phase 2)

Test asserts the status-unknown pill inside the running column.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-10-05T21:16:47+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · board_command re-loaded state just to count batches (phase 2)

write_board returns (path, card count) from the one load; command prints that.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-10-05T21:16:47+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · relative --dir copied verbatim (phase 2)

scope_args resolves --dir to an absolute path; test_a_relative_dir_is_copied_as_an_absolute_path.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-10-05T21:16:47+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · command wrap split tokens (phase 2)

code.cmd uses overflow-wrap: break-word.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-10-05T21:16:47+00:00 phase=2 state=open review_scope=out -->
### p2-r6 · finding [open] (reviewer: out of scope) · partial batch in Done shows a close-out hint (phase 2)

Reviewer: R2 puts partial in Done while the driver still emits close-out due for it.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-05T21:16:47+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: write_board reload test could never fail (phase 2)

Test now asserts card-b1 sits in the proposed column, then in running (and not proposed) after judgements change on disk, via a _column() section extractor.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-05T21:16:47+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: unknown asserted via note text, not the card pill (phase 2)

Test asserts the status-unknown pill inside the running column.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-10-05T21:16:47+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: board_command re-loaded state just to count batches (phase 2)

write_board returns (path, card count) from the one load; command prints that.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-10-05T21:16:47+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: relative --dir copied verbatim (phase 2)

scope_args resolves --dir to an absolute path; test_a_relative_dir_is_copied_as_an_absolute_path.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-10-05T21:16:47+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: command wrap split tokens (phase 2)

code.cmd uses overflow-wrap: break-word.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-10-05T21:16:47+00:00 phase=2 state=open resolves=p2-r6 out_of_scope=true -->
### p2-r6-resolved · finding [out-of-scope] · resolves p2-r6: partial batch in Done shows a close-out hint (phase 2)

Not a defect of this change: operator decision d2 put partial in Done, and spec-review finding sr-4 deliberately kept a partial card's live hint, status and jump buttons until its close-out finishes, so the board reports the driver faithfully. Changing the column table would be a new operator decision.

<!-- fr:journal kind=decision scope=plan id=p3-drive-lock-module created=2026-10-05T21:33:23+00:00 phase=3 -->
### p3-drive-lock-module · decision · drive-lock liveness moved to fr/triage/drive_lock.py (phase 3)

pid_alive, lock_text, lock_pid, DRIVE_LOCK and live_driver are pure path+pid logic there; triage_batch_cmd imports them under its old private names (so its tests patching _pid_alive still work) and triage_kanban_cmd imports live_driver, keeping the command-module import one-way.

<!-- fr:journal kind=decision scope=plan id=p3-watch-collect-failure created=2026-10-05T21:33:23+00:00 phase=3 -->
### p3-watch-collect-failure · decision · --watch collect failures warn once per cause and still render (phase 3)

A TriageError from the collect seam (recollect) prints one warning per distinct message, the board is still written from what is on disk, and the loop continues; Ctrl-C ends it with exit 0.

<!-- fr:journal kind=discovery scope=plan id=p3-plural-batches created=2026-10-05T21:33:23+00:00 phase=3 -->
### p3-plural-batches · discovery · plural(n, 'batch') printed 'batchs' (phase 3)

noun() only appended s; the phase-2 board line and the existing merge line both said '6 batchs'. Found while running the visual capture; fixed in noun() (-ch/-sh/-s/-x take es) with a test.

<!-- fr:journal kind=discovery scope=plan id=p3-explainers-none created=2026-10-05T21:33:23+00:00 phase=3 -->
### p3-explainers-none · discovery · no explainer describes triage batches or the driver (phase 3)

grep of docs/explainers/*.md for triage and driver found nothing, so explainers-currency owes no page update.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-10-05T21:33:23+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

the guard was extracted as _Driver._write_board in S2 (S3 done by construction)

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-10-05T21:33:23+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

the seams are named recollect and _sleep like the drive's; nothing else repeats

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-10-05T21:33:23+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

triage.html link is one keyword threaded through render/_batches; nothing repeated to clean
