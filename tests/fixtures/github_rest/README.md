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
