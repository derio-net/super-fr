# Journal: 2026-09-27-opencode-detach-tests-gate

<!-- fr:journal kind=repro scope=debug id=d677891c15d6 created=2026-09-27T10:27:00 -->
### d677891c15d6 · repro · OpenCode's detach form gives the tests= gate a zero-length window (gh#719)

OpenCode long-command rule (fr/harness/long_commands.py): `(cmd; echo "exit=$?") > log 2>&1 & echo $! > log.pid`. The bash tool part completes as soon as the `&` launches, so `_opencode_wrote_since` (fr/run/telemetry.py) records a window (launch start, launch end) of ~0s. The suite writes the log minutes later; its mtime falls outside every window and `_check_tests_log` refuses with "no command of YOURS wrote it". Repro: a top-level bash part with that command (window 0s) + log mtime 10 min later -> refused.

<!-- fr:journal kind=hypothesis scope=debug id=67097efe5339 created=2026-09-27T10:27:00 -->
### 67097efe5339 · hypothesis · The gate has no end-of-run signal for a detached OpenCode command

Unlike Claude Code (#693/#702: run_in_background launch ack -> task-notification closes the window), OpenCode records no event when a detached child ends. But it DOES record every later bash part's `state.output` (verified on a live DB: keys input/metadata/output/status/time/title). The rule already makes the log end with `exit=N`, so the orchestrator's own later command that names the log and prints `exit=0` is a harness-recorded completion signal: window = (launch start, that observation's end). Bounded above by what the orchestrator saw, so a later overwrite still refuses.

<!-- fr:journal kind=root-cause scope=debug id=28a3f48e4ef4 created=2026-09-27T10:41:28 -->
### 28a3f48e4ef4 · root-cause · A detached launch's own end was the only end the OpenCode reader knew

Confirmed by the red test built from the rule text itself: `_opencode_wrote_since` windowed every writer at (part start, part end), and the rule's `&` makes the part end at launch. Single root cause; #720 ($VAR binding) is a separate root in `_resolve_target` and is left alone.

<!-- fr:journal kind=finding scope=debug id=6114f2adcc31 created=2026-09-27T10:41:29 state=fixed -->
### 6114f2adcc31 · finding [fixed] · Detached writer windowed to the first later exit=N it printed (N=0 only)

telemetry.py: `_detaches` (a lone `&`, outside quotes/heredocs; not `&&`, `|&`, `&>`, `2>&1`), `_names` (any word of a command resolving to the log), `_seen_exit` (first later completed top-level bash part naming the log with an `exit=N` line in its output — first is final, N must be 0). The launch window is still recorded, so nothing narrows. Refusal message and the OpenCode rule (brief + phase-executor clause, mirrors synced) now say the exit= line must be printed. Pinned by tests/unit/test_run_tests_log_opencode.py (detached/unobserved/failed/subagent/other-log/no-exit-line/first-is-final/foreground/e2e accept+refuse/detach-syntax).

<!-- fr:journal kind=review scope=debug id=adc0f691e0d8 created=2026-09-27T10:49:12 -->
### adc0f691e0d8 · review · Independent adversarial review: 1 finding, refuted as out of the gate's stated scope, residual documented

Reviewer (separate context) found no regex/ordering/test-shape defects. One finding: the detached window closes on log CONTENT the orchestrator read back, so a co-resident writer of `exit=0` into the exact log path before that read is accepted, weaker than Claude Code's harness-emitted notice. Verdict: real but deliberate forgery, which the gate explicitly does not claim to stop; the foreground path shares the co-resident-write-inside-window residual. Pid-tying rejected (log.pid is equally readable). Residual now stated in `_seen_exit`'s docstring and the PR body.
