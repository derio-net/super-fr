# Journal: 2026-09-26-deliver-gate-background-window

<!-- fr:journal kind=repro scope=debug id=repro-bg-window created=2026-09-26T17:18:53 -->
### repro-bg-window · repro · deliver tests= gate refuses a log written by a run_in_background suite

Orchestrator runs 'pytest ... > log 2>&1' with run_in_background; the transcript's tool_result is the launch ack ~1s later (14:12:37->14:12:38 in the observed session), the log's mtime is when the suite ends (15:05). orchestrator_wrote_since pairs (tool_use, tool_result) so the mtime is outside every window -> 'its bytes were not written by the command of yours that names it'. A foreground call over ~120s is auto-backgrounded, so any suite over ~2 min hits this.

<!-- fr:journal kind=root-cause scope=debug id=rc-ack-is-not-completion created=2026-09-26T17:18:55 -->
### rc-ack-is-not-completion · root-cause · window end is the launch ack, not the command's completion

telemetry.orchestrator_wrote_since (windows.append((issued[id], done)) with done = the tool_result timestamp) treats every tool_result as completion. For a backgrounded Bash the tool_result says 'Command running in background with ID: X'; real completion is a later user record whose string content holds <task-notification> with <tool-use-id> and <status> (completed|failed|killed). The gate never reads it.
