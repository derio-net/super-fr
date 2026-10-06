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
