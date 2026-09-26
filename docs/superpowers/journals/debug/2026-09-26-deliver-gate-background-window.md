# Journal: 2026-09-26-deliver-gate-background-window

<!-- fr:journal kind=repro scope=debug id=repro-bg-window created=2026-09-26T17:18:53 -->
### repro-bg-window · repro · deliver tests= gate refuses a log written by a run_in_background suite

Orchestrator runs 'pytest ... > log 2>&1' with run_in_background; the transcript's tool_result is the launch ack ~1s later (14:12:37->14:12:38 in the observed session), the log's mtime is when the suite ends (15:05). orchestrator_wrote_since pairs (tool_use, tool_result) so the mtime is outside every window -> 'its bytes were not written by the command of yours that names it'. A foreground call over ~120s is auto-backgrounded, so any suite over ~2 min hits this.

<!-- fr:journal kind=root-cause scope=debug id=rc-ack-is-not-completion created=2026-09-26T17:18:55 -->
### rc-ack-is-not-completion · root-cause · window end is the launch ack, not the command's completion

telemetry.orchestrator_wrote_since (windows.append((issued[id], done)) with done = the tool_result timestamp) treats every tool_result as completion. For a backgrounded Bash the tool_result says 'Command running in background with ID: X'; real completion is a later user record whose string content holds <task-notification> with <tool-use-id> and <status> (completed|failed|killed). The gate never reads it.

<!-- fr:journal kind=finding scope=debug id=fix-notice-window created=2026-09-26T17:26:43 state=fixed review_scope=in -->
### fix-notice-window · finding [fixed] (reviewer: in scope) · window ends at the task-notification for a backgrounded command

telemetry.orchestrator_wrote_since: a tool_result with toolUseResult.backgroundTaskId is the launch ack and no longer closes the window; the user <task-notification> record naming the same <tool-use-id> with <status>completed</status> does. failed/killed/still-running yield no window (same rule as a foreground is_error). Pinned by 5 tests in tests/unit/test_run_telemetry.py over a captured fixture (claude-code-bash-background.jsonl).

<!-- fr:journal kind=review scope=debug id=review-gate-fix created=2026-09-26T17:28:17 -->
### review-gate-fix · review · independent review of the gate fix: no provenance weakening found

Reviewer a3be0e06072843aad: notices read only from main-thread user records with string content, id must belong to an orchestrator command that wrote the log, only status completed counts, OpenCode path untouched, 5 tests non-vacuous, fixture redacted. Noted, out of scope: the window for a backgrounded command is as wide as the suite (inherent to anchoring on the log's mtime, covered by the docstring's forgery limit); a duplicate/failed-then-completed notice pair is not emitted by the harness; a tool_use_id TypeError on malformed transcripts pre-exists; an unrecognised notice shape reports the generic 'no command of YOURS wrote it'.

<!-- fr:journal kind=finding scope=debug id=opus-r1-summary-injection created=2026-09-26T23:40:14 state=open review_scope=in -->
### opus-r1-summary-injection · finding [open] (reviewer: in scope) · summary-quoted description can forge <status>completed</status> or another command's id

telemetry._task_notice read every field occurrence and kept the last; the <summary> quotes the agent-written Bash description.

<!-- fr:journal kind=finding scope=debug id=opus-r2-unmarked-notice created=2026-09-26T23:40:16 state=open review_scope=in -->
### opus-r2-unmarked-notice · finding [open] (reviewer: in scope) · any string-content user record with the tag was accepted as a notice

Operator paste or !cmd stdout; the harness marker origin.kind=task-notification was ignored; a failed notice did not retire the id, so a later forged completed counted.

<!-- fr:journal kind=finding scope=debug id=opus-r3-late-window-end created=2026-09-26T23:40:18 state=open review_scope=in -->
### opus-r3-late-window-end · finding [open] (reviewer: in scope) · window ended at notice delivery, not the command's end

Below reviewer threshold but taken: the queue-operation enqueue is earlier when the orchestrator is mid-turn.

<!-- fr:journal kind=finding scope=debug id=opus-r4-completed-uncaptured created=2026-09-26T23:40:20 state=open review_scope=in -->
### opus-r4-completed-uncaptured · finding [open] (reviewer: in scope) · completed status never captured live

Fixture only had failed; helper synthesised completed.
