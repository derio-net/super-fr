<!-- fr:journal-schema=4 -->
# Journal: 2026-11-18-consumer-delivery

<!-- fr:journal kind=discovery scope=plan id=p1-bun-flaky-under-load created=2026-11-18T16:03:17+00:00 phase=1 -->
### p1-bun-flaky-under-load · discovery · bun timing tests time out on a loaded host (phase 1)

marker relative-PATH, pin registration and quiet-placement tests failed only while pytest ran in parallel; green alone (host load average above 30).

<!-- fr:journal kind=decision scope=plan id=p1-rule-list-env-var created=2026-11-18T16:03:17+00:00 phase=1 -->
### p1-rule-list-env-var · decision · install.sh hands the rule list to the delivery as FR_OPENCODE_RULES (phase 1)

One space-separated env var keeps the positional contract (install <dir>) that every caller and test uses; the list stays defined once, in CLAUDE_RULES.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-18T16:03:17+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

smoke and change fragment only, no code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-18T16:03:17+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

docs and acceptance bookkeeping, no code to clean

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-18T16:16:49+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · install.sh's refusal line still says fix cli.json, wrong for the new missing-rule refusal (phase 1)

scripts/install.sh:1024-1025. Fixed: the second line now says fix what the message above names (cli.json, or a missing rule file).

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-18T16:16:49+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · FR_OPENCODE_RULES expanded unquoted (globbing) and rule names not validated (phase 1)

scripts/deliver-opencode-plugin.sh:127,138. Fixed: one `read -r -a` into an array, every name must match ^[A-Za-z0-9._-]+\.md$ and not start with a dot, checked before any write; parametrised refusal test.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-18T16:16:49+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · De-dup by exact text gives two copies of a rule under version skew with opencode.json instructions (phase 1)

packages/fr-opencode-plugin/src/rules.ts:60. Fixed: a part whose `Instructions from: <path>/<file>` header names the same rule file also counts as present; tests for skew and for a same-suffix different file.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-18T16:16:49+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · Unreadable-file test passes as root and does not prove the skip (phase 1)

packages/fr-opencode-plugin/test/rules.test.ts:61-74. Fixed: a readFile seam throws for bad.md; the test asserts exactly ["OK"].

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-11-18T16:16:49+00:00 phase=1 -->
### review-phase-1 · review · phase 1 review: approve with 4 minor in-scope findings, all fixed (phase 1)

Independent reviewer (separate context) checked R1-R7, the three de-dup cases, lookup counts and fallbacks; bun test 320/0 and tsc clean at review. Findings p1-r1..p1-r4 (all in scope, minor) fixed with tests; after the fixes bun test 322/0, tsc clean, 32 pytest pass. Declined-to-judge items were outside the phase (live OpenCode semantics owed to Test Plan 1).

<!-- fr:journal kind=lens scope=plan id=lens-security-1 created=2026-11-18T16:16:49+00:00 phase=1 lens=security step=review-phase -->
### lens-security-1 · lens · the installer copies files named by an env var; check every installer input together (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-18T16:16:49+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: install.sh's refusal line still says fix cli.json, wrong for the new missing-rule refusal (phase 1)

Neutral remedy line in install.sh.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-18T16:16:49+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: FR_OPENCODE_RULES expanded unquoted (globbing) and rule names not validated (phase 1)

Array read plus name validation before any write; refusal tests.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-18T16:16:49+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: De-dup by exact text gives two copies of a rule under version skew with opencode.json instructions (phase 1)

Header-name de-dup in rules.ts with tests.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-18T16:16:49+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: Unreadable-file test passes as root and does not prove the skip (phase 1)

readFile seam; exact assertion.

<!-- fr:journal kind=decision scope=plan id=p2-render-resolves-pin-by-default created=2026-11-18T17:01:33+00:00 phase=2 -->
### p2-render-resolves-pin-by-default · decision · render_workflow/init/refresh_ci resolve the running fr's release pin when none is passed (phase 2)

Callers (the command layer, tests) may pass fr_pin; otherwise the module resolves through fr.acceptance.pin.default_ls_remote. An autouse conftest fixture replaces that reader so no test reaches the network. Golden tests pass an explicit pin so releases do not move them.

<!-- fr:journal kind=decision scope=plan id=p2-ci-cli-install-no-sudo created=2026-11-18T17:01:33+00:00 phase=2 -->
### p2-ci-cli-install-no-sudo · decision · CI installs of tea and glab go to $HOME/.local/bin, not /usr/local/bin via sudo (phase 2)

A CI job has no sudo. The snippet reads version, URLs and sha256 from isolation/scaffold.py's HOST_CLI_PINS; Gitea adds the directory to GITHUB_PATH because its steps do not share a shell.

<!-- fr:journal kind=discovery scope=plan id=p2-gitea-pins-lightweight-tags created=2026-11-18T17:01:33+00:00 phase=2 -->
### p2-gitea-pins-lightweight-tags · discovery · Gitea pins: checkout v4.4.0, setup-uv v5.4.2, upload-artifact v4.6.2 are lightweight tags (phase 2)

git ls-remote shows no peeled line for them, so the tag line is the commit SHA.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-18T17:01:33+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

pin module is new and small; render and read share one INSTALL_LINE/PIN_RE already (done in T3), nothing left to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-11-18T17:01:33+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

token pick and env header live in one helper (_remote_auth); nothing left to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t6 created=2026-11-18T17:01:33+00:00 phase=2 -->
### no-refactor-p2-t6 · discovery · no-refactor-because P2.T6 (phase 2)

docs and acceptance bookkeeping, no code to clean

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-18T17:42:21+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · acceptance-reports scenario now does a live ls-remote for the installed fr's tag; the release suite runs it at an untagged version (phase 2)

scaffold.py init via tests/scenarios/acceptance-reports-derived-published.sh. Fixed: the scenario sets a scratch HOME whose .gitconfig redirects super-fr's URL (insteadOf) to a local bare repo with an annotated v<version> tag, and asserts the pinned sha; no product override added.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-18T17:42:21+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · the autouse conftest stub means the real default_ls_remote is never tested (phase 2)

tests/conftest.py, pin.py. Fixed: unit tests drive the real default_ls_remote with subprocess.run patched (argv, no GIT_CONFIG_*, GIT_TERMINAL_PROMPT=0, timeout, FrPinError on non-zero exit and OSError).

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-18T17:42:21+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · Gitea tea login put the token on tea's command line (phase 2)

DEBT_STEP_GITEA. Fixed: GITEA_SERVER_URL and GITEA_SERVER_TOKEN via env (tea 0.14.2 reads both, verified with tea login add --help), `tea login add --name fr-ci`; test asserts no token on the run line.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-18T17:42:21+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · CLI refusal test asserted only that the output contains 'v' (phase 2)

test_acceptance_pin.py. Fixed: asserts the running version's tag and the nothing-was-written wording.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-18T17:42:21+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · refresh_ci and init resolved the pin before the foreign/paste/already-exists outcomes (phase 2)

scaffold.py refresh_ci, init. Fixed: foreign check first; init resolves only when the workflow is missing; paste and rewrite/current still resolve (they render the install line), commented; tests for each outcome with a failing resolver.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-11-18T17:42:21+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · GitLab FR_DEBT_TOKEN check ran after three downloads (phase 2)

DEBT_STEP_GITLAB. Fixed: first before_script line; test asserts the order.

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-11-18T17:42:21+00:00 phase=2 state=open review_scope=in -->
### p2-r7 · finding [open] (reviewer: in scope) · acceptance-matrix reference omitted --refresh-ci's refusal and the GH_TOKEN fallback (phase 2)

docs/reference/acceptance-matrix.md. Fixed; fr docs check clean.

<!-- fr:journal kind=finding scope=plan id=p2-r8 created=2026-11-18T17:42:21+00:00 phase=2 state=open review_scope=out -->
### p2-r8 · finding [open] (reviewer: out of scope) · Gitea matrix job checkout persists gitea.token for PR code (phase 2)

Pre-existing in the Gitea matrix job; R12 names only the debt job.

<!-- fr:journal kind=review scope=plan id=review-phase-2 created=2026-11-18T17:42:21+00:00 phase=2 -->
### review-phase-2 · review · phase 2 review: 8 findings (7 in scope, all fixed; 1 out of scope) (phase 2)

Independent reviewer verified every ACTION_PINS sha against its tag with git ls-remote, the pin's peeled-tag preference live, the byte-identical refusal, user-info stripping and token redaction. It raised p2-r1 (critical: release suite would fail at an untagged version) through p2-r7, all fixed with tests and pushed; p2-r8 is out of scope (pre-existing).

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-18T17:42:21+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: acceptance-reports scenario now does a live ls-remote for the installed fr's tag; the release suite runs it at an untagged version (phase 2)

Hermetic scenario via scoped HOME .gitconfig insteadOf to a local tagged bare repo.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-18T17:42:21+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: the autouse conftest stub means the real default_ls_remote is never tested (phase 2)

Real default_ls_remote unit-tested with subprocess patched.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-18T17:42:21+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: Gitea tea login put the token on tea's command line (phase 2)

tea login reads URL and token from env.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-18T17:42:21+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: CLI refusal test asserted only that the output contains 'v' (phase 2)

Exact tag and wording asserted.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-18T17:42:21+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: refresh_ci and init resolved the pin before the foreign/paste/already-exists outcomes (phase 2)

Pin resolved only when used, still before any write.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-11-18T17:42:21+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: GitLab FR_DEBT_TOKEN check ran after three downloads (phase 2)

Token check first in before_script.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-11-18T17:42:21+00:00 phase=2 state=fixed resolves=p2-r7 -->
### p2-r7-resolved · finding [fixed] · resolves p2-r7: acceptance-matrix reference omitted --refresh-ci's refusal and the GH_TOKEN fallback (phase 2)

Reference page updated.

<!-- fr:journal kind=finding scope=plan id=p2-r8-resolved created=2026-11-18T17:42:21+00:00 phase=2 state=open resolves=p2-r8 out_of_scope=true -->
### p2-r8-resolved · finding [out-of-scope] · resolves p2-r8: Gitea matrix job checkout persists gitea.token for PR code (phase 2)

Predates this change: the Gitea matrix job's checkout was not touched by R8-R13, and R12 scopes credentials to the debt job. Filed at deliver as a follow-up.
