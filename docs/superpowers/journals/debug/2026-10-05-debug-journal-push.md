# Journal: 2026-10-05-debug-journal-push

<!-- fr:journal kind=repro scope=debug id=c8b825f274df created=2026-10-05T20:37:40+00:00 -->
### c8b825f274df · repro · Review journal entry committed after the PR's last push never reaches it

fr-debugging §4 orders: open PR -> `fr journal add --scope debug --kind review` -> relay closeout -> stop. `fr journal add` commits locally and never pushes (no push anywhere under fr/journal or fr/record/apply.py). Seen on #860: review entry r1 committed 17:18 UTC, PR merged 17:52 UTC without it; verify-merge / archive / down all refused at close-out. Repro: follow §4 literally; `git rev-list --count @{u}..HEAD` is 1 when the session stops.

<!-- fr:journal kind=hypothesis scope=debug id=95d6812b3938 created=2026-10-05T20:37:43+00:00 -->
### 95d6812b3938 · hypothesis · Skill §4 has no push step after its last journal commit

The only commit-producing step after the PR opens is the review record; the prose never pushes it and never checks the branch is level with its upstream before stopping.
