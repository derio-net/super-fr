<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-queue-add-batch-pr-trust

<!-- fr:journal kind=repro scope=debug id=6fcfd41cef55 created=2026-11-27T20:06:08+00:00 -->
### 6fcfd41cef55 · repro · queue add --preapproved refuses a batch PR whose Closes lines name its members

`fr triage queue add --pr N --preapproved` on batch PRs #1734 and #1735 refused with 'its author and origin were never read; re-collect', while two stale drafts with no Closes lines were accepted. Repro: tests/unit/test_triage_queue_cmd.py::test_a_batch_pr_known_only_through_its_member_issue_is_preapproved (batch PR #17 present only in issue 1's prs) exits 2 on main.
