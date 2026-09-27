# Journal: 2026-09-27-opencode-detach-tests-gate

<!-- fr:journal kind=repro scope=debug id=d677891c15d6 created=2026-09-27T10:27:00 -->
### d677891c15d6 · repro · OpenCode's detach form gives the tests= gate a zero-length window (gh#719)

OpenCode long-command rule (fr/harness/long_commands.py): `(cmd; echo "exit=$?") > log 2>&1 & echo $! > log.pid`. The bash tool part completes as soon as the `&` launches, so `_opencode_wrote_since` (fr/run/telemetry.py) records a window (launch start, launch end) of ~0s. The suite writes the log minutes later; its mtime falls outside every window and `_check_tests_log` refuses with "no command of YOURS wrote it". Repro: a top-level bash part with that command (window 0s) + log mtime 10 min later -> refused.

<!-- fr:journal kind=hypothesis scope=debug id=67097efe5339 created=2026-09-27T10:27:00 -->
### 67097efe5339 · hypothesis · The gate has no end-of-run signal for a detached OpenCode command

Unlike Claude Code (#693/#702: run_in_background launch ack -> task-notification closes the window), OpenCode records no event when a detached child ends. But it DOES record every later bash part's `state.output` (verified on a live DB: keys input/metadata/output/status/time/title). The rule already makes the log end with `exit=N`, so the orchestrator's own later command that names the log and prints `exit=0` is a harness-recorded completion signal: window = (launch start, that observation's end). Bounded above by what the orchestrator saw, so a later overwrite still refuses.
