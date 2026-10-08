# `github-rest` fixtures — captured, never constructed

Captured live on **2026-10-08** from a **Claude Code cloud session** (its egress
proxy refuses GitHub GraphQL with HTTP 403 and allows REST), with `gh api`
2.89.0 against `derio-net/super-fr`, for the REST-only GitHub backend (spec
`2026-10-07-cloud-triage` §A, plan phase 1, P1.T3.S1).

**Every REST file is one command's stdout, byte for byte.** `index.json` maps
the exact request to its file: the key is the `gh api` route, prefixed with the
`-H` header when one was sent. The command was
`gh api [-H <header>] <route>`. A request that failed is stored as
`*.error.json`: `{exit, stdout, stderr}` exactly as gh gave them, and flagged
`"error": true` in the index. Nothing was subset, re-serialised or edited.

What each group is for:

- the repo, viewer, labels, two `per_page=2` pages of open issues (the
  pagination case), issue 1074 and its comments, the open PRs, open draft PR
  1080 with its files, reviews, check runs, combined status and Actions runs,
  `branches/main`, `rules/branches/main`, an unprotected branch
  (`feat%2Fcloud-triage`), a missing issue (404), `.fr/triage.yaml` at `HEAD`
  (raw), PR 852 found by head branch with its files: the client's reads
  (`tests/unit/test_real_ghrestclient.py`, `test_github_rest_no_graphql.py`);
- `issues/<n>` for every issue in `../triage/super-fr-issues.json` and
  `../triage/dedupe-calibration.json`, `pulls/<n>` for every closed or merged PR
  in `../triage/super-fr-prs.json`, PR 1044 (`../gh/pr-view-adopt.json`), and the
  check runs, status and Actions runs of PR 1038's head `f1919d4`
  (`../triage/super-fr-rerun-checks.json`): the contract test
  (`tests/unit/test_github_rest_contract.py`);
- issue 430's timeline plus the check runs, status and Actions runs of the heads
  of the PRs it names (517, 508): `list_linked_prs`.

Two requests the cloud token is refused, kept because the refusal is the fact:

- `branches/main/protection/required_status_checks` → 403 "Resource not
  accessible by integration" (it needs admin). The client reads the required
  contexts from `branches/{base}`'s `protection` summary and the ruleset rules
  instead.
- `orgs/derio-net/repos` → 403: "sessions are bound to their configured
  repositories". An org scope's repo list cannot be read from the cloud.

`refused/` holds the stderr of the two GraphQL-backed commands the proxy refuses,
captured in the same session (both exited 1, stdout empty):
`gh api graphql -f query='{viewer{login}}'` (`graphql.stderr`) and
`gh pr list --repo derio-net/super-fr --limit 1 --json number`
(`pr-list.stderr`).

Also in `refused/`, from the same session: `label-create-exists.{stdout,stderr}`,
the 422 of `gh api repos/derio-net/super-fr/labels -f name=bug -f color=d73a4a -f
description=x` (exit 1; the label exists, so nothing was written) — what
`ensure_labels` reads as "update it instead". `contents/docs/no-such-path` is the
captured 404 of a missing path.

Captured 2026-10-08 in a later session of the same run (review finding p1-r1):
`label-remove-absent.{stdout,stderr}`, the 404 "Label does not exist" of `gh api
-X DELETE repos/derio-net/super-fr/issues/1074/labels/fr-capture-no-such-label`
(a label the repo does not have, so nothing could be removed), which
`edit_issue_labels` reads as "already absent"; and
`label-remove-missing-issue.{stdout,stderr}`, the plain 404 "Not Found" of the
same DELETE on issue 99999999, which it still raises. Both exited 1.

**The GraphQL side.** The plan asked for the matching GraphQL-backed `gh --json`
outputs "for the same moment" from a host session into `graphql/`. No host
session was available to this capture, so **there is no `graphql/` directory**.
The contract test compares against the GraphQL captures already in the repo
(`../triage/*.json`, `../gh/pr-view-adopt.json`) where they cover the same
records, and says per record why the two moments agree (a closed PR, a finished
commit's check runs filtered to those that existed at the earlier capture, an
issue whose `updated_at` did not move). Nothing here was written by hand to look
like a GraphQL answer.

**Privacy.** Everything is `derio-net`'s own public repo and its members'
public logins; nothing is third-party under
`.claude/rules/third-party-privacy.md`, and nothing was redacted.

## `commit_checks/` — the CI-evidence reads (plan phase 2, P2.T1.S1)

Captured live on **2026-10-08** from a Claude Code cloud session with `gh api`
against `derio-net/super-fr`, one directory per moment. Each holds the stdout,
byte for byte, of the three routes `GhClient.commit_checks` reads, plus `sha`
(the commit) and `captured-at` (UTC):

- `check-runs.json` — `gh api 'repos/derio-net/super-fr/commits/<sha>/check-runs?filter=latest&per_page=100&page=1'`
- `status.json` — `gh api repos/derio-net/super-fr/commits/<sha>/status`
- `actions-runs.json` — `gh api 'repos/derio-net/super-fr/actions/runs?head_sha=<sha>&per_page=100&page=1'`

The moments:

- `green/` — `d9a76e7b`, phase 1's tested head on PR 1088: every check
  completed `success`, `ci-ok` among them; each check run carries the PR with
  its base sha.
- `pending/` — `43956047`, PR 1088's head while its CI was running: seven test
  shards `in_progress` and **no `ci-ok` check run at all** (a job that `needs`
  others gets its check run only when it starts).
- `rerun/` — `f1919d4`, PR 1038's head: CI ran twice (two check suites of the
  `CI` workflow). The first `ci-ok`, two test shards failed and `coverage`
  skipped; the second run is green throughout. `filter=latest` keeps both
  suites' runs; the PR is merged, so `pull_requests` is empty.

- `green-head/` — `b6604451`, PR 1088's head when read, CI green throughout:
  every check run lists the PR with `head.sha` equal to the commit, so the base
  sha is known (`18fa21e1`). Captured 2026-10-08 for review finding p2-r3,
  which found that `green/` is NOT that case: it was read after the PR's head
  had moved on to `pending/`'s commit, so its runs list the PR with that other
  head, and its base is no longer the CI sha's (`base_sha` "", witness
  `unknown`).

Also captured for phase 2's review (p2-r7), in the root index:
`pulls?head=derio-net:feat/cloud-triage&state=open&per_page=100&page=1`, the
open-PR lookup `GhClient.open_pr_for_head` makes (PR 1088, no file list).

No captured commit in this repo carries a commit status (every `status.json`
has `"statuses": []`): the status-context tests derive their entries from the
captured envelope and say so.
