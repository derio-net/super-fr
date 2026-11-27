# `rules/branches/<branch>` replies — captured, for `fr.config.protection`

Captured live on **2026-11-25** with `gh api` 2.x (`gh api repos/<repo>/rules/branches/<branch>`),
for spec `2026-11-19-event-driven-a-la-carte` R7 (plan `2026-11-24-s1-configuration-homes`,
P3.T1.S1). Each `.json` file is the command's stdout; each `.error.json` is
`{exit, stdout, stderr}` exactly as gh gave them.

- `pull-request.json` — a public third-party repo whose effective rules hold `deletion`,
  `non_fast_forward` and `pull_request`. **Redacted**: the org and repo names in
  `ruleset_source` are replaced by `example-org` / `example-org/example-repo`, and the
  `ruleset_id` / `integration_id` numbers by 1001-1003. Nothing else was edited.
- `pull-request-approved.json` — captured **2026-11-25** the same way: a public third-party repo
  whose effective rules are exactly `deletion`, `non_fast_forward` and `pull_request` with
  `required_approving_review_count: 1` (review p3-r3: the only reply fr reads as enforced).
  **Redacted**: `ruleset_source` is `example-org/example-repo` and `ruleset_id` is 1004.
  Nothing else was edited. `pull-request.json` (0 approvals) is the negative case. Its
  `dismiss_stale_reviews_on_push` and `require_last_push_approval` are both `false`, so a push
  after the approval keeps it: fr reads this reply as **not** enforced (lens review
  l-security-r1).
- `pull-request-approved-dismiss-stale.json` — **not a separate capture**: it is
  `pull-request-approved.json` with one parameter flipped, `dismiss_stale_reviews_on_push`
  `false` → `true` (made 2026-11-25 for lens review l-security-r1, because no live reply with it
  set could be captured then). Every other byte is the capture's. It is the reply fr reads as
  enforced.
- `no-pull-request.json` — `derio-net/super-fr` `main`: `deletion`, `non_fast_forward` and
  `required_status_checks`, no `pull_request` rule.
- `empty.json` — `derio-net/super-fr` `fr-config`, a branch with no rules (`[]`).
- `not-found.error.json` — a repo that does not exist under `derio-net` (HTTP 404).
- `free-plan.error.json` — a private `derio-net` repo on the free plan: the HTTP 403 whose
  message is `Upgrade to GitHub Pro or make this repository public` (the reply names no repo).
