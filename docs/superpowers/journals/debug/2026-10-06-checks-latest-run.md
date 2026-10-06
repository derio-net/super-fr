# Journal: 2026-10-06-checks-latest-run

<!-- fr:journal kind=repro scope=debug id=e8703ea341c5 created=2026-10-06T20:17:24+00:00 -->
### e8703ea341c5 · repro · A check re-run green on the same head still counts as failing

PR #1038, head f1919d4: `gh pr view --json statusCheckRollup` returns BOTH CI runs on that head — the 17:00 run (test (py3.11, 2), test (py3.14, 2), ci-ok = FAILURE) and the 19:53 run (all SUCCESS). `collect._checks` buckets every entry, so PullRequest.checks reads fail=3 forever and `checks_verdict` (no required checks on main) returns failing; the merge train never merges it.

<!-- fr:journal kind=ruled-out scope=debug id=87c0c9aaea05 created=2026-10-06T20:17:29+00:00 -->
### 87c0c9aaea05 · ruled-out · The drive's own gh pr checks path is not a second cause

`GhClient.pr_checks`/`pr_required_checks` shell to `gh pr checks`, which already reports the latest run per check. On a branch with no required checks `checks_verdict` falls through to the collected `PullRequest.checks` counts — the only path that sees stale runs is `collect._checks`. The same counts feed views.py, render.py, kanban.py, so one fix covers them.

<!-- fr:journal kind=root-cause scope=debug id=dea78f795763 created=2026-10-06T20:17:31+00:00 -->
### dea78f795763 · root-cause · collect._checks counts superseded check runs

statusCheckRollup lists every CheckRun of every workflow run on the head commit (and every StatusContext). `_checks` never collapses entries naming the same check, so a superseded failure is counted beside its newer success. GitHub's UI and `gh pr checks` keep only the most recent run per (workflow, check name) / status context.

<!-- fr:journal kind=finding scope=debug id=131419e2f90d created=2026-10-06T20:42:52+00:00 state=fixed -->
### 131419e2f90d · finding [fixed] · collect counts one run per check, the latest

New `collect._latest_runs` collapses statusCheckRollup to one entry per (workflowName, name) / StatusContext context, the most recent by startedAt; a not-yet-started, not-completed run ranks newest (a queued re-run reads pending, never its predecessor's green). Entries with no identity are each counted. Pinned red-first in tests/unit/test_triage_open_prs.py by the live #1038 rollup (fixture super-fr-rerun-checks.json), order-independence, the queued-rerun case and cross-workflow/status-context separation. The older captured-fixture test had pinned the double count (16 runs for 8 checks) and now counts distinct checks. Full suite: 9733 passed, 123 skipped; ruff + mypy clean.
