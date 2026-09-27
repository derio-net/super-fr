# Journal: 2026-09-27-opencode-holder-identity

<!-- fr:journal kind=repro scope=debug id=be650f4db6df created=2026-09-27T09:32:31+00:00 -->
### be650f4db6df · repro · An OpenCode process launched from a Claude Code shell records claude-code and a Claude session as the unit holder

Reproduced from code plus the installed OpenCode 1.18.32 binary. OpenCode sets `OPENCODE=1` and `OPENCODE_PID` at startup; a Claude Code bash tool exports `CLAUDECODE=1`, `CLAUDE_PID` and `CLAUDE_CODE_SESSION_ID`. An OpenCode started from a Claude Code shell inherits all of them. Under that env:
- `detect_harness` (fr/harness/detect.py:37) checks the claude-code markers FIRST and returns `claude-code`;
- `fr run advance` stamps `Attempt.harness` from `detect_harness` and `Attempt.session` from `telemetry.current_session` (run_cmd.py `_open_dispatch`), which reads `CLAUDE_CODE_SESSION_ID` whatever the harness;
- `Attempt.agent_type` is the manifest id (`super-fr:fr-phase-executor`), never the OpenCode tier agent `fr-phase-executor-<tier>` that actually ran;
- `fr run claim` needs `--step`/`--item`, which the OpenCode plugin (the only party that sees the child session id while it holds the unit) does not know (gh#530).
