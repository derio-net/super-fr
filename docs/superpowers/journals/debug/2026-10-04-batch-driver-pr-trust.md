# Journal: 2026-10-04-batch-driver-pr-trust

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-04T06:16:54+00:00 -->
### repro · repro · batch_pr attributes a PR by repo, head branch name and creation time only

Code-level repro on main f850fceb (gh#936): `batch_pr` (triage/batch.py) keeps every PR with `p.repo == repo and p.head_ref == event.branch and of_dispatch(p, event)`; `pr_open_queue` feeds it to `drive_pass`, which emits `merge` for any non-draft green one. A fork PR (isCrossRepository) or a foreign-author PR named `fix/batch-<id>` opened after the dispatch is therefore merged unattended. `attributed()` (batch_drive.py) attributes archive PRs by head name / files, likewise with no origin check.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-10-04T06:16:57+00:00 -->
### root-cause · root-cause · Facts carry no PR identity, so no attribution can check it

`fr.gh.PR_LIST_FIELDS` (the field list every PR read derives from: list_prs, list_open_prs, list_prs_by_head) asks for neither `author` nor `isCrossRepository`, and `PullRequest` has no field for either. `batch_pr` and `attributed()` match on what exists — a head branch NAME, which anyone who can open a PR (including from a fork) chooses freely. One root cause for both attributions: identity is never collected, so never checked.
