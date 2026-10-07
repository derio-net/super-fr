# Journal: 2026-10-06-triage-batch-adopt

<!-- fr:journal kind=discovery scope=plan id=p1-herdr-renames-hand-started-agent created=2026-10-06T20:08:58+00:00 phase=1 -->
### p1-herdr-renames-hand-started-agent · discovery · herdr renames an agent it did not launch; it is addressed by pane id until named (phase 1)

Captured live 2026-10-06 (herdr 0.9.0) in a scratch workspace `fr-adopt-scratch`,
`claude` started with `herdr pane run` (not `agent start`): `herdr agent list`
reports the hand-started agent with no `name` and no `agent_session`;
`herdr agent rename <pane-id> <name>` exits 0 and `herdr agent get <name>` then
resolves it. So `HerdrRunner` addresses an agent by `name` when it has one, else
by `pane_id`. herdr also auto-relabels a tab running claude
(`1 · adopt › claude › model haiku`). Two scratch workspaces were created and
closed (the second for one coherent capture of all three lists); no other tab or
agent was renamed, messaged or closed. Fixtures and provenance:
tests/fixtures/herdr/README.md.

<!-- fr:journal kind=discovery scope=plan id=p1-gh-pr-create-captured-live created=2026-10-06T20:08:58+00:00 phase=1 -->
### p1-gh-pr-create-captured-live · discovery · No captured `gh pr create` existed; one was captured against a scratch branch and cleaned up (phase 1)

tests/fixtures held no `gh pr create` capture (the existing pr_create test used a
hand-written URL). Per the brief, an empty commit on origin/main was pushed to
`scratch/fr-adopt-capture` on derio-net/super-fr, `gh pr create --draft` opened
PR #1044, `gh pr view --json …` and `gh pr close` were captured, and the branch was
deleted with `gh api -X DELETE …/git/refs/heads/scratch/fr-adopt-capture` (prints
nothing). PR #1044 is closed, the branch is gone (`git ls-remote` empty).
Fixtures: tests/fixtures/gh/ (README records it).

<!-- fr:journal kind=decision scope=plan id=p1-delete-old-branch-through-the-forge created=2026-10-06T20:08:58+00:00 phase=1 -->
### p1-delete-old-branch-through-the-forge · decision · The old remote branch is deleted through GhClient.delete_branch; gitseam gained no delete (phase 1)

Spec §A named two new gitseam operations (publish, delete remote branch) while §C
put "delete branch" on the GhClient adapter; implementing both would leave one
dead. Adopt deletes through `GhClient.delete_branch` (glab/tea refuse it via
UnsupportedBatchOps), and gitseam gained `publish_branch` plus the two reads the
verb needs (`worktree_of`, `has_branch`). The batch tripwire now forbids
`fr.isolation` in batch modules except `from fr.isolation.rename import
rename_branch, IsolationError`; `rename_branch(dry_run=True)` gives the verb its
refusals before any write without a second isolation import.

<!-- fr:journal kind=decision scope=plan id=p1-pr-view-and-create-pr created=2026-10-06T20:08:58+00:00 phase=1 -->
### p1-pr-view-and-create-pr · decision · pr_view now also returns title and body; create_pr added beside pr_create (phase 1)

`GhClient.pr_create` already existed (never draft, returns the number) for the
driver's export PR. Adopt needs the draft state and the URL, so `create_pr(…,
draft)` returns `{number, url}` and `pr_create` delegates to it. The superseded
PR's title and body are read by adding `title,body` to `pr_view`'s `--json`.

<!-- fr:journal kind=decision scope=plan id=p1-adopt-idempotence-boundaries created=2026-10-06T20:08:58+00:00 phase=1 -->
### p1-adopt-idempotence-boundaries · decision · How adopt decides a step is done on a re-run (phase 1)

Rename: rename_branch's own plan (local old gone, marker/record/cursor on new).
Publish: the batch branch on origin. New PR: an OPEN PR on the batch branch; then
the event is stamped no later than its creation (never before the batch's last
event), so of_dispatch keeps it. Supersede comment: a comment on the old PR
starting `Superseded by #<new>`. Close/delete: the old PR open / old branch on
origin. Tab: `runner.adopt` is always called — the protocol makes it a no-op when
already adopted. Event: the batch's last event is a dispatch with this tab as
handle and the batch branch. Forge writes: `_forge_writes`, already idempotent.
The message is the last step and is not tracked: a re-run after a FULL success
sends it again (harmless; nothing else changes).

<!-- fr:journal kind=discovery scope=plan id=p1-drive-already-matched-recorded-branch created=2026-10-06T20:08:58+00:00 phase=1 -->
### p1-drive-already-matched-recorded-branch · discovery · R13's drive behaviour already held; its test pins it, and the three branch readers were the gap (phase 1)

`batch._branch_prs` and `of_dispatch` already match by `event.branch` and event
time, so the new drive_pass/derive_batch_stage test for an adopted batch passed
before any change. The RED part of P1.T4 was the three readers (closeout_brief,
attributed, dispatch_comment), which now use `recorded_branch`. Note: the T4 RED
tests were swept into the T3 commit by a backgrounded `git add -A`; the history
is otherwise one commit per task.

<!-- fr:journal kind=discovery scope=plan id=p1-no-explainer-owed created=2026-10-06T20:08:58+00:00 phase=1 -->
### p1-no-explainer-owed · discovery · No explainer describes triage, so the minor bump owes no explainer update (phase 1)

docs/explainers holds only 01-fr-goal and fr-isolation (plus index); neither
describes `fr triage batch`, so explainers-currency asks for nothing here.

<!-- fr:journal kind=finding scope=plan id=p1-wall-clock-tests-flake-under-host-load created=2026-10-06T20:08:58+00:00 phase=1 state=open review_scope=out -->
### p1-wall-clock-tests-flake-under-host-load · finding [open] (reviewer: out of scope) · Two wall-clock-budget tests fail in the full suite under heavy host load and pass alone (phase 1)

The final full suite (`uv run pytest -q --no-cov -n auto`, log in evidence) ended
`2 failed, 9756 passed, 115 skipped` with the host's 15-minute load average at
~130 (the operator's other sessions and ~20 devcontainers):
`tests/integration/test_run_idle_guard.py::test_fails_open_when_fr_hangs_and_does_not_hang_with_it`
("the stub was never reached") and
`tests/unit/test_records_commit.py::test_a_record_commit_gives_up_on_a_stuck_index_lock_quickly`
(5.96s against a 5.0s budget). An earlier full run at load ~60 also failed four
`tests/unit/test_run_evidence_visual.py` tests on file-mtime-vs-transcript timing.
None of these touch code this phase changed; all six pass when re-run alone
(`6 passed in 49.17s`, $TMPDIR/adopt-fail6.log). Wall-clock-tight under load,
per AGENTS.md's xdist note; not fixed here.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-10-06T20:08:58+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

rename_branch was written plan-then-apply from the start (plan_rename reads and refuses, rename_branch writes only what the plan holds); nothing duplicated to clean beyond naming

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-06T20:08:58+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the one duplication, parsing `gh pr create`'s URL, was removed in GREEN itself: pr_create now delegates to create_pr(draft=False)

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-06T20:08:58+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

recorded_branch is the whole change; the three readers each call it once

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-10-06T20:08:58+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

no refactor step: skill prose, matrix rows, change fragment and the gate

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-10-06T21:05:51+00:00 phase=1 -->
### p1-review-1 · review · phase 1 code review: 11 findings p1-r1..p1-r11, all in scope (phase 1)

Dispatched reviewer read diff ccb71a11..HEAD, ran 261 targeted tests (pass), checked R8 ordering, R10 resumability, shell safety (argv only), conventions (no version edits, fragment, skill 119 lines, mirrors in sync, import direction). Raised p1-r1..p1-r11, all in scope; all fixed in this step (c6f0f541, 9a37cc9a, 94d5c64c, spec §A).

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-06T21:05:51+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · adopt copied/closed PRs and accepted a batch-branch PR without distrust()/pr_authors (phase 1)

adopt copied/closed PRs and accepted a batch-branch PR without distrust()/pr_authors

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-06T21:05:51+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · first-run event `at` could exceed the new PR's second-truncated createdAt (phase 1)

first-run event `at` could exceed the new PR's second-truncated createdAt

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-06T21:05:51+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · no refusal for --branch being the default branch (would rename and delete main) (phase 1)

no refusal for --branch being the default branch (would rename and delete main)

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-06T21:05:51+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · failed cursor commit not resumable (phase 1)

failed cursor commit not resumable

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-10-06T21:05:51+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · marker/record rewrites non-atomic; marker not validated against toplevel (phase 1)

marker/record rewrites non-atomic; marker not validated against toplevel

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-10-06T21:05:51+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · supersede-comment detection accepted any author (phase 1)

supersede-comment detection accepted any author

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-10-06T21:05:51+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · delete_branch did not URL-quote the branch (phase 1)

delete_branch did not URL-quote the branch

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-10-06T21:05:51+00:00 phase=1 state=open review_scope=in -->
### p1-r8 · finding [open] (reviewer: in scope) · failure inside a --yes step exited 2 without the done/remain report (phase 1)

failure inside a --yes step exited 2 without the done/remain report

<!-- fr:journal kind=finding scope=plan id=p1-r9 created=2026-10-06T21:05:51+00:00 phase=1 state=open review_scope=in -->
### p1-r9 · finding [open] (reviewer: in scope) · R9 worktree refusals skipped when --branch already is the batch branch (phase 1)

R9 worktree refusals skipped when --branch already is the batch branch

<!-- fr:journal kind=finding scope=plan id=p1-r10 created=2026-10-06T21:05:51+00:00 phase=1 state=open review_scope=in -->
### p1-r10 · finding [open] (reviewer: in scope) · test gaps (several agents, plain branch, dispatched/pr-open stage, loose resume assertion) (phase 1)

test gaps (several agents, plain branch, dispatched/pr-open stage, loose resume assertion)

<!-- fr:journal kind=finding scope=plan id=p1-r11 created=2026-10-06T21:05:51+00:00 phase=1 state=open review_scope=in -->
### p1-r11 · finding [open] (reviewer: in scope) · --checkout single-path vs spec §A REPO=PATH, departure not journaled (phase 1)

--checkout single-path vs spec §A REPO=PATH, departure not journaled

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-06T21:05:51+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: adopt copied/closed PRs and accepted a batch-branch PR without distrust()/pr_authors (phase 1)

Fixed c6f0f541: both branches' PRs gated by the driver's trust rule before any write; fork and foreign-author cases tested.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-06T21:05:51+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: first-run event `at` could exceed the new PR's second-truncated createdAt (phase 1)

Fixed c6f0f541: `at` truncated to seconds, floored at the last event, clamped to the created PR's createdAt; same-second and skewed-clock tests.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-06T21:05:51+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: no refusal for --branch being the default branch (would rename and delete main) (phase 1)

Fixed c6f0f541: default branch and main-worktree branch refused before any write; rename/delete steps re-check.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-06T21:05:51+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: failed cursor commit not resumable (phase 1)

Fixed 9a37cc9a: uncommitted cursor naming the new branch counts as not done and is committed on resume.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-10-06T21:05:51+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: marker/record rewrites non-atomic; marker not validated against toplevel (phase 1)

Fixed 9a37cc9a: save_state atomic for every caller; marker for another toplevel is not rewritten.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-10-06T21:05:51+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: supersede-comment detection accepted any author (phase 1)

Fixed c6f0f541: only the operator's own comment counts.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-10-06T21:05:51+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: delete_branch did not URL-quote the branch (phase 1)

Fixed 94d5c64c: quoted, tested with `#`.

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-10-06T21:05:51+00:00 phase=1 state=fixed resolves=p1-r8 -->
### p1-r8-resolved · finding [fixed] · resolves p1-r8: failure inside a --yes step exited 2 without the done/remain report (phase 1)

Fixed c6f0f541: any failure after the first write reports and exits 1.

<!-- fr:journal kind=finding scope=plan id=p1-r9-resolved created=2026-10-06T21:05:51+00:00 phase=1 state=fixed resolves=p1-r9 -->
### p1-r9-resolved · finding [fixed] · resolves p1-r9: R9 worktree refusals skipped when --branch already is the batch branch (phase 1)

Fixed 9a37cc9a/c6f0f541: refusals apply; tested.

<!-- fr:journal kind=finding scope=plan id=p1-r10-resolved created=2026-10-06T21:05:51+00:00 phase=1 state=fixed resolves=p1-r10 -->
### p1-r10-resolved · finding [fixed] · resolves p1-r10: test gaps (several agents, plain branch, dispatched/pr-open stage, loose resume assertion) (phase 1)

Fixed c6f0f541/9a37cc9a: all four covered, exact resume counts.

<!-- fr:journal kind=finding scope=plan id=p1-r11-resolved created=2026-10-06T21:05:51+00:00 phase=1 state=fixed resolves=p1-r11 -->
### p1-r11-resolved · finding [fixed] · resolves p1-r11: --checkout single-path vs spec §A REPO=PATH, departure not journaled (phase 1)

Fixed in the spec: §A now states adopt takes dispatch's single-path --checkout, because a batch is always one repo.

<!-- fr:journal kind=finding scope=plan id=p1-wall-clock-tests-flake-under-host-load-resolved created=2026-10-06T21:05:51+00:00 phase=1 state=open resolves=p1-wall-clock-tests-flake-under-host-load out_of_scope=true -->
### p1-wall-clock-tests-flake-under-host-load-resolved · finding [out-of-scope] · resolves p1-wall-clock-tests-flake-under-host-load: Two wall-clock-budget tests fail in the full suite under heavy host load and pass alone (phase 1)

Not caused by this change: test_run_idle_guard::test_fails_open_when_fr_hangs_and_does_not_hang_with_it and test_records_commit::...stuck_index_lock_quickly assert wall-clock limits and failed only at host load 130-226; both pass alone (logs adopt-fail6.log, adopt-idle-guard-rerun.log). Neither touches adopt code. Worth an issue: wall-clock tests flake under host load.
