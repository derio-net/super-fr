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
