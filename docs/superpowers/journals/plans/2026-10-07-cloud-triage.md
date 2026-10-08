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

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-08T14:18:11+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · edit_issue_labels removal DELETEs a label not on the issue -> 404 GhError; GraphQL path is idempotent (phase 1)

real_ghrestclient.py ~737; callers tracker/github.py:110-112 and triage/claim_writes.py:61 break under rest.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-08T14:18:11+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · edit_issue_state sends reason.lower() verbatim; 'not planned' -> 422 (phase 1)

real_ghrestclient.py ~746; undispatch_cmd.py:120.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-08T14:18:11+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · _closing_refs lacks a leading word boundary and a host check; code fences not excluded (phase 1)

real_ghrestclient.py:47-55: 'prefixes #3', 'unresolved #5' and non-GitHub issue URLs became closing refs; refs hard-coded to github.com.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-08T14:18:11+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · list_linked_prs fetches pulls/{n} for every cross-referencing PR (phase 1)

real_ghrestclient.py:470-482: the timeline carries title/body/state; extra calls, and a 403 on a non-closing cross-repo mention failed the call.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-10-08T14:18:11+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · repo_merge_methods always default None, so choose_method refuses merge/drive on multi-method repos under rest (phase 1)

real_ghrestclient.py:663-672; triage/batch_merge.py:157-164; super-fr allows all three.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-10-08T14:18:11+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · spec §A not amended for the gaps phase 1 found (phase 1)

required-checks 403 route still named; CCR ready, viewerDefaultMergeMethod, author.name, REVIEW_REQUIRED, node ids, org repo listing unlisted though R2 requires each.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-10-08T14:18:11+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · the shell-execution test passed edit-by-branch without its head lookup running; branch not URL-encoded (phase 1)

test_github_rest_no_graphql.py:213-226; hostclient.py:205-206.

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-10-08T14:18:11+00:00 phase=1 state=open review_scope=in -->
### p1-r8 · finding [open] (reviewer: in scope) · pr_required_checks matching logic untested (phase 1)

only the nothing-required case was exercised (test_real_ghrestclient.py:174-181).

<!-- fr:journal kind=finding scope=plan id=p1-r9 created=2026-10-08T14:18:11+00:00 phase=1 state=open review_scope=in -->
### p1-r9 · finding [open] (reviewer: in scope) · acceptance row cloud-triage-github-rest not updated with phase 1's unit evidence (phase 1)

matrix.yaml:5045-5046 levels {}.

<!-- fr:journal kind=finding scope=plan id=p1-r10 created=2026-10-08T14:18:11+00:00 phase=1 state=open review_scope=in -->
### p1-r10 · finding [open] (reviewer: in scope) · _project silently yields None for fields REST records lack (phase 1)

real_ghrestclient.py:325-326; gh --json fails on an unknown field.

<!-- fr:journal kind=finding scope=plan id=p1-r11 created=2026-10-08T14:18:11+00:00 phase=1 state=open review_scope=out -->
### p1-r11 · finding [open] (reviewer: out of scope) · tracker/github.py:114 passes state='closed' in lower case; both clients accept only OPEN/CLOSED (phase 1)

Found by the fix agent while fixing p1-r1. Pre-existing on main (RealGhClient raises ValueError the same way), so moving a tracker item to done fails on either backend; not caused by this change.

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-10-08T14:18:11+00:00 phase=1 -->
### p1-review · review · phase 1 code review: 10 findings in scope, 1 out (phase 1)

Dispatched reviewer (superpowers:requesting-code-review discipline) over 2cd15337..d9a76e7b against spec R1-R3/§A and plan 01.yaml; read-only, targeted checks only (CI ran the full suite green on d9a76e7b). Raised p1-r1..p1-r10, all in scope. Received (superpowers:receiving-code-review): each verified against the code; p1-r6 fixed in the spec (0686d3ff), p1-r9 by fr acceptance set-status (ae2e5856), the rest by a fix agent with a failing test first (217df288, 6d903f73, 18e87557, 628bf447, 2e539e87, 2257ee33, 4e1571d9, ec1e980a); 2115 targeted tests pass, ruff and mypy clean. p1-r11 surfaced while fixing, out of scope. p1-r5's new .fr/triage.yaml merge_method key is documented in the fr-triage skill by phase 7 (R21).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-08T14:18:11+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: edit_issue_labels removal DELETEs a label not on the issue -> 404 GhError; GraphQL path is idempotent (phase 1)

217df288: a 'Label does not exist' 404 is success, any other 404 raises; captured fixtures; test_removing_a_label_the_issue_does_not_carry_is_success.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-08T14:18:11+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: edit_issue_state sends reason.lower() verbatim; 'not planned' -> 422 (phase 1)

217df288: reasons mapped to completed/not_planned/reopened, unknown refused before any call; test_close_reason_is_sent_in_githubs_spelling.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-08T14:18:11+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: _closing_refs lacks a leading word boundary and a host check; code fences not excluded (phase 1)

6d903f73: word boundary, fenced/inline code skipped (fr.record.pr_body's reader), issue URLs on the repo's own host only, refs built on that host; test_a_non_closing_mention_is_not_a_ref.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-08T14:18:11+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: list_linked_prs fetches pulls/{n} for every cross-referencing PR (phase 1)

18e87557: timeline fields used; pulls/{n} fetched only for closing PRs; test_list_linked_prs_fetches_pulls_only_for_closing_prs.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-10-08T14:18:11+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: repo_merge_methods always default None, so choose_method refuses merge/drive on multi-method repos under rest (phase 1)

628bf447 plus spec §A (0686d3ff): optional merge_method in .fr/triage.yaml, used when the forge names no default; refusal names the key; facts.json schema 7 -> 8 with 3-7 still read.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-10-08T14:18:11+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: spec §A not amended for the gaps phase 1 found (phase 1)

0686d3ff: §A lists every gap and the branches/{base} + rules/branches/{base} required-checks routes, plus the closing-ref, label-removal and state_reason rules.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-10-08T14:18:11+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: the shell-execution test passed edit-by-branch without its head lookup running; branch not URL-encoded (phase 1)

2e539e87: the shell test uses a captured head lookup and asserts the PATCH went to pulls/852; branch URL-encoded.

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-10-08T14:18:11+00:00 phase=1 state=fixed resolves=p1-r8 -->
### p1-r8-resolved · finding [fixed] · resolves p1-r8: pr_required_checks matching logic untested (phase 1)

2257ee33: test_pr_required_checks_matches_runs_by_name_and_statuses_by_context (captured JSON with required lists filled in, said in its docstring).

<!-- fr:journal kind=finding scope=plan id=p1-r9-resolved created=2026-10-08T14:18:11+00:00 phase=1 state=fixed resolves=p1-r9 -->
### p1-r9-resolved · finding [fixed] · resolves p1-r9: acceptance row cloud-triage-github-rest not updated with phase 1's unit evidence (phase 1)

ae2e5856: three unit level refs added; status stays not-implemented until Test Plan 16's client-live walk.

<!-- fr:journal kind=finding scope=plan id=p1-r10-resolved created=2026-10-08T14:18:11+00:00 phase=1 state=fixed resolves=p1-r10 -->
### p1-r10-resolved · finding [fixed] · resolves p1-r10: _project silently yields None for fields REST records lack (phase 1)

4e1571d9: _project raises GhError on an unknown field; every field set fr requests is tested.

<!-- fr:journal kind=finding scope=plan id=p1-r11-resolved created=2026-10-08T14:18:11+00:00 phase=1 state=open resolves=p1-r11 out_of_scope=true -->
### p1-r11-resolved · finding [out-of-scope] · resolves p1-r11: tracker/github.py:114 passes state='closed' in lower case; both clients accept only OPEN/CLOSED (phase 1)

Pre-existing on main: tracker/github.py:114's lower-case state fails on both backends; this change did not cause it and does not touch that path.

<!-- fr:journal kind=decision scope=plan id=p2-commit-checks-base-sha created=2026-10-08T14:38:52+00:00 phase=2 -->
### p2-commit-checks-base-sha · decision · commit_checks records carry base_sha beside the plan's five fields (phase 2)

The witness needs the base sha "from the gate's check suite", so each record also carries
`base_sha`: the base of the PR whose head is the sha in the check run's `pull_requests`
(else the suite's Actions run's), "" for a status context or a run naming no PR (a merged
PR's runs name none: the captured f1919d4 re-run). It is the PR base GitHub reports when
the checks are READ, not provably the base at run time; verify_ci writes `unknown` when no
gate record names one.

<!-- fr:journal kind=discovery scope=plan id=p2-gate-absent-while-running created=2026-10-08T14:38:52+00:00 phase=2 -->
### p2-gate-absent-while-running · discovery · ci-ok has no check run until its needs finish, so a missing gate mid-run is pending, not absent (phase 2)

Captured on PR 1088's head 43956047 while CI ran (tests/fixtures/github_rest/commit_checks/pending):
seven test shards in_progress and no ci-ok check run at all — a job that `needs` others is
created only when it starts. Read literally, §I step 5 ("absent -> exit 2") would refuse every
resolve made while CI runs. verify_ci reads a gate missing from every same-tree commit as
pending (75) while any check on HEAD is unfinished or HEAD has none yet, and as absent
(exit 2) only once every check on it finished. The spec's §I step 5 should say so.

<!-- fr:journal kind=discovery scope=plan id=p2-required-checks-only-reported created=2026-10-08T14:38:52+00:00 phase=2 -->
### p2-required-checks-only-reported · discovery · Without .fr/ci.yaml, a required gate that never reported cannot be named absent (phase 2)

`pr_required_checks` (both backends) returns the required checks that RAN on the head, not
the required names, so with no `.fr/ci.yaml` the gate set is "required checks reported so
far": an empty answer reads as no gates declared (exit 2, naming both ways), and a required
check that never ran is not seen. This repo ships `.fr/ci.yaml` (`gate_checks: [ci-ok]`),
which avoids it; a repo relying on required checks would want a required-names read.

<!-- fr:journal kind=discovery scope=plan id=p2-no-commit-statuses-captured created=2026-10-08T14:38:52+00:00 phase=2 -->
### p2-no-commit-statuses-captured · discovery · No commit in super-fr carries a commit status; the status-context test is derived (phase 2)

Every captured `commits/{sha}/status` has `"statuses": []` (all CI here is check runs), so
test_commit_checks.py's status-context case adds entries to the captured envelope and says
so in its docstring. Failed/skipped/cancelled/in-progress gates in test_run_ci_evidence.py
are likewise derived from the captured green head; pending-with-no-gate, the re-run and
green are captured as they were.

<!-- fr:journal kind=discovery scope=plan id=p2-explainer-html-owed created=2026-10-08T14:38:52+00:00 phase=2 -->
### p2-explainer-html-owed · discovery · 01-fr-goal.md describes tests ci; its .html regeneration is owed (phase 2)

docs/explainers/01-fr-goal.md said delivery names a local test log only; a paragraph now
describes CI evidence. The blog-craft renderer (`derio-net--blog-craft` marketplace) is not
installed in this cloud container, so docs/explainers/01-fr-goal.html was NOT regenerated:
the published page lags until someone renders it per .claude/rules/explainers-currency.md.
The heading tripwire passes (no heading changed).

<!-- fr:journal kind=decision scope=plan id=p2-scenario-fake-gh-rest created=2026-10-08T14:38:52+00:00 phase=2 -->
### p2-scenario-fake-gh-rest · decision · The ci-evidence scenario drives the github-rest client against a fake gh of captured stdout (phase 2)

tests/scenarios/cloud-triage-ci-evidence.sh sets FR_FORGE_API=rest so every forge read is a
`gh api <route>` its fake gh (tests/scenarios/fixtures/ci-evidence/bin/gh) answers from
captures: PR 1088 by head and by number (captured this phase), the commit_checks moments,
and PR 852's captured files page standing in for 1088's (1.1 MB; verify_ci reads no file).
The run is a one-step repo workflow `verify` with `evidence: [tests]`; origin is a bare
repo at ../derio-net/super-fr.git so the slug and `git ls-remote` are real.

<!-- fr:journal kind=discovery scope=plan id=p2-ci-pending-exit-through-record created=2026-10-08T14:38:52+00:00 phase=2 -->
### p2-ci-pending-exit-through-record · discovery · A pending gate through --record restores every byte, the record file included (phase 2)

`apply_record` already restores every write on any typer.Exit, so exit 75 needed no new
path: the cursor and the record are byte-identical afterwards (pinned in
test_run_resolve_tests_ci.py and the scenario).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-10-08T14:38:52+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

commit_checks is one pure helper that reuses _rollup (workflow names) and collect._latest_runs (latest per check) plus a three-route method; RealGhClient delegates to it, so nothing was duplicated to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-10-08T14:38:52+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

the only cleanup was folding a one-use _Pr dataclass into an int during GREEN; the six steps are already one small function each.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-10-08T14:38:52+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

the routing is one branch plus one helper beside the existing witness helpers; nothing to consolidate.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-10-08T14:38:52+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

prose and mirrors only; the mirrors are generated.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-08T14:58:28+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · required-checks fallback used only checks already reported: a not-yet-created required gate was skipped, none reported refused instead of pending (phase 2)

ci_evidence.py:158-169; real_ghrestclient.py:700-715.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-08T14:58:28+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · gate_checks read from HEAD's .fr/ci.yaml let the branch under test choose a weaker gate (phase 2)

ci_evidence.py:70.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-10-08T14:58:28+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · witness base sha fell back to the first-listed PR, so ci:<sha>+<base> could name a merge CI never tested (phase 2)

real_ghrestclient.py:323-332; the captured green fixture showed the mismatch.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-10-08T14:58:28+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · a failed gate with a re-run in flight refused instead of pending (phase 2)

ci_evidence.py:235-248.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-10-08T14:58:28+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · HEAD with zero checks was pending forever (phase 2)

ci_evidence.py:227.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-10-08T14:58:28+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · pending output named no URL though fr-goal says to report the gate's URL (phase 2)

ci_evidence.py:228,248.

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-10-08T14:58:28+00:00 phase=2 state=open review_scope=in -->
### p2-r7 · finding [open] (reviewer: in scope) · the open-PR lookup fetched every file page of every PR on each resolve and retry (phase 2)

real_ghrestclient.py:663-669 via list_prs_by_head(state=all).

<!-- fr:journal kind=finding scope=plan id=p2-r8 created=2026-10-08T14:58:28+00:00 phase=2 state=open review_scope=in -->
### p2-r8 · finding [open] (reviewer: in scope) · PR body rendered a ci witness as 'Full suite run at delivery'; the missing-tests hint offered only a log (phase 2)

pr_body.py:567; run_cmd.py:1656.

<!-- fr:journal kind=finding scope=plan id=p2-r9 created=2026-10-08T14:58:28+00:00 phase=2 state=open review_scope=in -->
### p2-r9 · finding [open] (reviewer: in scope) · 01-fr-goal.html not regenerated after the .md change (phase 2)

explainers-currency.

<!-- fr:journal kind=finding scope=plan id=p2-r10 created=2026-10-08T14:58:28+00:00 phase=2 state=open review_scope=in -->
### p2-r10 · finding [open] (reviewer: in scope) · no tests for WALK_LIMIT, a reverted code change, a failed gate during a re-run, a partial required set (phase 2)

tests/unit/test_run_ci_evidence.py.

<!-- fr:journal kind=review scope=plan id=p2-review created=2026-10-08T14:58:28+00:00 phase=2 -->
### p2-review · review · phase 2 code review: 10 findings in scope (phase 2)

Dispatched reviewer (superpowers:requesting-code-review discipline) over 39a1efb9..bc1f170 against spec R22/§I/Test Plan 19 and plan 02.yaml; read-only, 65 targeted tests run. Raised p2-r1..p2-r10, all in scope. Received (superpowers:receiving-code-review): each verified against the code; the spec decided p2-r1..r8 (b6604451: gate union with the base, names-only required checks, re-run and no-CI waits, honest base, URLs, files-free lookup, PR body wording); a fix agent implemented them with a failing test first (60ae306c, 0bae3530, 31817d45; 203 targeted + scenario pass, ruff/mypy clean); p2-r9 regenerated with blog-craft's renderer after a byte-identical re-render of main's page (adc20d1a).

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-08T14:58:28+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: required-checks fallback used only checks already reported: a not-yet-created required gate was skipped, none reported refused instead of pending (phase 2)

60ae306c + 0bae3530: required_check_names(repo, base) reads names whether or not reported; unreported required gates are pending; test_a_partially_reported_required_set_is_pending.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-08T14:58:28+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: gate_checks read from HEAD's .fr/ci.yaml let the branch under test choose a weaker gate (phase 2)

b6604451 (spec) + 0bae3530: gates are the union of .fr/ci.yaml at origin/<base> and HEAD; test_a_branch_cannot_drop_a_gate_its_base_declares.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-10-08T14:58:28+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: witness base sha fell back to the first-listed PR, so ci:<sha>+<base> could name a merge CI never tested (phase 2)

60ae306c: base only from a suite whose PR head is the CI sha, else unknown; fresh green-head capture; test_a_run_whose_pr_moved_on_witnesses_an_unknown_base.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-10-08T14:58:28+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: a failed gate with a re-run in flight refused instead of pending (phase 2)

0bae3530: a failed gate is pending while its own workflow runs; test_a_failed_gate_while_its_workflow_re_runs_is_pending.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-10-08T14:58:28+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: HEAD with zero checks was pending forever (phase 2)

0bae3530: no checks anywhere -> pending for 15 minutes after HEAD's committer time, then 'no CI ran'; test_no_check_fifteen_minutes_on_is_refused.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-10-08T14:58:28+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: pending output named no URL though fr-goal says to report the gate's URL (phase 2)

0bae3530: pending names each unfinished check's URL or the PR's checks page; test_pending_names_each_unfinished_checks_url.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-10-08T14:58:28+00:00 phase=2 state=fixed resolves=p2-r7 -->
### p2-r7-resolved · finding [fixed] · resolves p2-r7: the open-PR lookup fetched every file page of every PR on each resolve and retry (phase 2)

60ae306c + 0bae3530: open_pr_for_head makes one pulls?head=&state=open call, no files; test_the_open_pr_lookup_reads_no_files.

<!-- fr:journal kind=finding scope=plan id=p2-r8-resolved created=2026-10-08T14:58:28+00:00 phase=2 state=fixed resolves=p2-r8 -->
### p2-r8-resolved · finding [fixed] · resolves p2-r8: PR body rendered a ci witness as 'Full suite run at delivery'; the missing-tests hint offered only a log (phase 2)

31817d45: ci witness rendered as 'CI (<gates>) green on <sha> merged with <base>'; hint offers tests=ci where a CI is configured.

<!-- fr:journal kind=finding scope=plan id=p2-r9-resolved created=2026-10-08T14:58:28+00:00 phase=2 state=fixed resolves=p2-r9 -->
### p2-r9-resolved · finding [fixed] · resolves p2-r9: 01-fr-goal.html not regenerated after the .md change (phase 2)

adc20d1a: regenerated with blog-craft tools/render_explainer.py; main's unmodified .md re-rendered byte-identical first; tripwire passes.

<!-- fr:journal kind=finding scope=plan id=p2-r10-resolved created=2026-10-08T14:58:28+00:00 phase=2 state=fixed resolves=p2-r10 -->
### p2-r10-resolved · finding [fixed] · resolves p2-r10: no tests for WALK_LIMIT, a reverted code change, a failed gate during a re-run, a partial required set (phase 2)

0bae3530: WALK_LIMIT, revert, re-run and partial-set tests added.

<!-- fr:journal kind=discovery scope=plan id=p3-default-state-dir-moved created=2026-10-08T15:33:48+00:00 phase=3 -->
### p3-default-state-dir-moved · discovery · The default triage state dir is now the working directory's clone; outside one, every triage command needs --workspace or --dir (phase 3)

R4 moves state from ~/.cache/fr/triage/<scope>/ to <workspace>/.fr/triage-state/<scope>/.
An org triage typed in $HOME (no clone) used to work and now exits 2 naming --workspace,
for every scope kind (the spec says "required for an org or group scope", but a repo
scope outside a clone has no workspace either). The old cache is imported once, on the
first resolve that finds no workspace dir. Board commands copied into another pane now
carry --workspace <toplevel>, because the default follows the pane's cwd.

<!-- fr:journal kind=decision scope=plan id=p3-state-push-fetch-cli created=2026-10-08T15:33:48+00:00 phase=3 -->
### p3-state-push-fetch-cli · decision · fr triage state push|fetch drive the ref from the CLI; the CAS base is <state>/.state-ref (phase 3)

The plan names push_state/fetch_state but no verb; the candidate scenario needs one, so
`fr triage state push [--remote]` and `fetch [--remote] [--state-repo]` were added
(default remote https://github.com/<state_repo>.git). Every fetch and push writes the
sha it left the ref at to <state>/.state-ref (not a REF_FILES entry, so it never rides
on the ref or an export); `state push` uses it as expected_old. Phase 4's drive pass can
use the same file.

<!-- fr:journal kind=decision scope=plan id=p3-privacy-unknown-is-private created=2026-10-08T15:33:48+00:00 phase=3 -->
### p3-privacy-unknown-is-private · decision · The privacy guard counts an unreadable key repo as private and also reads origins and pattern keys (phase 3)

A key's repo whose visibility neither facts nor the forge can give is treated as not
public, so it is refused toward a public state repo (never let an unknown through). A
key naming no repo of the scope (check's orphan) has no repo to read and is skipped.
guard_state reads judged issues, batch and pattern members, and origins.yaml's issues,
since origins.yaml rides on the ref too. The write guard lives in the batch verbs'
_save, the one path every engine judgements write takes (create, edit --add-issue, the
wave setters, the driver's and claim's writes); added_keys counts every member of a
batch whose wave was set or moved.

<!-- fr:journal kind=decision scope=plan id=p3-forge-api-not-recorded-at-decision created=2026-10-08T15:33:48+00:00 phase=3 -->
### p3-forge-api-not-recorded-at-decision · decision · The first collect records only state_repo; forge_api is left for whoever configures the driver (phase 3)

Recording the host's resolved forge.api (graphql on a host) in scope-durable.yaml would
restore graphql onto a cloud container whose forge.yaml is missing. So the decision
writes state_repo only and keeps an existing forge_api; phase 4's driver start (R11)
is where forge_api: rest is set.

<!-- fr:journal kind=discovery scope=plan id=p3-facts-visibility-on-schema-8 created=2026-10-08T15:33:48+00:00 phase=3 -->
### p3-facts-visibility-on-schema-8 · discovery · facts.json's visibility map rides on the unreleased schema 8; no second bump (phase 3)

Schema 8 (phase 1's per-config merge_method) has not been released, so the new
`visibility` key joins it and FACTS_SCHEMA stays 8. The two claims scenario fixtures
were regenerated by make_claims_facts.py (they now carry "visibility": {}).
GhClient gained repo_visibility (REST GET repos/{r}; GraphQL gh repo view --json
visibility; glab/tea unsupported), and the Forge protocol and its fakes with it.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-10-08T15:33:48+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

state_dir's three duties (workspace, exclude, import) are one short function over two gitseam helpers; the --workspace option was threaded through one shared resolve_state_dir, so nothing was duplicated to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-10-08T15:33:48+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

state_ref is four small functions over five gitseam primitives written once; the only shared need (walking a directory without following symlinks) reuses state_sync._walk

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-10-08T15:33:48+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

the decision is one pure function and collect's call is one helper beside collect_into; ScopeDurable and ScopeConfig share their fields by design (the mirror), not by copy

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-10-08T16:05:37+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · R5 half done: no host write path fetched before reading or pushed the ref after a change (phase 3)

push_state/fetch_state reached only from state push|fetch (triage_state_cmd.py:118-166).

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-10-08T16:05:37+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · legacy import copytreed the whole ~/.cache dir (merge/ worktrees, drive.lock, pages) (phase 3)

model.py:211.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-10-08T16:05:37+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · state dir followed cwd's clone: per-clone forks, drive.lock no longer same-host, repo scopes outside a clone exited 2 (phase 3)

model.py:181-212; triage_batch_cmd.py:2026-2037.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-10-08T16:05:37+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · .state-ref not tied to its remote; fetch overwrote unpushed edits and kept dropped files (phase 3)

state_ref.py:160,215.

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-10-08T16:05:37+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · fetch_ref ran ls-remote then a separate fetch (phase 3)

gitseam.py:191-198.

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-10-08T16:05:37+00:00 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · a test wrote the real ~/.config/fr/forge.yaml (HOME not isolated) (phase 3)

test_fetch_into_a_fresh_clone_restores_every_entry_byte_for_byte via apply_durable.

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-10-08T16:05:37+00:00 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · _settle_state_repo ran in every drive and watch loop collect, prompting each pass (phase 3)

triage_cmd.py:271,292.

<!-- fr:journal kind=finding scope=plan id=p3-r8 created=2026-10-08T16:05:37+00:00 phase=3 state=open review_scope=in -->
### p3-r8 · finding [open] (reviewer: in scope) · privacy guard skipped keys naming no repo of the scope (phase 3)

privacy.py:114-116.

<!-- fr:journal kind=finding scope=plan id=p3-r9 created=2026-10-08T16:05:37+00:00 phase=3 state=open review_scope=in -->
### p3-r9 · finding [open] (reviewer: in scope) · collect made one GET repos/{r} per repo every pass though the repo list carries visibility (phase 3)

collect.py:450-460,642; real_ghrestclient.py:860.

<!-- fr:journal kind=finding scope=plan id=p3-r10 created=2026-10-08T16:05:37+00:00 phase=3 state=open review_scope=in -->
### p3-r10 · finding [open] (reviewer: in scope) · stale ~/.cache/fr/triage paths in fr skills output, triage_cmd docstring, fr-origins/fr-audit skills, docs/triage/README.md (phase 3)

skills_cmd.py:54 and others.

<!-- fr:journal kind=finding scope=plan id=p3-r11 created=2026-10-08T16:05:37+00:00 phase=3 state=open review_scope=in -->
### p3-r11 · finding [open] (reviewer: in scope) · privacy-guard scenario claimed a private-state-repo create it did not test; row moved to ci without the owed lease-push part (phase 3)

cloud-triage-privacy-guard.sh:7.

<!-- fr:journal kind=finding scope=plan id=p3-r12 created=2026-10-08T16:05:37+00:00 phase=3 state=open review_scope=in -->
### p3-r12 · finding [open] (reviewer: in scope) · ref files restored 0600 and committed 100644, losing executable modes (phase 3)

state_ref.py:135-147; gitseam commit_tree_from_paths.

<!-- fr:journal kind=review scope=plan id=p3-review created=2026-10-08T16:05:37+00:00 phase=3 -->
### p3-review · review · phase 3 code review: 12 findings in scope (phase 3)

Dispatched reviewer (superpowers:requesting-code-review discipline) over 0c04ad8e..527f33a7 against spec R4-R8/§B/§C/Test Plan 4-7 and plan 03.yaml; 148 targeted tests run. Raised p3-r1..p3-r12, all in scope; it also judged the executor's two departures (state push|fetch verbs accepted; exit 2 outside a clone a host regression -> p3-r3). Received (superpowers:receiving-code-review): each verified; the spec decided r1-r4, r7-r9, r12 (22675eea: legacy dir outside a clone, durable-only import, one ref-wrapping wrapper, .state-ref per remote, settle only on explicit collect, foreign keys read); a fix agent implemented all twelve with a failing test first (f749bf6c, c47c1abd, b9408eec, f60ed8a5, d9290a87, dde24616, 0a39e97a); 2839 targeted tests and 3 cloud-triage scenarios pass; ruff, mypy and fr acceptance check clean.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-10-08T16:05:37+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: R5 half done: no host write path fetched before reading or pushed the ref after a change (phase 3)

f749bf6c: resolve_state_dir is the one wrapper: fetch before, push after a ref-file change, conflict refuses with RETRY_LINE; test_triage_state_ref_sync.py.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-10-08T16:05:37+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: legacy import copytreed the whole ~/.cache dir (merge/ worktrees, drive.lock, pages) (phase 3)

f749bf6c: import_legacy copies REF_FILES that exist plus facts.json and scope.yaml; test_the_import_copies_only_the_durable_files.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-10-08T16:05:37+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: state dir followed cwd's clone: per-clone forks, drive.lock no longer same-host, repo scopes outside a clone exited 2 (phase 3)

f749bf6c: legacy ~/.cache dir outside a clone for every scope kind; drive.lock in ~/.cache per scope; test_the_drive_lock_lives_in_the_home_cache_whatever_the_workspace.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-10-08T16:05:37+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: .state-ref not tied to its remote; fetch overwrote unpushed edits and kept dropped files (phase 3)

c47c1abd: .state-ref JSON with remote and ref; foreign or vanished base discarded; fetch refuses over unpushed changes and removes dropped files.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-10-08T16:05:37+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: fetch_ref ran ls-remote then a separate fetch (phase 3)

c47c1abd: fetch_ref fetches then rev-parses the local ref; test_fetch_ref_fetches_first_and_never_asks_ls_remote.

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-10-08T16:05:37+00:00 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: a test wrote the real ~/.config/fr/forge.yaml (HOME not isolated) (phase 3)

b9408eec: autouse tmp HOME for every test; test_writing_the_forge_default_never_touches_the_operators_file.

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-10-08T16:05:37+00:00 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: _settle_state_repo ran in every drive and watch loop collect, prompting each pass (phase 3)

f749bf6c + f60ed8a5: collect_into(settle=False) by default, only fr triage collect settles; loops warn once per pass.

<!-- fr:journal kind=finding scope=plan id=p3-r8-resolved created=2026-10-08T16:05:37+00:00 phase=3 state=fixed resolves=p3-r8 -->
### p3-r8-resolved · finding [fixed] · resolves p3-r8: privacy guard skipped keys naming no repo of the scope (phase 3)

f60ed8a5: keys outside the scope have their repo read; unnameable or unreadable counts as private.

<!-- fr:journal kind=finding scope=plan id=p3-r9-resolved created=2026-10-08T16:05:37+00:00 phase=3 state=fixed resolves=p3-r9 -->
### p3-r9-resolved · finding [fixed] · resolves p3-r9: collect made one GET repos/{r} per repo every pass though the repo list carries visibility (phase 3)

f60ed8a5: visibility from the repo list (both backends); one GET only for repos the list omits.

<!-- fr:journal kind=finding scope=plan id=p3-r10-resolved created=2026-10-08T16:05:37+00:00 phase=3 state=fixed resolves=p3-r10 -->
### p3-r10-resolved · finding [fixed] · resolves p3-r10: stale ~/.cache/fr/triage paths in fr skills output, triage_cmd docstring, fr-origins/fr-audit skills, docs/triage/README.md (phase 3)

d9290a87: stale paths corrected in skills_cmd, triage_cmd, fr-origins, fr-audit, fr-triage skills, docs/triage/README.md and AGENTS.md; mirrors synced.

<!-- fr:journal kind=finding scope=plan id=p3-r11-resolved created=2026-10-08T16:05:37+00:00 phase=3 state=fixed resolves=p3-r11 -->
### p3-r11-resolved · finding [fixed] · resolves p3-r11: privacy-guard scenario claimed a private-state-repo create it did not test; row moved to ci without the owed lease-push part (phase 3)

dde24616 + 0a39e97a: the scenario's second create really uses a private state repo; the row's notes say the lease-push part is owed to phase 4.

<!-- fr:journal kind=finding scope=plan id=p3-r12-resolved created=2026-10-08T16:05:37+00:00 phase=3 state=fixed resolves=p3-r12 -->
### p3-r12-resolved · finding [fixed] · resolves p3-r12: ref files restored 0600 and committed 100644, losing executable modes (phase 3)

c47c1abd: 100755 for owner-executable files; restores honour the umask; test_an_executable_keeps_its_mode_across_the_ref_and_restores_honour_the_umask.

<!-- fr:journal kind=decision scope=plan id=p4-driver-adapter-is-policy created=2026-10-08T16:36:54+00:00 phase=4 -->
### p4-driver-adapter-is-policy · decision · The Driver adapter is the environment's policy (runner, refusal, post_merge); the pass is one_pass, which both entries call (phase 4)

§E sketches `Driver` as "run passes until done". The pass already lives in
`triage_batch_cmd._Driver.run_pass`, so `fr.triage.driver.Driver` carries only what
differs by environment: `runner_for(batch, to)` (host: `--to`, else the batch's/repo's
default, unchanged; cloud: `claude-cloud`), `refusal(batch)` (cloud: an explicit other
`launch.runner`, reported as a `warn` line and counted as a held dispatch) and
`post_merge(checkout, argv)` (cloud runs nothing, so no PostMergeEvent and no
`post_merge_restart`). `one_pass(driver)` (fetch + renew the lease, run_pass, mark the
pass + push) is the one body: `_host_loop` (`fr triage batch drive`) and `fr triage
drive pass` both call it, through one `build_driver`. dispatch_batch and adopt_batch
take `driver=` (default HOST) and dispatch_batch a `load=` runner cache, so a mailbox
runner the pass opened is the one that takes the dispatch.

<!-- fr:journal kind=decision scope=plan id=p4-mailbox-protocol created=2026-10-08T16:36:54+00:00 phase=4 -->
### p4-mailbox-protocol · decision · drive pass/record reach the cloud runner through a structural Mailbox protocol in fr.triage.driver; phase 5 implements it (phase 4)

Phase 5 puts requests.yaml in fr_claude_cloud, which fr never imports, so fr speaks to
it through `fr.triage.driver.Mailbox`: `open_mailbox(state_dir, statuses)` (called when
the driver loads the runner, before the pass, so pending requests re-emit),
`outbox() -> list[dict]` and `record_results(results) -> applied ids`. The outbox file
is `{"requests": [...]}`; results are a JSON list (or `{"results": [...]}`), one object
per request with its `id`. Until phase 5, `drive pass` warns that `claude-cloud` cannot
be loaded and writes an empty outbox; `drive record` needs the runner only when there
are results. `drive record` refuses a result no pending request names (exit 2, the
rest recorded) and a lease held by another driver.

<!-- fr:journal kind=decision scope=plan id=p4-scope-options-not-scope-flag created=2026-10-08T16:36:54+00:00 phase=4 -->
### p4-scope-options-not-scope-flag · decision · drive pass and lease take --repo/--org/--dir/--workspace, not the spec's `--scope S` (phase 4)

Every triage verb names its scope with --repo/--org (and --dir/--workspace); a lone
`--scope S` would need a second scope grammar. `drive pass` also takes `--state-repo`
(the brief's, for a fresh workspace: fetched and recorded), `--interval`/`--routine`
(minutes, sizing the lease and the "a wake within the interval only renews" rule) and
`--statuses` (handed to the mailbox runner). `lease take` takes `--as host|cloud`.

<!-- fr:journal kind=decision scope=plan id=p4-lease-shape-and-host-use created=2026-10-08T16:36:54+00:00 phase=4 -->
### p4-lease-shape-and-host-use · decision · lease.yaml is holder "<scope id> <identity>", started, expires and an optional last_pass; the host takes it only when the scope has a ref (phase 4)

`last_pass` is how a wake within --interval of the last pass only renews (exit 3, empty
outbox); it survives a re-home because it rides on the ref. The host loop takes the
lease after drive.lock only with --yes, a state_repo and state in a clone (without a
ref there is nothing cross-host to guard, and every existing drive test runs that way,
unchanged); it renews and pushes every pass (fetch first), and releases it on any stop
but a refusal (exit 2). The cloud pass takes drive.lock too, then the lease, and never
releases it. The wrapper's end-of-command push now skips when the state already equals
the ref it last pushed (`push_now` ran mid-command).

<!-- fr:journal kind=discovery scope=plan id=p4-scenario-gitconfig-leak created=2026-10-08T16:36:54+00:00 phase=4 -->
### p4-scenario-gitconfig-leak · discovery · A scenario's `git config --global` writes the operator's ~/.gitconfig under pytest, which lends GIT_CONFIG_GLOBAL (phase 4)

tests/conftest.py lends `GIT_CONFIG_GLOBAL=<operator>/.gitconfig` to every test, and the
scenario subprocess inherits it, so the first draft of cloud-triage-driver-lease.sh
(which set HOME and then `git config --global url.<bare>.insteadOf ...`) wrote two
`insteadOf` entries into the real /root/.gitconfig; a parallel test
(test_acceptance_cmd's resolve_identity) then read its origin through them and failed.
Both entries were removed and the scenario now exports its own GIT_CONFIG_GLOBAL. Any
future scenario that writes git's global config must do the same.

<!-- fr:journal kind=discovery scope=plan id=p4-scenario-forge-and-empty-outbox created=2026-10-08T16:36:54+00:00 phase=4 -->
### p4-scenario-forge-and-empty-outbox · discovery · The driver-lease scenario's forge answers three list routes with `[]`; its outbox stays empty until phase 5 (phase 4)

fixtures/cloud-triage-driver/bin/gh replays captured `user`, `repos/derio-net/super-fr`
and `.fr/triage.yaml` at HEAD (which names herdr and a post_merge the cloud pass must
ignore), and answers the open-issues, all-PRs and open-PRs pages with `[]`, GitHub's
empty page (no record shape invented). The state remote is a bare repo reached through
git's `url.<bare>.insteadOf https://github.com/derio-net/super-fr.git`; workspace B's
origin is the ssh spelling so `git remote get-url` is not rewritten. With no
claude-cloud runner installed there are no requests, so the scripted executor answers
none; phase 5 can extend the scenario with real requests.

<!-- fr:journal kind=discovery scope=plan id=p4-full-suite-left-to-ci created=2026-10-08T16:36:54+00:00 phase=4 -->
### p4-full-suite-left-to-ci · discovery · P4.T3.S4's full local suite was not run; evidence is the PR's CI, as the dispatch directed (phase 4)

The suite takes over 20 minutes in this container and the draft PR's CI runs it on every
push, so the record's evidence is `tests: ci`. Run locally instead: every
tests/unit/test_triage_*.py, test_cloud_triage_skeleton, test_import_direction,
test_acceptance*.py and the cloud_triage scenarios (2389 passed), ruff check, ruff
format and the AGENTS.md mypy command (clean).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-10-08T16:36:54+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

lease.py is a handful of pure functions over one file plus acquire's write-then-push; the in-command push the lease needed became triage_cmd.push_now, which the wrapper's close push now calls instead of repeating push_state's arguments

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t2 created=2026-10-08T16:36:54+00:00 phase=4 -->
### no-refactor-p4-t2 · discovery · no-refactor-because P4.T2 (phase 4)

the adapter is two small frozen dataclasses; the runner choice reuses the existing _with_runner/--to path (runner_for returns the --to the host already had), so no selection code was duplicated

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-10-08T16:55:15+00:00 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · a cloud-refused batch still took an in-flight slot in drive_pass (phase 4)

batch_drive.py:1118; triage_batch_cmd.py:3162.

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-10-08T16:55:15+00:00 phase=4 state=open review_scope=in -->
### p4-r2 · finding [open] (reviewer: in scope) · 'wake within the interval only renews' compared strictly; minute-truncated wakes halved the drive rate (phase 4)

triage_drive_cmd.py:254-258.

<!-- fr:journal kind=finding scope=plan id=p4-r3 created=2026-10-08T16:55:15+00:00 phase=4 state=open review_scope=in -->
### p4-r3 · finding [open] (reviewer: in scope) · a host drive with a state_repo but state in no clone ran with no lease (phase 4)

triage_batch_cmd.py:4068-4078.

<!-- fr:journal kind=finding scope=plan id=p4-r4 created=2026-10-08T16:55:15+00:00 phase=4 state=open review_scope=in -->
### p4-r4 · finding [open] (reviewer: in scope) · the lease was not released on Ctrl-C/SIGTERM (phase 4)

triage_batch_cmd.py:4186-4192.

<!-- fr:journal kind=finding scope=plan id=p4-r5 created=2026-10-08T16:55:15+00:00 phase=4 state=open review_scope=in -->
### p4-r5 · finding [open] (reviewer: in scope) · drive record recorded with no lease, ignored expiry, took no drive.lock (phase 4)

triage_drive_cmd.py:337.

<!-- fr:journal kind=finding scope=plan id=p4-r6 created=2026-10-08T16:55:15+00:00 phase=4 state=open review_scope=in -->
### p4-r6 · finding [open] (reviewer: in scope) · phase 5's plan never named the Mailbox contract; an unloadable claude-cloud was a warning with an empty outbox (phase 4)

triage_drive_cmd.py:288-306; 05.yaml.

<!-- fr:journal kind=finding scope=plan id=p4-r7 created=2026-10-08T16:55:15+00:00 phase=4 state=open review_scope=in -->
### p4-r7 · finding [open] (reviewer: in scope) · spec §E still said drive pass --scope S (phase 4)

spec line 277.

<!-- fr:journal kind=finding scope=plan id=p4-r8 created=2026-10-08T16:55:15+00:00 phase=4 state=open review_scope=in -->
### p4-r8 · finding [open] (reviewer: in scope) · the scenario's second driver was refused by the workspace-local lease.yaml, not through the ref (phase 4)

tests/scenarios/cloud-triage-driver-lease.sh:70.

<!-- fr:journal kind=finding scope=plan id=p4-r9 created=2026-10-08T16:55:15+00:00 phase=4 state=open review_scope=in -->
### p4-r9 · finding [open] (reviewer: in scope) · drive pass handed out commands without --dir/--workspace (phase 4)

triage_drive_cmd.py:282.

<!-- fr:journal kind=finding scope=plan id=p4-r10 created=2026-10-08T16:55:15+00:00 phase=4 state=open review_scope=in -->
### p4-r10 · finding [open] (reviewer: in scope) · a cloud driver closed out a host-dispatched batch through herdr (phase 4)

triage_batch_cmd.py:3096.

<!-- fr:journal kind=finding scope=plan id=p4-r11 created=2026-10-08T16:55:15+00:00 phase=4 state=open review_scope=out -->
### p4-r11 · finding [open] (reviewer: out of scope) · scope id = sha256(name, host id), so drivers with different host ids get different refs and the lease cannot arbitrate them (phase 4)

scope_config.py:80-85; a spec/phase 3 design property.

<!-- fr:journal kind=finding scope=plan id=p4-r12 created=2026-10-08T16:55:15+00:00 phase=4 state=open review_scope=out -->
### p4-r12 · finding [open] (reviewer: out of scope) · tests/conftest.py lent the operator's real ~/.gitconfig as GIT_CONFIG_GLOBAL (phase 4)

tests/conftest.py:120, from phase 3's b9408eec; filed in scope as p4-o1.

<!-- fr:journal kind=finding scope=plan id=p4-o1 created=2026-10-08T16:55:15+00:00 phase=4 state=open review_scope=in -->
### p4-o1 · finding [open] (reviewer: in scope) · the suite's HOME sandbox let tests write the operator's global git config (this PR's phase 3 defect; it happened in this phase) (phase 4)

Raised by the orchestrator from p4-r12 and the executor's report: a scenario draft wrote url.insteadOf entries into /root/.gitconfig through GIT_CONFIG_GLOBAL. This PR introduced the fixture (b9408eec), so it is this change's defect, filed in scope rather than left as p4-r12's out-of-scope note.

<!-- fr:journal kind=finding scope=plan id=p4-o2 created=2026-10-08T16:55:15+00:00 phase=5 state=open review_scope=in -->
### p4-o2 · finding [open] (reviewer: in scope) · the cloud driver still loads the foreign runner (herdr) for a close-out's preflight/existing_dispatches check (phase 5)

Found by the p4 fix agent while fixing p4-r10 (8fe0fd02): _close_out now returns before any dispatch for a batch whose runner the driver lacks, but the foreign runner is still loaded and asked preflight/existing_dispatches first, so a cloud environment without herdr hits that load. Belongs to phase 5 (the claude-cloud runner and its environment): the cloud driver must never load a runner it does not carry.

<!-- fr:journal kind=review scope=plan id=p4-review created=2026-10-08T16:55:15+00:00 phase=4 -->
### p4-review · review · phase 4 code review: 10 findings in scope, 2 out (phase 4)

Dispatched reviewer (superpowers:requesting-code-review discipline) over ae78e6fb..1ae604aa (excluding the orchestrator's ce8bd6a0 and e7024b4d) against spec R9-R13/§B/§D/§E/Test Plan 8, 9, 14 and plan 04.yaml; 33 targeted tests run. It judged the three departures: --repo/--org acceptable (spec amended, p4-r7), the Mailbox seam acceptable with p4-r6, the host lease only with a state ref acceptable except outside a clone (p4-r3). Received (superpowers:receiving-code-review): each verified; the spec and plan decided r1-r7, r9, r10 (cecf1f9e); a fix agent implemented them and p4-o1 with a failing test first (d6c7a752, a13e9c03, 567c31bc, 8fe0fd02, 820127cf); 2047 targeted tests and 4 cloud-triage scenarios pass; ruff and mypy clean. p4-r11 is out of scope by design (decision d1: the cloud driver is its own scope beside the host's, kept apart by per-issue claims). p4-o2 is filed against phase 5.

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-10-08T16:55:15+00:00 phase=4 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: a cloud-refused batch still took an in-flight slot in drive_pass (phase 4)

d6c7a752: Snapshot.refused; the planner emits held before the in-flight cap; test_a_batch_the_driver_refuses_is_a_hold_that_takes_no_in_flight_slot.

<!-- fr:journal kind=finding scope=plan id=p4-r2-resolved created=2026-10-08T16:55:15+00:00 phase=4 state=fixed resolves=p4-r2 -->
### p4-r2-resolved · finding [fixed] · resolves p4-r2: 'wake within the interval only renews' compared strictly; minute-truncated wakes halved the drive rate (phase 4)

a13e9c03: renew only under half an interval; test_only_a_wake_within_half_an_interval_of_the_last_pass_only_renews.

<!-- fr:journal kind=finding scope=plan id=p4-r3-resolved created=2026-10-08T16:55:15+00:00 phase=4 state=fixed resolves=p4-r3 -->
### p4-r3-resolved · finding [fixed] · resolves p4-r3: a host drive with a state_repo but state in no clone ran with no lease (phase 4)

567c31bc: refuses with exit 2 naming --workspace; test_a_host_drive_whose_state_is_in_no_clone_refuses_naming_workspace.

<!-- fr:journal kind=finding scope=plan id=p4-r4-resolved created=2026-10-08T16:55:15+00:00 phase=4 state=fixed resolves=p4-r4 -->
### p4-r4-resolved · finding [fixed] · resolves p4-r4: the lease was not released on Ctrl-C/SIGTERM (phase 4)

567c31bc: SIGTERM raises KeyboardInterrupt for the loop; the lease is released and the handler restored; test_sigterm_releases_the_host_drivers_lease_and_restores_the_handler.

<!-- fr:journal kind=finding scope=plan id=p4-r5-resolved created=2026-10-08T16:55:15+00:00 phase=4 state=fixed resolves=p4-r5 -->
### p4-r5-resolved · finding [fixed] · resolves p4-r5: drive record recorded with no lease, ignored expiry, took no drive.lock (phase 4)

a13e9c03: record requires this driver's live lease and runs under drive_lock; test_record_refuses_without_this_drivers_live_lease.

<!-- fr:journal kind=finding scope=plan id=p4-r6-resolved created=2026-10-08T16:55:15+00:00 phase=4 state=fixed resolves=p4-r6 -->
### p4-r6-resolved · finding [fixed] · resolves p4-r6: phase 5's plan never named the Mailbox contract; an unloadable claude-cloud was a warning with an empty outbox (phase 4)

cecf1f9e (05.yaml names the Mailbox contract) + a13e9c03: a pass refuses when the cloud runner is unloadable or keeps no Mailbox.

<!-- fr:journal kind=finding scope=plan id=p4-r7-resolved created=2026-10-08T16:55:15+00:00 phase=4 state=fixed resolves=p4-r7 -->
### p4-r7-resolved · finding [fixed] · resolves p4-r7: spec §E still said drive pass --scope S (phase 4)

cecf1f9e: §E shows drive pass --repo/--org and its options.

<!-- fr:journal kind=finding scope=plan id=p4-r8-resolved created=2026-10-08T16:55:15+00:00 phase=4 state=fixed resolves=p4-r8 -->
### p4-r8-resolved · finding [fixed] · resolves p4-r8: the scenario's second driver was refused by the workspace-local lease.yaml, not through the ref (phase 4)

a13e9c03: workspace C restored from the ref as host: with the same host id is refused through the ref's lease; the existing check kept.

<!-- fr:journal kind=finding scope=plan id=p4-r9-resolved created=2026-10-08T16:55:15+00:00 phase=4 state=fixed resolves=p4-r9 -->
### p4-r9-resolved · finding [fixed] · resolves p4-r9: drive pass handed out commands without --dir/--workspace (phase 4)

a13e9c03: triage_kanban_cmd.scope_args with --dir/--workspace; test_the_pass_hands_out_commands_with_the_full_scope_arguments.

<!-- fr:journal kind=finding scope=plan id=p4-r10-resolved created=2026-10-08T16:55:15+00:00 phase=4 state=fixed resolves=p4-r10 -->
### p4-r10-resolved · finding [fixed] · resolves p4-r10: a cloud driver closed out a host-dispatched batch through herdr (phase 4)

8fe0fd02: a close-out of a batch another driver's runner owns is reported and left to it before any fast-forward, post_merge or dispatch; the remaining foreign-runner load is p4-o2, filed against phase 5.

<!-- fr:journal kind=finding scope=plan id=p4-r11-resolved created=2026-10-08T16:55:15+00:00 phase=4 state=open resolves=p4-r11 out_of_scope=true -->
### p4-r11-resolved · finding [out-of-scope] · resolves p4-r11: scope id = sha256(name, host id), so drivers with different host ids get different refs and the lease cannot arbitrate them (phase 4)

By design, not caused by phase 4: decision d1 makes the cloud driver its own scope beside the host one, kept apart by per-issue claims (spec 2026-10-06-triage-claims); the lease guards one scope, as R9 states.

<!-- fr:journal kind=finding scope=plan id=p4-r12-resolved created=2026-10-08T16:55:15+00:00 phase=4 state=open resolves=p4-r12 out_of_scope=true -->
### p4-r12-resolved · finding [out-of-scope] · resolves p4-r12: tests/conftest.py lent the operator's real ~/.gitconfig as GIT_CONFIG_GLOBAL (phase 4)

Not caused by phase 4 (from phase 3's b9408eec); filed in scope as p4-o1 and fixed there.

<!-- fr:journal kind=finding scope=plan id=p4-o1-resolved created=2026-10-08T16:55:15+00:00 phase=4 state=fixed resolves=p4-o1 -->
### p4-o1-resolved · finding [fixed] · resolves p4-o1: the suite's HOME sandbox let tests write the operator's global git config (this PR's phase 3 defect; it happened in this phase) (phase 4)

820127cf: a per-test identity-only .gitconfig; GIT_CONFIG_GLOBAL never names the operator's file; test_a_global_git_config_write_never_reaches_the_operators_file.

<!-- fr:journal kind=decision scope=plan id=p5-entry-point-is-the-class created=2026-10-08T17:30:08+00:00 phase=5 -->
### p5-entry-point-is-the-class · decision · The claude-cloud entry point names the class, not a from_env function as 05.yaml wrote (phase 5)

P5.T1.S2 said `claude-cloud = "fr_claude_cloud.runner:from_env"`, but
`fr_dispatch.registry.load_runner` and `runner_units` load the entry point and read
`from_env` and `units` off what it names; a module-level function has neither, so
the runner could not be built or routed. The entry point is
`fr_claude_cloud.runner:ClaudeCloudRunner`, as herdr's is, and `from_env` is its
classmethod; test_claude_cloud_contract.py pins both.

<!-- fr:journal kind=decision scope=plan id=p5-mailbox-files-and-results created=2026-10-08T17:30:08+00:00 phase=5 -->
### p5-mailbox-files-and-results · decision · requests.yaml holds pending requests and an `issued` counter; sessions.yaml the recorded sessions with their last state; status requests are never stored (phase 5)

A request id is `<item id>:<kind>:<n>`, n from `issued["<item>:<kind>"]`, so a retry
(a refused message, a busy close) is a new id and a re-emitted request the same id.
Results: dispatch `{id, session}` records the session, `{id, error}` keeps it pending;
close `{id, outcome: closed|busy|absent}`; message `{id, outcome: sent|refused}`, a
refused one re-queued as the next number; rehome `{id, session}` replaces the session;
status `{id, state, needs_action}`. Every pass emits one `<item>:status:1` per recorded
session (not stored; recording it updates that session's state), so a later read with
no `--statuses` (the board, `drive record`) still knows a blocked session's note. Each
outbox entry carries `execute` and `record` from `fr_claude_cloud.mailbox.REQUEST_TABLE`
(dispatch/message/close/rehome/status), the text phase 7's fr-triage skill can point
the agent at. `--statuses` accepts `{"sessions": [...]}`, a bare list, or a mapping by
item id; a pending dispatch whose tag a listed session carries is recorded, not created
again. `rehome(item, brief)` exists on the runner; phase 6 wires the driver to it.

<!-- fr:journal kind=decision scope=plan id=p5-scenario-uses-the-real-runner created=2026-10-08T17:30:08+00:00 phase=5 -->
### p5-scenario-uses-the-real-runner · decision · The driver-lease scenario now runs the real claude-cloud runner; stub_cloud.py is deleted (phase 5)

The candidate install carries every runner package (its checkout derivation reads the
`fr.runners` entry points; the git list gained fr-claude-cloud), so the stub injection
was no longer needed and its "a pass with no cloud runner refuses" step could no longer
hold (the unit test test_a_pass_refuses_when_the_cloud_runner_cannot_be_loaded keeps
that refusal). Workspace A now seeds the ref with one pending dispatch request in the
runner's own format; B's pass, restored from the ref alone, re-emits it (with its
`create_session` instruction), the scripted executor answers it with a session, and
`drive record` moves it into the ref's sessions.yaml. No fake session executor beyond
that sed is needed: the scope has no batch, and a real dispatch would need an invented
forge issue record.

<!-- fr:journal kind=decision scope=plan id=p5-carries-and-host-board-unchanged created=2026-10-08T17:30:08+00:00 phase=5 -->
### p5-carries-and-host-board-unchanged · decision · Driver.carries and Driver.adopt_runner; the host's board still loads runners as before (phase 5)

p4-o2: `Driver.carries(name)` (host: everything; cloud: only claude-cloud) is checked
where `_Driver` loads a runner: `runner()` raises for an uncarried name, `_try_runner`
returns None silently (`_sessions`, `_idle`, `_restart_sessions`), `_existing` skips a
close-out whose runner is not carried, and `_hand_back` leaves another runner's session
to its driver. The cloud driver's board reads sessions through its own runner cache
(`write_board(loader=...)`), so the mailbox already opened with the pass's statuses
answers; the host's board keeps loading through triage_kanban_cmd.load_runner, as
before (tests/unit/test_triage_batch_drive_idle.py counts those calls). `adopt --list`
without `--to` reads `driver.adopt_runner or ADOPT_LIST_RUNNER` and, when that runner
adopts nothing, prints that it is skipped instead of refusing.

<!-- fr:journal kind=discovery scope=plan id=p5-needs-you-now-reads-runners-on-render created=2026-10-08T17:30:08+00:00 phase=5 -->
### p5-needs-you-now-reads-runners-on-render · discovery · fr triage render now asks the dispatched batches' runners for session notes (phase 5)

Needs you now is drawn by `render.render`, which loaded no runner before. To show a
blocked session's note there (R15), `fr triage render` calls
`triage_kanban_cmd.read_sessions(..., target=<state dir>)`, the board's soft reader: a
runner that cannot load, refuses or raises costs nothing on the page, and only a
runner implementing `SessionNotes` adds rows (kind `session-blocked`). With no notes the
page is byte-identical (pinned by a test).

<!-- fr:journal kind=discovery scope=plan id=p5-batch-cmd-import-cycle created=2026-10-08T17:30:08+00:00 phase=5 -->
### p5-batch-cmd-import-cycle · discovery · Importing fr.commands.triage_batch_cmd before fr.cli fails on a pre-existing triage_cmd ↔ triage_kanban_cmd cycle (phase 5)

`python -c "from fr.commands import triage_batch_cmd"` raises ImportError (`_fail` from a
partially initialised triage_kanban_cmd, via triage_claim_cmd) on the base of this phase
too, so it is not this phase's. It shows as a collection error when an xdist worker
collects tests/unit/test_triage_batch_drive_idle.py first in a small file set; the test
modules that `import fr.cli` first are unaffected. Left as found.

<!-- fr:journal kind=discovery scope=plan id=p5-full-suite-left-to-ci created=2026-10-08T17:30:08+00:00 phase=5 -->
### p5-full-suite-left-to-ci · discovery · P5.T3.S3's full local suite was not run; evidence is the PR's CI, as the dispatch directed (phase 5)

Run locally instead: tests/unit/test_triage_*.py, test_claude_cloud_*.py,
test_import_direction.py, test_runner_package_lists.py, test_fr_herdr_*.py,
test_fr_dispatch_*.py, test_run_unit_runner_contract.py, test_tripwire_*.py,
test_acceptance*.py and tests/integration/test_scenarios.py (the cloud_triage
scenarios against a fresh candidate install); ruff check, ruff format and the AGENTS.md
mypy command with packages/fr-claude-cloud/src (clean). The one known failure,
test_validate_artifacts.py::test_an_unreadable_artifact_is_a_failure_naming_it, is the
container running as root.

<!-- fr:journal kind=finding scope=plan id=p4-o2-resolved created=2026-10-08T17:30:08+00:00 phase=5 state=fixed resolves=p4-o2 -->
### p4-o2-resolved · finding [fixed] · resolves p4-o2: the cloud driver still loads the foreign runner (herdr) for a close-out's preflight/existing_dispatches check (phase 5)

Driver.carries (cloud: claude-cloud only) gates every runner load in _Driver: a
foreign close-out is no longer probed through _existing (its preflight and
existing_dispatches), _try_runner/_sessions/_idle skip an uncarried runner without
loading it, _hand_back leaves another runner's session to its driver, runner() raises
rather than load, and the cloud board reads through the driver's own cache. Test:
tests/unit/test_claude_cloud_status.py::test_the_cloud_driver_never_loads_a_runner_it_does_not_carry
(fails with carries() returning True: "the cloud driver loaded herdr").

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t1 created=2026-10-08T17:30:08+00:00 phase=5 -->
### no-refactor-p5-t1 · discovery · no-refactor-because P5.T1 (phase 5)

the package is a pyproject, an __init__ and a stub runner; every obligation was a one-token edit to an existing list (workspace dependencies and sources, coverage source, the scaffold's RUNNER_PACKAGES, the mypy command) and scripts/version_surfaces.py already globs packages/*/pyproject.toml, so it needed no edit

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t2 created=2026-10-08T17:30:08+00:00 phase=5 -->
### no-refactor-p5-t2 · discovery · no-refactor-because P5.T2 (phase 5)

the mailbox is one class over two files and the runner only delegates to it; the stub_cloud.py test double the driver-lease scenario carried became dead the moment the real runner existed, and was deleted rather than kept beside it

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t3 created=2026-10-08T17:30:08+00:00 phase=5 -->
### no-refactor-p5-t3 · discovery · no-refactor-because P5.T3 (phase 5)

each change rides an existing seam: session_statuses became a wrapper over read_sessions (one loop, one place notes are read), the board hint and Needs-you-now each gained one optional mapping, and p4-o2 is one adapter predicate (Driver.carries) checked at the three places a runner is loaded

<!-- fr:journal kind=finding scope=plan id=p5-r1 created=2026-10-08T17:44:32+00:00 phase=5 state=open review_scope=in -->
### p5-r1 · finding [open] (reviewer: in scope) · after a rehome, matching by tag let the old session overwrite the new recorded session's state (order-dependent) (phase 5)

mailbox.py:215,381; reproduced.

<!-- fr:journal kind=finding scope=plan id=p5-r2 created=2026-10-08T17:44:32+00:00 phase=5 state=open review_scope=in -->
### p5-r2 · finding [open] (reviewer: in scope) · replaying a rehome whose result was lost created a second session (phase 5)

mailbox.py:73; R14 never-duplicated.

<!-- fr:journal kind=finding scope=plan id=p5-r3 created=2026-10-08T17:44:32+00:00 phase=5 state=open review_scope=in -->
### p5-r3 · finding [open] (reviewer: in scope) · a status request for a session with a pending close made drive record exit 2 (phase 5)

mailbox.py:270,308; triage_drive_cmd.py:365-367; reproduced.

<!-- fr:journal kind=finding scope=plan id=p5-r4 created=2026-10-08T17:44:32+00:00 phase=5 state=open review_scope=in -->
### p5-r4 · finding [open] (reviewer: in scope) · Mailbox.record was not atomic (phase 5)

mailbox.py:293,267; reproduced.

<!-- fr:journal kind=finding scope=plan id=p5-r5 created=2026-10-08T17:44:32+00:00 phase=5 state=open review_scope=in -->
### p5-r5 · finding [open] (reviewer: in scope) · the item-keyed statuses shape invented a session id and consumed a pending dispatch (phase 5)

mailbox.py:131,381; reproduced.

<!-- fr:journal kind=finding scope=plan id=p5-r6 created=2026-10-08T17:44:32+00:00 phase=5 state=open review_scope=in -->
### p5-r6 · finding [open] (reviewer: in scope) · archived sessions kept the item held and were re-closed every pass (phase 5)

mailbox.py:228,37; runner.py:100; reproduced.

<!-- fr:journal kind=finding scope=plan id=p5-r7 created=2026-10-08T17:44:32+00:00 phase=5 state=open review_scope=in -->
### p5-r7 · finding [open] (reviewer: in scope) · adopt --list driver selection was unreachable from the CLI (phase 5)

triage_batch_cmd.py:1848.

<!-- fr:journal kind=finding scope=plan id=p5-r8 created=2026-10-08T17:44:32+00:00 phase=5 state=open review_scope=in -->
### p5-r8 · finding [open] (reviewer: in scope) · fr triage render probed every runner and could save the mailbox from a read-only command (phase 5)

triage_cmd.py:728; triage_kanban_cmd.py:311; mailbox.py:192.

<!-- fr:journal kind=finding scope=plan id=p5-r9 created=2026-10-08T17:44:32+00:00 phase=5 state=open review_scope=in -->
### p5-r9 · finding [open] (reviewer: in scope) · HERMES.md, README.md and subsystems.yaml lists lacked fr-claude-cloud (phase 5)

HERMES.md:67; README.md:467; docs/triage/derio-net--super-fr/subsystems.yaml:33.

<!-- fr:journal kind=finding scope=plan id=p5-o1 created=2026-10-08T17:44:32+00:00 phase=5 state=open review_scope=in -->
### p5-o1 · finding [open] (reviewer: in scope) · test_version_surfaces' hand-kept lists and the committed dev/admin profiles' POST_CREATE lacked fr-claude-cloud (CI red on 6bb24bae) (phase 5)

Raised by the orchestrator from the CI annotations on 6bb24bae (test_one_uv_lock_entry_per_workspace_member, test_committed_profiles_carry_the_scaffold_post_create) before review was dispatched.

<!-- fr:journal kind=review scope=plan id=p5-review created=2026-10-08T17:44:32+00:00 phase=5 -->
### p5-review · review · phase 5 code review: 9 findings in scope (phase 5)

Dispatched reviewer (superpowers:requesting-code-review discipline) over 7bb849ab..9290737a against spec R14/R15/§E/§F/Test Plan 9-10 and plan 05.yaml; every mailbox finding reproduced with a throwaway script against the real mailbox. It judged the departures: the entry point naming the class is what the registry requires (all four runner packages do it); the scenario on the real runner is sound; render reading notes is legitimate but costly (p5-r8). Received (superpowers:receiving-code-review): each verified; no spec change needed (R14/§F already require never-duplicated and idempotent replay); a fix agent implemented all nine with a failing test first (41438b61, a571923c, 71816688, e3a5136a); 2225 targeted tests and 4 cloud-triage scenarios pass; ruff and mypy clean. p5-o1, caught by CI before review, fixed in 9290737a.

<!-- fr:journal kind=finding scope=plan id=p5-r1-resolved created=2026-10-08T17:44:32+00:00 phase=5 state=fixed resolves=p5-r1 -->
### p5-r1-resolved · finding [fixed] · resolves p5-r1: after a rehome, matching by tag let the old session overwrite the new recorded session's state (order-dependent) (phase 5)

41438b61: a recorded session is matched by id, the tag only finds an unrecorded one; test_after_a_rehome_the_recorded_session_is_matched_by_id_not_by_the_shared_tag.

<!-- fr:journal kind=finding scope=plan id=p5-r2-resolved created=2026-10-08T17:44:32+00:00 phase=5 state=fixed resolves=p5-r2 -->
### p5-r2-resolved · finding [fixed] · resolves p5-r2: replaying a rehome whose result was lost created a second session (phase 5)

41438b61: dispatch and rehome carry a request_tag looked up first; test_a_replayed_rehome_whose_result_was_lost_creates_one_new_session.

<!-- fr:journal kind=finding scope=plan id=p5-r3-resolved created=2026-10-08T17:44:32+00:00 phase=5 state=fixed resolves=p5-r3 -->
### p5-r3-resolved · finding [fixed] · resolves p5-r3: a status request for a session with a pending close made drive record exit 2 (phase 5)

41438b61: no status asked of a session with a pending close; a status for a session closed in the same record is applied; test_record_accepts_a_status_for_a_session_it_closes_in_the_same_file.

<!-- fr:journal kind=finding scope=plan id=p5-r4-resolved created=2026-10-08T17:44:32+00:00 phase=5 state=fixed resolves=p5-r4 -->
### p5-r4-resolved · finding [fixed] · resolves p5-r4: Mailbox.record was not atomic (phase 5)

41438b61: validate all, apply in memory, save once, restore on any raise; test_a_refused_record_leaves_both_files_byte_identical.

<!-- fr:journal kind=finding scope=plan id=p5-r5-resolved created=2026-10-08T17:44:32+00:00 phase=5 state=fixed resolves=p5-r5 -->
### p5-r5-resolved · finding [fixed] · resolves p5-r5: the item-keyed statuses shape invented a session id and consumed a pending dispatch (phase 5)

41438b61: an item-keyed status without a session id only updates a recorded session; test_an_item_keyed_status_never_invents_a_session_or_consumes_a_dispatch.

<!-- fr:journal kind=finding scope=plan id=p5-r6-resolved created=2026-10-08T17:44:32+00:00 phase=5 state=fixed resolves=p5-r6 -->
### p5-r6-resolved · finding [fixed] · resolves p5-r6: archived sessions kept the item held and were re-closed every pass (phase 5)

41438b61: archived or closed sessions release the item and are never closed again (sessions.yaml closed: list); test_an_archived_session_releases_the_item_and_is_not_closed_again.

<!-- fr:journal kind=finding scope=plan id=p5-r7-resolved created=2026-10-08T17:44:32+00:00 phase=5 state=fixed resolves=p5-r7 -->
### p5-r7-resolved · finding [fixed] · resolves p5-r7: adopt --list driver selection was unreachable from the CLI (phase 5)

a571923c: adopt --list follows the scope's lease holder through the CLI; test_adopt_list_in_a_cloud_scope_reads_the_cloud_runner_through_the_cli.

<!-- fr:journal kind=finding scope=plan id=p5-r8-resolved created=2026-10-08T17:44:32+00:00 phase=5 state=fixed resolves=p5-r8 -->
### p5-r8-resolved · finding [fixed] · resolves p5-r8: fr triage render probed every runner and could save the mailbox from a read-only command (phase 5)

41438b61 + 71816688: read_sessions(notes_only) for render; read-only mailbox open; test_render_reads_a_cloud_mailbox_without_writing_it.

<!-- fr:journal kind=finding scope=plan id=p5-r9-resolved created=2026-10-08T17:44:32+00:00 phase=5 state=fixed resolves=p5-r9 -->
### p5-r9-resolved · finding [fixed] · resolves p5-r9: HERMES.md, README.md and subsystems.yaml lists lacked fr-claude-cloud (phase 5)

e3a5136a: HERMES.md (mypy and runner lines), README.md table, subsystems.yaml paths; a repo-wide grep found no other runner list lacking it.

<!-- fr:journal kind=finding scope=plan id=p5-o1-resolved created=2026-10-08T17:44:32+00:00 phase=5 state=fixed resolves=p5-o1 -->
### p5-o1-resolved · finding [fixed] · resolves p5-o1: test_version_surfaces' hand-kept lists and the committed dev/admin profiles' POST_CREATE lacked fr-claude-cloud (CI red on 6bb24bae) (phase 5)

9290737a: fr-claude-cloud in test_version_surfaces' members and manifests and in both committed profiles' POST_CREATE; CI green on 9290737a.

<!-- fr:journal kind=decision scope=plan id=p6-drift-reads-the-cursor-from-the-pr-files created=2026-10-08T18:20:21+00:00 phase=6 -->
### p6-drift-reads-the-cursor-from-the-pr-files · decision · The pass finds a batch's run cursor among its open PR's changed files and reads it at the PR head (phase 6)

§G says the pass reads the cursor "from the batch branch head". The run id is not
known to triage, and REST lists no directory at a ref, so `_Driver._drift` takes the
one `docs/superpowers/runs/<run>.yaml` among `batch_pr(...).files` (facts already
carry them) and reads it with `read_file_at_ref(repo, path, head_oid)`. A batch with
no open PR, or whose PR carries no cursor yet, is skipped that pass, never reported
as versionless; only a cursor read without `fr_version` is.

<!-- fr:journal kind=decision scope=plan id=p6-rehome-at-idle created=2026-10-08T18:20:21+00:00 phase=6 -->
### p6-rehome-at-idle · decision · A drifted run's rehome request is written only when its session is idle, like the conflict hand-back (phase 6)

R17's "at its next idle moment" is applied by the planner (`plan_drift` needs status
`idle` from the runner's `session_statuses`), the rule the conflict hand-back already
keeps; a working or blocked session is asked again on a later pass. The (run,
release) entry is written to rehomes.yaml when the request is written, so a lost
result is re-emitted by the mailbox (same id), never asked twice.

<!-- fr:journal kind=decision scope=plan id=p6-ledger-shape created=2026-10-08T18:20:21+00:00 phase=6 -->
### p6-ledger-shape · decision · rehomes.yaml holds rehomes per (run, release), the runs reported versionless, and the driver's own start and pending self-rehome (phase 6)

"Reported once" must survive a fresh process (every cloud wake is one), so the
reported runs live in the ledger too, beside `rehomes`. `driver.start` is the fr the
driver session started with (recorded on its first pass that read a release);
`driver.pending` is the self-rehome request, re-emitted until `drive record` names
it, which sets `start` to the release. Results whose id starts `driver:rehome:` are
routed to the ledger, the rest to the runner's mailbox.

<!-- fr:journal kind=decision scope=plan id=p6-driver-rehomes-on-a-greater-major created=2026-10-08T18:20:21+00:00 phase=6 -->
### p6-driver-rehomes-on-a-greater-major · decision · The driver re-homes itself only when the release's major is GREATER than its start's (R18 says "differs") (phase 6)

A dev build newer than every release (this repo's candidate install, once fr reaches
6.0 before 6.0 is released) would otherwise re-home onto an older fr on every pass.
Runs keep R17's literal "differs". The spec's R18 wording may want the same
qualification; not edited here (the spec is outside this phase's files).

<!-- fr:journal kind=decision scope=plan id=p6-self-update-install-and-reexec created=2026-10-08T18:20:21+00:00 phase=6 -->
### p6-self-update-install-and-reexec · decision · The real installer is the cloud setup's (the marketplace clone at the release tag, then install.sh); the re-exec runs the first fr on PATH, once per release (phase 6)

`_install_release` clones or fetches `~/.claude/plugins/marketplaces/derio-net--super-fr`,
checks out the release tag and runs `scripts/install.sh`, the §H setup-script steps
phase 7 documents; `_reexec` sets FR_TRIAGE_REEXEC=<release> and execs `fr` with the
same arguments, outside drive.lock (the same pid takes it again). A re-exec that
still finds the older fr warns and runs the pass on it; a failed install warns and
runs it too. Neither has run live: both are injected in every test.

<!-- fr:journal kind=discovery scope=plan id=p6-drift-scenario-forge created=2026-10-08T18:20:21+00:00 phase=6 -->
### p6-drift-scenario-forge · discovery · The version-drift scenario's forge derives three batch PRs from captured draft PR 1080 and serves every other route from the captured index (phase 6)

Each batch PR is PR 1080's record with only number, head.ref and its one changed
file's name rewritten (all three share its head and so its captured CI); members are
captured closed issues 432/458/471, whose comments answer `[]` (the claim refresh
then writes nothing). The cursors at that head are fr's own artifact. The latest
release is the capture `v5.17.1` (added this phase, `repos/.../releases/latest`), so
the cursors record 4.9.0 and 5.17.0 rather than the plan's 5.x and 6.x: the shape
(one run on another major, one on the release's, one with none) is the plan's.

<!-- fr:journal kind=discovery scope=plan id=p6-full-suite-left-to-ci created=2026-10-08T18:20:21+00:00 phase=6 -->
### p6-full-suite-left-to-ci · discovery · P6.T3.S2's full local suite was not run; evidence is the PR's CI, as the dispatch directed (phase 6)

Run locally instead: test_migration_*, test_run_*, test_validate_artifacts,
test_triage_*, test_claude_cloud_*, test_real_ghrestclient, test_github_rest_*,
test_forgeapi, test_release_script, test_import_direction, test_tripwire_* (4722
passed, the one known root-only failure) and the six cloud_triage scenario tests
against a fresh candidate install; ruff format/check and the AGENTS.md mypy command
with fr-claude-cloud (clean); `fr validate artifacts`, `fr acceptance check` and
`fr run status` on this run's migrated cursor.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t1 created=2026-10-08T18:20:21+00:00 phase=6 -->
### no-refactor-p6-t1 · discovery · no-refactor-because P6.T1 (phase 6)

a stamp-only hop is one module copied from run_bound_model.py, one optional field, one line in start_cmd and the version pins the older hop tests carried; _already_v9 joins its two siblings in the one module allowed to consult the live model, so nothing was duplicated to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t2 created=2026-10-08T18:20:21+00:00 phase=6 -->
### no-refactor-p6-t2 · discovery · no-refactor-because P6.T2 (phase 6)

drift.py is pure and new; the pass gained one method (_Driver._drift) on existing seams (batch_pr, _probe, _try_runner, the mailbox runner's rehome), and the client gained one route on each backend

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t3 created=2026-10-08T18:20:21+00:00 phase=6 -->
### no-refactor-p6-t3 · discovery · no-refactor-because P6.T3 (phase 6)

the self-update is one function in triage_drive_cmd beside the pass it guards, and its plan is drift.py's; the only shared code touched is one_pass's new lease_taken flag
