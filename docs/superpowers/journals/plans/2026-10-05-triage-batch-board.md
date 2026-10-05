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
