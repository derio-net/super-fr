# Journal: 2026-09-28-tests-log-symlinked-dir

<!-- fr:journal kind=repro scope=debug id=39d1330041ad created=2026-09-28T16:31:55+00:00 -->
### 39d1330041ad · repro · deliver tests= refuses a log under a symlinked dir (macOS /tmp)

gh#758. `mvn -q test > /tmp/x.log 2>&1` then `fr run resolve --step deliver --evidence tests=/tmp/x.log` is refused: "no command of YOURS wrote it". `/tmp` -> `/private/tmp` on macOS.

<!-- fr:journal kind=root-cause scope=debug id=b3a48e50b336 created=2026-09-28T16:31:57+00:00 -->
### b3a48e50b336 · root-cause · _is_log compares an unresolved absolute target against a resolved log path

`run_cmd._verify_tests_log` resolves the evidence path (`.resolve()` -> `/private/tmp/x.log`); `telemetry._is_log` compares the literal absolute target (`/tmp/x.log`) with `==`, so any log reached through a symlinked directory never matches.
