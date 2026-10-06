# Journal: 2026-10-06-checks-latest-run

<!-- fr:journal kind=repro scope=debug id=e8703ea341c5 created=2026-10-06T20:17:24+00:00 -->
### e8703ea341c5 · repro · A check re-run green on the same head still counts as failing

PR #1038, head f1919d4: `gh pr view --json statusCheckRollup` returns BOTH CI runs on that head — the 17:00 run (test (py3.11, 2), test (py3.14, 2), ci-ok = FAILURE) and the 19:53 run (all SUCCESS). `collect._checks` buckets every entry, so PullRequest.checks reads fail=3 forever and `checks_verdict` (no required checks on main) returns failing; the merge train never merges it.
