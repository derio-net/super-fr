# Journal: 2026-10-07-cloud-triage

<!-- fr:journal kind=discovery scope=plan id=p1-ci-pull-request-only created=2026-10-08T13:58:42+00:00 phase=1 -->
### p1-ci-pull-request-only · discovery · CI runs only on pull_request, so P1.T1's "CI green on the branch" cannot be observed before the PR (phase 1)

`.github/workflows/ci.yml` triggers on `push: branches: [main]` and `pull_request` only (#941), so a
push of `feat/cloud-triage` starts no run (confirmed: `actions/runs?head_sha=` empty after the push).
The executor never opens a PR. What T1 could prove ran: the skeleton test passes and
`scripts/check-change-fragment.py origin/main` passes; CI-green is owed to the orchestrator's PR.

<!-- fr:journal kind=discovery scope=plan id=p1-graphql-fixtures-not-same-moment created=2026-10-08T13:58:42+00:00 phase=1 -->
### p1-graphql-fixtures-not-same-moment · discovery · No host session to capture GraphQL; the contract test compares against the repo's existing GraphQL captures (phase 1)

P1.T3.S1 asked for GraphQL `gh --json` captures of the same moment from a host session into
`tests/fixtures/github_rest/graphql/`. None was available (this is a cloud session; GraphQL is 403),
so no `graphql/` directory exists and nothing was written to look like one. The contract test
(`tests/unit/test_github_rest_contract.py`) compares the REST capture against GraphQL captures already
in the repo, narrowing each comparison to where the two moments agree:
`triage/super-fr-prs.json` (11 closed/merged PRs, every field incl. closingIssuesReferences),
`triage/super-fr-rerun-checks.json` (PR 1038 head f1919d4: all 35 check runs field for field incl.
workflowName, the one later post-merge run filtered by date), `gh/pr-view-adopt.json` (PR 1044),
`triage/super-fr-issues.json` (issue 477 unchanged since capture compared whole; the 11 updated since
compared on immutable fields, only updatedAt/labels allowed to differ), `triage/dedupe-calibration.json`
(title/body; state only where closed on/after the capture day), `triage/super-fr-open-prs.json`
(CONFLICTING/DIRTY enum, different PR). Comments have no GraphQL capture in the repo: list_issue_comments
is tested against REST only. A host-session capture would let a later phase tighten this.

<!-- fr:journal kind=discovery scope=plan id=p1-required-checks-route-refused created=2026-10-08T13:58:42+00:00 phase=1 -->
### p1-required-checks-route-refused · discovery · §A's required-checks route is 403 from the cloud token; required contexts are read from branches/{base} and rulesets (phase 1)

Captured: `GET repos/derio-net/super-fr/branches/main/protection/required_status_checks` → 403
"Resource not accessible by integration" (needs admin). `GET branches/{base}` carries a readable
`protection.required_status_checks` summary, and `GET rules/branches/{base}` the ruleset rules;
`pr_required_checks` unions the two. The spec's §A row should name these routes.

<!-- fr:journal kind=decision scope=plan id=p1-ready-via-ccr-route created=2026-10-08T13:58:42+00:00 phase=1 -->
### p1-ready-via-ccr-route · decision · github-rest `ready` uses the cloud proxy's CCR route: GitHub REST has no ready-for-review (phase 1)

The plan spelled `ready` as "the REST PATCH that clears draft". GitHub's REST update-a-pull-request
endpoint documents no `draft` parameter (ready-for-review is the GraphQL mutation
markPullRequestReadyForReview), so that PATCH would report success and change nothing. The cloud
proxy's own 403 text (captured, `tests/fixtures/github_rest/refused/`) names the route it offers:
`POST /repos/{owner}/{repo}/pulls/{n}/ccr/ready_for_review`. `FORGE_COMMANDS["github-rest"]["ready"]`
uses it. It exists only behind a Claude Code cloud session's proxy, which is where `forge.api: rest`
is selected; not live-exercised here (it would flip a real PR). The spec's §A should say so.

<!-- fr:journal kind=decision scope=plan id=p1-soft-none-methods created=2026-10-08T13:58:42+00:00 phase=1 -->
### p1-soft-none-methods · decision · The REST client's None-on-failure set is the four methods whose GhClient contract says so, not two (phase 1)

The plan named `pr_for_branch` and `issues_enabled`; the spec's rule is "a method whose GhClient
contract answers None when the forge cannot say keeps that contract". The Protocol says the same of
`default_branch` ("never raises for a CLI failure") and `pr_status_by_url` ("None on any
not-found/error condition"), so all four answer None; every other method raises GhError on a 403
(asserted for all 36 methods). `file_exists`/`list_dir` read a 404 as absent and raise anything else.
A host trust refusal is never softened.

<!-- fr:journal kind=discovery scope=plan id=p1-list-repos-refused-in-cloud created=2026-10-08T13:58:42+00:00 phase=1 -->
### p1-list-repos-refused-in-cloud · discovery · An org's repo list is refused from a cloud session: sessions are bound to their configured repositories (phase 1)

Captured: `GET orgs/derio-net/repos` → 403 "This GitHub API path is not available: sessions are
bound to their configured repositories. Use repository-scoped endpoints". `list_repos` raises it
(never []). A cloud scope over an org (R7) cannot enumerate repos from the forge; the phases that
build cloud scopes must take the repo list from the scope itself.

<!-- fr:journal kind=discovery scope=plan id=p1-r2-gaps-beyond-the-field-map created=2026-10-08T13:58:42+00:00 phase=1 -->
### p1-r2-gaps-beyond-the-field-map · discovery · REST gaps not in §A's table: closing-ref node ids, viewerDefaultMergeMethod, author name, REVIEW_REQUIRED (phase 1)

Found building the field map (R2 says every such field is listed): (1) closingIssuesReferences' GraphQL
node ids (`id`, `repository.id`, `owner.id`) are not produced — collect reads none; (2) REST has no
`viewerDefaultMergeMethod`, so `repo_merge_methods` answers `default: None`, and `choose_method`
refuses a repo allowing several methods unless `--method` is given (super-fr allows all three) — the
cloud driver's merge needs an explicit method; (3) `author.name` is absent from REST list records;
(4) `reviewDecision` derives from reviews only, never GraphQL's REVIEW_REQUIRED. Each is stated in the
helper's docstring; the spec's §A table should list them.

<!-- fr:journal kind=discovery scope=plan id=p1-tdd-red-shown-by-mutation created=2026-10-08T13:58:42+00:00 phase=1 -->
### p1-tdd-red-shown-by-mutation · discovery · T4's RED and T6's field-map RED were shown by mutation, not observed first (phase 1)

The writes were written into real_ghrestclient.py with T3's reads, so P1.T4.S1's tests passed on first
run; removing the writes made 7 of them fail. The contract test's first failure was a test-shape issue
(comparing records with fields the older GraphQL capture never asked for), not the field map, which
held; dropping workflowName mapping and conclusion upper-casing made 2 contract tests fail.

<!-- fr:journal kind=decision scope=plan id=p1-test-suite-pins-graphql created=2026-10-08T13:58:42+00:00 phase=1 -->
### p1-test-suite-pins-graphql · decision · tests/conftest.py pins FR_FORGE_API=graphql for every test (phase 1)

A suite run in a cloud session whose ~/.config/fr/forge.yaml says `rest` would otherwise hand every
GitHub test the REST client. The env var outranks the file; the tests of the setting delete it.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-10-08T13:58:42+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

forgeapi.py is four small functions written to the spec's shape at GREEN (resolve, write_default, config_path, one validator); nothing duplicated to extract.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-08T13:58:42+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the writes reuse T3's one `_api` transport and its field helpers; no duplication was introduced, so nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-08T13:58:42+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

each seam gained a single `forgeapi.resolve()` check delegating to the REST client, and the github-rest command table is data; nothing to consolidate.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-10-08T13:58:42+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

the field map held on the contract test's first run (its discrimination shown by mutation), so no fix was made and nothing needed cleaning.
