# Journal: 2026-10-05-debug-journal-push

<!-- fr:journal kind=repro scope=debug id=c8b825f274df created=2026-10-05T20:37:40+00:00 -->
### c8b825f274df · repro · Review journal entry committed after the PR's last push never reaches it

fr-debugging §4 orders: open PR -> `fr journal add --scope debug --kind review` -> relay closeout -> stop. `fr journal add` commits locally and never pushes (no push anywhere under fr/journal or fr/record/apply.py). Seen on #860: review entry r1 committed 17:18 UTC, PR merged 17:52 UTC without it; verify-merge / archive / down all refused at close-out. Repro: follow §4 literally; `git rev-list --count @{u}..HEAD` is 1 when the session stops.

<!-- fr:journal kind=hypothesis scope=debug id=95d6812b3938 created=2026-10-05T20:37:43+00:00 -->
### 95d6812b3938 · hypothesis · Skill §4 has no push step after its last journal commit

The only commit-producing step after the PR opens is the review record; the prose never pushes it and never checks the branch is level with its upstream before stopping.

<!-- fr:journal kind=ruled-out scope=debug id=416b7f149748 created=2026-10-05T20:37:44+00:00 -->
### 416b7f149748 · ruled-out · fr journal add is not expected to push

By design every journal/record write is one local commit; pushes are host-side git I/O (fr-isolation: all git-host I/O runs on the host, outside exec). Making the engine push would break that seam, so the engine is not the defect.

<!-- fr:journal kind=root-cause scope=debug id=1968bc31ff3c created=2026-10-05T20:37:46+00:00 -->
### 1968bc31ff3c · root-cause · §4 records the review after the PR's last push and has no push after it

The review record is the last commit of the run, written after the PR opened, and the skill's step order ends at 'relay closeout, stop' with no push and no ahead-of-upstream check — so the commit stays local and the merged PR lacks it.

<!-- fr:journal kind=finding scope=debug id=4038889f25de created=2026-10-05T21:07:05+00:00 state=fixed -->
### 4038889f25de · finding [fixed] · Deliver pushes after the review record and checks level-with-upstream before the closeout relay

plugins/super-fr/skills/fr-debugging/SKILL.md §4 (+ both mirrors re-synced): after `fr journal add --kind review`, `git push` on the host and confirm `git rev-list --count @{u}..HEAD` is 0, before relaying `closeout: fr pickup --branch`. Pinned first by tests/unit/test_fr_debugging_journal.py::test_review_record_is_pushed_before_the_closeout_relay (red on all three copies at 6c582a926, green after). Full suite: 8441 passed, 1 failed (test_sentinel_lifecycle::test_looking_into_another_workspace_does_not_stake_the_pipeline_on_it — passes alone; untouched by this prose-only change, load flake).

<!-- fr:journal kind=review scope=debug id=899c29cad61e created=2026-10-05T21:07:44+00:00 -->
### 899c29cad61e · review · Independent review: no in-scope findings

Reviewer checked prose placement in all three copies, host-only push consistency with fr-isolation's git-host I/O rule, test ordering/slicing robustness, and that the review record is §4's only post-PR commit. No in-scope findings. Noted (out of scope, cosmetic): `@{u}` errors loudly rather than passing if no upstream is set; a removed `--kind review` raises a bare ValueError instead of the custom message.
