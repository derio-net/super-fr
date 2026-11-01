<!-- fr:journal-schema=3 -->
# Journal: 2026-11-01-gitea-adapter-live-shapes

<!-- fr:journal kind=repro scope=debug id=repro created=2026-11-01T09:08:28+00:00 -->
### repro · repro · Phase 9 live walk: 9 of 30 RealTeaClient checks fail against real Gitea + tea 0.16.0

Walked 2026-11-01 against a self-hosted Gitea (operator's cluster, reached via kubectl port-forward because its external host is SSO-gated, derio-net/frank#909; host and LAN address redacted), tea 0.16.0, a private scratch repo. Driver: a script calling every RealTeaClient method. Failing: ensure_labels duplicates (2 labels named fr:walk after two calls); file_exists on a missing path returns True; pr_for_branch and default_branch always None; pr_status_by_url None for an http ROOT_URL and would read a merged PR as CLOSED; list_open_issues_with_body returns number as a str and splits labels on commas. Passing: list_linked_prs (PR surfaced, plain referencing issue excluded, merged state correct, deduped), contents read, pr_body by index/URL/branch, labels/comments/body edits, close/reopen.
