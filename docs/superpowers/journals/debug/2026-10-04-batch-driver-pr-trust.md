# Journal: 2026-10-04-batch-driver-pr-trust

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-04T06:16:54+00:00 -->
### repro · repro · batch_pr attributes a PR by repo, head branch name and creation time only

Code-level repro on main f850fceb (gh#936): `batch_pr` (triage/batch.py) keeps every PR with `p.repo == repo and p.head_ref == event.branch and of_dispatch(p, event)`; `pr_open_queue` feeds it to `drive_pass`, which emits `merge` for any non-draft green one. A fork PR (isCrossRepository) or a foreign-author PR named `fix/batch-<id>` opened after the dispatch is therefore merged unattended. `attributed()` (batch_drive.py) attributes archive PRs by head name / files, likewise with no origin check.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-10-04T06:16:57+00:00 -->
### root-cause · root-cause · Facts carry no PR identity, so no attribution can check it

`fr.gh.PR_LIST_FIELDS` (the field list every PR read derives from: list_prs, list_open_prs, list_prs_by_head) asks for neither `author` nor `isCrossRepository`, and `PullRequest` has no field for either. `batch_pr` and `attributed()` match on what exists — a head branch NAME, which anyone who can open a PR (including from a fork) chooses freely. One root cause for both attributions: identity is never collected, so never checked.

<!-- fr:journal kind=finding scope=debug id=fix created=2026-10-04T06:35:03+00:00 state=fixed -->
### fix · finding [fixed] · Attribution requires the repo's own branch and an allowed author

Collect now reads `author` and `isCrossRepository` on every PR (`PR_LIST_FIELDS`) and the authenticated login once (`Facts.viewer`). `batch.distrust` refuses a fork PR, a PR whose author is not in `allowed_authors` (`.fr/triage.yaml` `pr_authors`, else the viewer; case-insensitive), and an identity never read. `batch_pr` (so `batch merge`, `batch drive`, stages, board) keeps only trusted PRs; `foreign_batch_prs` names the open refused ones. `LivePr.trusted` (default False) gates `attributed()` for archive PRs. `drive_pass` emits one `foreign` action per refused PR, remembered by key so it prints once; the board lists it as foreign-pr under Needs you now and never says to ready it. The config arrives through the same freshness rule as post_merge: drive re-collects each pass and `merge_ctx` runs `_fresh_config` before any merge. Pinned by the gh#936 tests in test_triage_batch_model, test_triage_batch_drive, test_triage_batch_drive_cmd, test_triage_board_views and test_triage_open_prs.

<!-- fr:journal kind=review scope=debug id=review created=2026-10-04T06:49:34+00:00 -->
### review · review · Independent adversarial review: no merge path bypasses the trust check; one regression fixed

A separate reviewer traced every merge path: drive merges only `pr_open_queue` entries (all `batch_pr`, so trusted), pinned to number and head sha; archive PRs need `LivePr.trusted`, computed through `distrust` in both `_archive_prs` and `_live_head_prs`; case handling, empty viewer and config freshness hold; other GhClient adapters raise on `list_prs_by_head`. Findings: (1) FIXED — a merged/closed batch PR carried over from pre-fix facts (`known_batch_prs`) has no identity and would be distrusted forever, leaving its batch `dispatched`; collect now re-reads such a PR (test_a_terminal_known_pr_whose_identity_was_never_read_is_looked_up_again). (2) NOT CHANGED — `closeout_state` reads MERGED `chore/closeout-*` PRs from `facts.prs` without trust, but `facts.prs` holds only open PRs and the value only feeds a `batch list` display column. (3) OUT OF SCOPE, pre-existing — `batch merge --yes` merges the live head read at plan time, not the facts head; exploiting it needs write access to the repo's own branch, not a fork or foreign PR.
