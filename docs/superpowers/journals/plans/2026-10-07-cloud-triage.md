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
