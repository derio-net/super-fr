# Journal: 2026-09-27-opencode-holder-identity

<!-- fr:journal kind=repro scope=debug id=be650f4db6df created=2026-09-27T09:32:31+00:00 -->
### be650f4db6df · repro · An OpenCode process launched from a Claude Code shell records claude-code and a Claude session as the unit holder

Reproduced from code plus the installed OpenCode 1.18.32 binary. OpenCode sets `OPENCODE=1` and `OPENCODE_PID` at startup; a Claude Code bash tool exports `CLAUDECODE=1`, `CLAUDE_PID` and `CLAUDE_CODE_SESSION_ID`. An OpenCode started from a Claude Code shell inherits all of them. Under that env:
- `detect_harness` (fr/harness/detect.py:37) checks the claude-code markers FIRST and returns `claude-code`;
- `fr run advance` stamps `Attempt.harness` from `detect_harness` and `Attempt.session` from `telemetry.current_session` (run_cmd.py `_open_dispatch`), which reads `CLAUDE_CODE_SESSION_ID` whatever the harness;
- `Attempt.agent_type` is the manifest id (`super-fr:fr-phase-executor`), never the OpenCode tier agent `fr-phase-executor-<tier>` that actually ran;
- `fr run claim` needs `--step`/`--item`, which the OpenCode plugin (the only party that sees the child session id while it holds the unit) does not know (gh#530).

<!-- fr:journal kind=root-cause scope=debug id=17cef48d7094 created=2026-09-27T09:32:34+00:00 -->
### 17cef48d7094 · root-cause · fr names a holder from inherited ambient env, never from the process that holds the unit

One cause, two faces. (1) #537: the holder identity is inferred from environment variables that cross process boundaries; detection gives claude-code a fixed precedence and the session key is Claude-only, so the outer harness is named instead of the one fr runs under. (2) #530: the one source that DOES know the holder, the child session itself (seen by fr-opencode-plugin on its first tool call), has no way to report it, because `fr run claim` requires the unit named. Fix: detection resolves a multi-harness env by the NEAREST ancestor harness pid (`CLAUDE_PID`/`OPENCODE_PID`), with explicit `FR_HARNESS` still winning; the session is recorded only when the detected harness owns that key; and `fr run claim --open-unit` lets the plugin claim the sole open unclaimed attempt from the child, carrying the agent that ran.
