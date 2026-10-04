# Journal: 2026-10-04-batch-driver-pr-trust

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-04T06:16:54+00:00 -->
### repro · repro · batch_pr attributes a PR by repo, head branch name and creation time only

Code-level repro on main f850fceb (gh#936): `batch_pr` (triage/batch.py) keeps every PR with `p.repo == repo and p.head_ref == event.branch and of_dispatch(p, event)`; `pr_open_queue` feeds it to `drive_pass`, which emits `merge` for any non-draft green one. A fork PR (isCrossRepository) or a foreign-author PR named `fix/batch-<id>` opened after the dispatch is therefore merged unattended. `attributed()` (batch_drive.py) attributes archive PRs by head name / files, likewise with no origin check.
