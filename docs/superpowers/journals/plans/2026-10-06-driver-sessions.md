# Journal: 2026-10-06-driver-sessions

<!-- fr:journal kind=decision scope=plan id=plan-shape created=2026-10-06T18:52:57+00:00 -->
### plan-shape · decision · Three agentic phases, one per reviewable ask; no member issue is a tracking_issue

P1 restart engine + CLI + install (skeleton,

<!-- fr:journal kind=discovery scope=plan id=herdr-agent-start-name-reuse created=2026-10-06T19:30:58+00:00 phase=1 -->
### herdr-agent-start-name-reuse · discovery · herdr accepts the pane's own agent name again right after /exit; it refuses only when another pane holds it (phase 1)

Probed live (herdr 0.9.1) in scratch tabs. After `/exit` the pane drops out of `agent list` (the name is released), and `agent start <same name> --kind claude --pane <same pane> -- --resume <id>` is ACCEPTED with the same agent_session.value and name (fixture agent-start-reuse.json). A different pane starting a name another pane holds gets `agent_name_taken` (agent-start-name-taken.json). So the named `agent start` path is primary, and `agent_name_taken` alone triggers the send-text fallback.

<!-- fr:journal kind=discovery scope=plan id=claude-agent-count-is-not-background-work created=2026-10-06T19:30:58+00:00 phase=1 -->
### claude-agent-count-is-not-background-work · discovery · `← N agent` is on every idle Claude status line, so only shells/monitors and the agent panel mean background work (phase 1)

Spec §A treats `← N agent(s)` as background-agent evidence. Live, a freshly started session with nothing running already shows `← 1 agent`, and the count did not change while a background subagent ran (the status line then also showed `2 shells, 1 monitor` and an agent panel, `⏺ main` / `◯ general-purpose ...`, while herdr reported `done`). `has_background_work` therefore counts `N shells|monitors`, a `◯` panel row, or `← N agents` with N above 1. Using the spec's literal rule would have skipped nearly every pane. The hint segments also vanish from the status line while a draft is typed, and herdr still says `idle` then.

<!-- fr:journal kind=discovery scope=plan id=pane-read-is-raw-text created=2026-10-06T19:30:58+00:00 phase=1 -->
### pane-read-is-raw-text · discovery · `herdr pane read` prints raw terminal text, not a JSON envelope (phase 1)

`_run_herdr` returns it as `{"raw": <text>}` (stripped), so the screen fixtures are that return value and restart.py reads `.get("raw")`. process-info's foreground_processes also lists non-claude processes (MCP servers; one has no `argv` key), so the claude process is found by argv[0] basename, and its cwd (not the pane's) slugs the transcript path. An extra classify reason `no-process` covers a pane with no claude in the foreground.

<!-- fr:journal kind=discovery scope=plan id=exit-dialog-not-live-captured created=2026-10-06T19:30:58+00:00 phase=1 -->
### exit-dialog-not-live-captured · discovery · Claude's exit dialog is quoted from #964, not captured (phase 1)

An unsent feedback draft is not reproducible without sending feedback, so no fixture of the dialog exists; the engine matches "unsent feedback draft" / "Enter to review & send" in the visible text and the tests use that quoted string. The fixtures README says so.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-10-06T19:30:58+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a smoke test over captured fixtures; no production code existed to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-06T19:30:58+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

cli.py is 58 lines of argparse over restart_idle written once to its tests; nothing duplicated or misnamed

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-06T19:30:58+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

shell and test additions follow the existing atomic_symlink and stub-uv patterns; nothing to tidy
