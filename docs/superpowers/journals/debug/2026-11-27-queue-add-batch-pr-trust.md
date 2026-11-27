<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-queue-add-batch-pr-trust

<!-- fr:journal kind=repro scope=debug id=6fcfd41cef55 created=2026-11-27T20:06:08+00:00 -->
### 6fcfd41cef55 · repro · queue add --preapproved refuses a batch PR whose Closes lines name its members

`fr triage queue add --pr N --preapproved` on batch PRs #1734 and #1735 refused with 'its author and origin were never read; re-collect', while two stale drafts with no Closes lines were accepted. Repro: tests/unit/test_triage_queue_cmd.py::test_a_batch_pr_known_only_through_its_member_issue_is_preapproved (batch PR #17 present only in issue 1's prs) exits 2 on main.

<!-- fr:journal kind=hypothesis scope=debug id=c3c792188da9 created=2026-11-27T20:06:10+00:00 -->
### c3c792188da9 · hypothesis · the trust read searches only facts.prs

collect files a PR whose Closes lines name an issue under that issue's prs; facts.prs holds only open PRs linked to no issue. queue add looked up author/cross_repo in facts.prs alone, so a linked PR read as never-read. Confirmed by the new tests failing on main.

<!-- fr:journal kind=root-cause scope=debug id=73a9581e21ca created=2026-11-27T20:06:12+00:00 -->
### 73a9581e21ca · root-cause · queue add reads PR author and origin from facts.prs only, so a linked batch PR has no identity

packages/fr/src/fr/commands/triage_queue_cmd.py queue_add_command looked up the PR in facts.prs (unlinked open PRs). A batch PR closes its members, so collect files it under those issues' prs; the lookup returned None and distrust() answered 'never read'. batch_pr (via _branch_prs) already pools member-linked PRs, facts.prs and facts.batch_prs and applies distrust itself.

<!-- fr:journal kind=finding scope=debug id=d-fix-1 created=2026-11-27T20:06:14+00:00 state=fixed -->
### d-fix-1 · finding [fixed] · trust a batch PR by batch_pr's verdict; read any other PR from the same pool

queue_add_command resolves the batch first: a batch PR (found by _batch_of, i.e. batch_pr, which trusts only same-repo PRs by allowed authors) skips the second distrust. Any other PR is read by the new _known_pr from issue prs + facts.prs + facts.batch_prs, preferring a record whose author and origin were read. Tests: test_a_batch_pr_known_only_through_its_member_issue_is_preapproved, test_a_linked_pr_that_is_no_batch_s_is_added, test_a_linked_fork_or_foreign_pr_is_still_refused.

<!-- fr:journal kind=review scope=debug id=d-review-1 created=2026-11-27T20:09:11+00:00 -->
### d-review-1 · review · independent review of the queue add trust fix: no findings

A separate reviewer read triage_queue_cmd.py, its tests, the fragment and batch.py.
No in-scope or out-of-scope findings (review-findings: []). Checked: a batch PR's
trust comes from batch_pr (distrust + repo + dispatch-branch + of_dispatch); a fork
or foreign PR on a batch branch falls to the ordinary path and is refused as itself;
repo and number both filter _known_pr; an unread PR still refuses with re-collect;
the head_ref fallback is unchanged. Noted, not a finding: two disagreeing records of
one PR resolve first-seen, the same dedupe _branch_prs uses.
