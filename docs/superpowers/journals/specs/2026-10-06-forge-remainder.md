# Journal: 2026-10-06-forge-remainder

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-06T07:38:09+00:00 input=true -->
### operator-brief · discovery · Operator brief — batch forge-remainder (super-fr#742, super-fr#892)

Every forge call goes through the adapter: triage collect and isolation lookups, allowlist emptied

Batch `forge-remainder` of derio-net/super-fr: 2 issues, delivered as ONE pull request.

## super-fr#742: Pipeline code and skills call gh directly, bypassing the forge adapter: deliver can never resolve on GitLab/Gitea
Hard gate fixed by #744 (deliver reads the PR body via `client_for`; tripwire `test_tripwire_forge_adapter.py` with a shrink-only allowlist). Still direct `gh`: triage collect (`fr.gh.list_*`), isolation/local.py default-branch and PR-by-branch lookups (second copy of the adapter), remaining skill prose.
Note: Feature (fr-goal), batch `forge-remainder`, after `closeout-always` (both touch run/closeout.py). Driven by the tripwire allowlist: each site removed shrinks it.

## super-fr#892: fr triage batch: make_client drops the self-hosted host (same class as #490)
`triage_batch_cmd.make_client` never passes `host=`, so batch verbs on a self-hosted forge talk to the SaaS default.
Note: Same class as super-fr#490.

## Why these belong together
Wave 5 (high severity): #742 is a high-severity regression (deliver never resolves on GitLab/Gitea); #744 fixed the hard gate and left a shrink-only allowlist, this empties it. #892 is the same bypass in the triage batch verbs (make_client drops the self-hosted host).

## Delivery rules
- Work on branch `feat/batch-forge-remainder`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#742
  Closes derio-net/super-fr#892
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=d1-collect-adapter-github-only created=2026-10-06T07:38:09+00:00 -->
### d1-collect-adapter-github-only · decision · Triage collect moves onto the adapter, GitHub-only

Collect reads join the GhClient protocol; GitHub implements them, glab/tea raise UnsupportedForgeOperation (gh#611). No GitLab/Gitea triage.

<!-- fr:journal kind=decision scope=spec id=d2-isolation-injected-runner created=2026-10-06T07:38:09+00:00 -->
### d2-isolation-injected-runner · decision · Isolation lookups become adapter methods with an injected runner

default_branch / pr_for_branch on all three backends; isolation passes its Runner (network env + timeout), so its tests and timeouts are preserved.

<!-- fr:journal kind=decision scope=spec id=d3-client-for-url-and-gh-host created=2026-10-06T07:38:09+00:00 -->
### d3-client-for-url-and-gh-host · decision · Shared client_for_url helper, and RealGhClient honours host via GH_HOST

Promote pr_state's resolver to hostclient.client_for_url; thread host into the GitHub adapter so a GHE triage batch reaches its instance.

<!-- fr:journal kind=decision scope=spec id=d4-forge-error-kind created=2026-10-06T07:38:09+00:00 -->
### d4-forge-error-kind · decision · Bridge rate-limit classification via hostclient over every FORGE_ERRORS member

hostclient.forge_error_kind(exc); bridge_cli catches FORGE_ERRORS so glab/tea rate limits back off too.

<!-- fr:journal kind=decision scope=spec id=d5-skill-prose-neutral created=2026-10-06T07:38:09+00:00 -->
### d5-skill-prose-neutral · decision · Forge-neutral skill prose, no prose tripwire

fr-triage and fr-dispatch name operations with "on GitHub, `gh …`" examples; both mirror syncs run.

<!-- fr:journal kind=finding scope=spec id=sr-f1 created=2026-10-06T07:45:30+00:00 state=open review_scope=in -->
### sr-f1 · finding [open] (reviewer: in scope) · ClientForge cannot reuse the projected GhClient.view_issue

See spec-review-r1; reviewer tagged in scope.

<!-- fr:journal kind=finding scope=spec id=sr-f2 created=2026-10-06T07:45:30+00:00 state=open review_scope=in -->
### sr-f2 · finding [open] (reviewer: in scope) · GH_HOST contextvar misses view_pr_body and the new lookups

See spec-review-r1; reviewer tagged in scope.

<!-- fr:journal kind=finding scope=spec id=sr-f3 created=2026-10-06T07:45:30+00:00 state=open review_scope=in -->
### sr-f3 · finding [open] (reviewer: in scope) · test_isolation_network_timeouts patches local.detect_backend

See spec-review-r1; reviewer tagged in scope.

<!-- fr:journal kind=finding scope=spec id=sr-f4 created=2026-10-06T07:45:30+00:00 state=open review_scope=in -->
### sr-f4 · finding [open] (reviewer: in scope) · R6 widens client_for for every caller; test_hostclient warning test

See spec-review-r1; reviewer tagged in scope.

<!-- fr:journal kind=finding scope=spec id=sr-f5 created=2026-10-06T07:45:30+00:00 state=open review_scope=in -->
### sr-f5 · finding [open] (reviewer: in scope) · GhForge rename leaves make_forge, tests, AGENTS.md unnamed

See spec-review-r1; reviewer tagged in scope.

<!-- fr:journal kind=finding scope=spec id=sr-f6 created=2026-10-06T07:45:30+00:00 state=open review_scope=in -->
### sr-f6 · finding [open] (reviewer: in scope) · Test Plan lacks lookup, contextvar-leak and local.py argv items

See spec-review-r1; reviewer tagged in scope.

<!-- fr:journal kind=finding scope=spec id=sr-f7 created=2026-10-06T07:45:30+00:00 state=open review_scope=in -->
### sr-f7 · finding [open] (reviewer: in scope) · R8 vs §4.F cover different gh mentions

See spec-review-r1; reviewer tagged in scope.

<!-- fr:journal kind=finding scope=spec id=sr-f8 created=2026-10-06T07:45:30+00:00 state=open review_scope=in -->
### sr-f8 · finding [open] (reviewer: in scope) · 'mypy will name them' is false for test fakes

See spec-review-r1; reviewer tagged in scope.

<!-- fr:journal kind=review scope=spec id=spec-review-r1 created=2026-10-06T07:45:30+00:00 -->
### spec-review-r1 · review · independent spec review: 8 findings (sr-f1..sr-f8)

fr-spec-reviewer checked decisions d1-d5, every named file/line/helper, the callers and fakes the design touches, and internal consistency. Findings raised: sr-f1..sr-f8, all in scope.

<!-- fr:journal kind=finding scope=spec id=sr-f1-resolved created=2026-10-06T07:45:30+00:00 state=fixed resolves=sr-f1 -->
### sr-f1-resolved · finding [fixed] · resolves sr-f1: ClientForge cannot reuse the projected GhClient.view_issue

§4.A adds a new view_issue_record (raw ISSUE_VIEW_FIELDS record), stubbed on glab/tea; view_issue's contract untouched; R1 says so.

<!-- fr:journal kind=finding scope=spec id=sr-f2-resolved created=2026-10-06T07:45:30+00:00 state=fixed resolves=sr-f2 -->
### sr-f2-resolved · finding [fixed] · resolves sr-f2: GH_HOST contextvar misses view_pr_body and the new lookups

§4.E: one fr.gh._env() used by _run_gh AND view_pr_body, and by the GitHub adapter's default runner; R6 names all three; GH_HOST semantics stated per gh's docs; Test Plan 3 covers each path.

<!-- fr:journal kind=finding scope=spec id=sr-f3-resolved created=2026-10-06T07:45:30+00:00 state=fixed resolves=sr-f3 -->
### sr-f3-resolved · finding [fixed] · resolves sr-f3: test_isolation_network_timeouts patches local.detect_backend

§4.B names the test and re-points its patch at fr._hosts.detect_backend; §5's red-flag rule narrowed to assertion changes.

<!-- fr:journal kind=finding scope=spec id=sr-f4-resolved created=2026-10-06T07:45:30+00:00 state=fixed resolves=sr-f4 -->
### sr-f4-resolved · finding [fixed] · resolves sr-f4: R6 widens client_for for every caller; test_hostclient warning test

R6/§4.E: client_for threads only a DECLARED GitHub host (a derived/SSH-alias host never becomes GH_HOST); reach stated; Test Plan 5 rewrites test_hostclient.py:134.

<!-- fr:journal kind=finding scope=spec id=sr-f5-resolved created=2026-10-06T07:45:30+00:00 state=fixed resolves=sr-f5 -->
### sr-f5-resolved · finding [fixed] · resolves sr-f5: GhForge rename leaves make_forge, tests, AGENTS.md unnamed

§4.A names triage_cmd.make_forge, the three GhForge tests, the two docstrings and the AGENTS.md line; no alias.

<!-- fr:journal kind=finding scope=spec id=sr-f6-resolved created=2026-10-06T07:45:30+00:00 state=fixed resolves=sr-f6 -->
### sr-f6-resolved · finding [fixed] · resolves sr-f6: Test Plan lacks lookup, contextvar-leak and local.py argv items

Test Plan items 4, 6 and 7 added (per-backend lookups incl. run=None missing binary, contextvar reset, glab/tea argv scan of local.py).

<!-- fr:journal kind=finding scope=spec id=sr-f7-resolved created=2026-10-06T07:45:30+00:00 state=fixed resolves=sr-f7 -->
### sr-f7-resolved · finding [fixed] · resolves sr-f7: R8 vs §4.F cover different gh mentions

§4.F extended to fr-triage:49,112 and fr-dispatch:91; R8 states the one kept kind (fr-triage:96, a fact about the GitHub-only collector).

<!-- fr:journal kind=finding scope=spec id=sr-f8-resolved created=2026-10-06T07:45:30+00:00 state=fixed resolves=sr-f8 -->
### sr-f8-resolved · finding [fixed] · resolves sr-f8: 'mypy will name them' is false for test fakes

§5 rewritten: names tests/unit/fakes.py FakeGhClient, states mypy does not check tests, and when the plan adds methods to a fake.
