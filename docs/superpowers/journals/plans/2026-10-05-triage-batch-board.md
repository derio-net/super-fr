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
