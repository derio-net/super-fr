# Journal: 2026-09-28-tests-log-symlinked-dir

<!-- fr:journal kind=repro scope=debug id=39d1330041ad created=2026-09-28T16:31:55+00:00 -->
### 39d1330041ad · repro · deliver tests= refuses a log under a symlinked dir (macOS /tmp)

gh#758. `mvn -q test > /tmp/x.log 2>&1` then `fr run resolve --step deliver --evidence tests=/tmp/x.log` is refused: "no command of YOURS wrote it". `/tmp` -> `/private/tmp` on macOS.
