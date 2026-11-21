<!-- fr:journal-schema=4 -->
# Journal: 2026-11-21-release-app-hardening

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-21T11:34:23+00:00 input=true -->
### operator-brief · discovery · Operator brief, verbatim

Harden the release app's credential and ruleset bypass before its private key is stored, and automate the operator setup. Add a `security` lens.

Current state, checked 2026-11-20 in derio-net/super-fr:
- The operator ran `scripts/configure-main-protection.sh --stage bypass`. Repo variable FR_AUTOMATION_APP_ID=3994132 is set. Ruleset "protect main" (id 17365086) has rules [deletion, non_fast_forward] and bypass actor Integration 3994132 with bypass_mode "always".
- Secret FR_AUTOMATION_APP_KEY does not exist (`gh secret list` is empty). Because the variable is set, every release now fails at `publish` (`create-github-app-token`: "The 'private-key' input must be set to a non-empty string"; run 44683248617). Releases are blocked until this lands and the key is stored.
- `.github/workflows/release.yml:109-113` and `:298-302` mint the app token with `secrets.FR_AUTOMATION_APP_KEY` and use no `environment:`. A repo-level secret can be read by a workflow on any branch that anyone with push access pushes, so the key is not limited to code from `main`, despite what `docs/merge-protection.md` says.
- With bypass_mode "always" on the ruleset that holds deletion and non_fast_forward, a leaked key can force-push or delete `main`.
- `configure-main-protection.sh --stage bypass` sets the variable without checking that the secret exists. That is how releases got blocked.
- PR #1559 and issue #1580 listed only bypass → app release → require. They left out the runbook's steps 1–2 (install the app and generate the key; `gh secret set FR_AUTOMATION_APP_KEY`).

Asks:
1. Scope the key to a `release` environment whose deployment branch policy allows only `main`. Add `environment: release` to the two app-token jobs. A branch workflow must get no key.
2. Split the protection: one ruleset holds deletion + non_fast_forward with no bypass actors. A separate ruleset holds the required `ci-ok` check (the `require` stage), with the app as its only bypass actor. Migrate the existing "protect main" safely: never leave main unprotected between steps.
3. Write an idempotent, interactive operator script, run from the operator's own shell with their `gh`, that automates every step `gh` can do. Each step checks state first and is a no-op when already done. Every write is confirmed first. It has `--dry-run`. Steps: check the app installation and its permissions (contents and issues write only, this repo only); create or verify the environment and its branch policy; read the .pem path at a prompt, store it as the environment secret, and offer to delete the file; set FR_AUTOMATION_APP_ID last, only once the secret exists; then the ruleset stages. It must also handle the current half-done state (variable set, no secret, old combined ruleset). It must never print or log the key. Fold `configure-main-protection.sh` into it, or have it call that script, whichever is cleaner.
4. Detailed docs (`docs/merge-protection.md`) for the steps only the GitHub web UI can do: create the app if it is missing (exact permission settings), install it on the repo only, generate and download the private key, and revoke or rotate a leaked key. Also how to verify each step and how to roll back. Explain the security model: what the app can do, where the key lives, who can read it, and what a leak allows after this change.
5. Update #1580's steps in the PR body so the operator follows the new order.

Constraints: never change live repo settings, rulesets, variables or secrets yourself — the script is for the operator to run. Do not run the full suite on this host (it is loaded): run single test files only; CI is the suite evidence. Deliver a draft PR; never mark it ready or merge. Redact third-party identities.

<!-- fr:journal kind=decision scope=spec id=d-migration created=2026-11-21T11:34:23+00:00 decided_by=operator -->
### d-migration · decision · Keep "protect main", strip its bypass; the require step creates a new "require ci-ok" ruleset with check and app bypass in one write

Operator, round 1 question 1 (recommended option). Main's history rules are never touched, so main is never unprotected.

<!-- fr:journal kind=decision scope=spec id=d-tag-ruleset created=2026-11-21T11:34:23+00:00 decided_by=operator -->
### d-tag-ruleset · decision · Add a "protect release tags" ruleset on refs/tags/v* (deletion + update, no bypass)

Operator, round 1 question 2 (recommended option). A leaked key cannot move or delete a release tag; creation stays allowed.

<!-- fr:journal kind=decision scope=spec id=d-jwt-check created=2026-11-21T11:34:23+00:00 decided_by=operator -->
### d-jwt-check · decision · Prove the key belongs to the app with a locally signed JWT and GET /app before storing it

Operator, round 1 question 3 (recommended option). openssl is the only new dependency.

<!-- fr:journal kind=decision scope=spec id=d-environment created=2026-11-21T11:34:23+00:00 decided_by=operator -->
### d-environment · decision · release environment: main-only custom branch policy, can_admins_bypass false, no reviewers

Operator, round 1 question 4 (recommended option). Releases run unattended (push and daily cron).

<!-- fr:journal kind=decision scope=spec id=d-gate created=2026-11-21T11:34:23+00:00 decided_by=operator -->
### d-gate · decision · Gate tester, CI unit tests with a stub gh, one post-merge live row

Operator answered round 1 question 5 with gate devops. I then showed that fr ops apply runs only inside an ops-profile container (fr/ops/profile.py), which cannot see a host .pem or use the operator's own gh, and that adding an ops profile needs its own PR first. The operator chose option A in prose: gate tester, the script run from the operator's shell.

<!-- fr:journal kind=decision scope=spec id=d-merge-order created=2026-11-21T11:34:23+00:00 decided_by=operator -->
### d-merge-order · decision · Run the script from the PR branch before merging

Operator, round 1 question 6 (recommended option). The merge's own Release run then goes out as the app; require follows.

<!-- fr:journal kind=decision scope=spec id=d-fold-script created=2026-11-21T11:34:23+00:00 decided_by=operator -->
### d-fold-script · decision · Fold configure-main-protection.sh into one new bash script, scripts/setup-release-app.sh, and delete the old one

The operator delegated the choice. The stage semantics change (no bypass stage), so calling the old script would keep a shape that is now wrong. bash + jq + gh keeps the stub-gh test pattern.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-21T11:34:23+00:00 lens=security step=brainstorm -->
### lens-security-1 · lens · Operator asked for it: the change handles a GitHub App private key, a JWT, environment secrets and ruleset bypasses

<!-- fr:journal kind=finding scope=spec id=spr-r1 created=2026-11-21T11:42:24+00:00 state=open review_scope=in -->
### spr-r1 · finding [open] (reviewer: in scope) · R6's repo-list read through gh's OAuth token always fails, so the manual confirm becomes the only path

target: spec
GET /user/installations/{id}/repositories needs a GitHub App user access token; gh holds an OAuth app token.

<!-- fr:journal kind=finding scope=spec id=spr-r2 created=2026-11-21T11:42:24+00:00 state=open review_scope=in -->
### spr-r2 · finding [open] (reviewer: in scope) · Security model claims code reaches main only through a reviewed PR, but no ruleset requires a PR

target: spec
Anyone with write access can push a job naming the environment to main.

<!-- fr:journal kind=finding scope=spec id=spr-r3 created=2026-11-21T11:42:24+00:00 state=open review_scope=in -->
### spr-r3 · finding [open] (reviewer: in scope) · Running the script before merge leaves releases failing until the merge and undoes the preflight unset in the same run

target: spec
main's release.yml reads no environment secret until this PR merges.

<!-- fr:journal kind=finding scope=spec id=spr-r4 created=2026-11-21T11:42:24+00:00 state=open review_scope=in -->
### spr-r4 · finding [open] (reviewer: in scope) · R5's 'a declined write stops the script' conflicts with the optional offers

target: spec
Declining the .pem delete would stop the run.

<!-- fr:journal kind=finding scope=spec id=spr-r5 created=2026-11-21T11:42:24+00:00 state=open review_scope=in -->
### spr-r5 · finding [open] (reviewer: in scope) · With the old script's required check on 'protect main', stripping the bypass first blocks the release require waits for

target: spec
The app's release push would be refused.

<!-- fr:journal kind=finding scope=spec id=spr-r6 created=2026-11-21T11:42:24+00:00 state=open review_scope=in -->
### spr-r6 · finding [open] (reviewer: in scope) · The environment pin covers only release.yml; any other workflow on main could name environment: release

target: spec
pull_request_target/workflow_run/issue_comment jobs run main's code on outsider input.

<!-- fr:journal kind=finding scope=spec id=spr-r7 created=2026-11-21T11:42:24+00:00 state=open review_scope=in -->
### spr-r7 · finding [open] (reviewer: in scope) · release.py's protection hint still names the protect main bypass list after the split

target: plan
The hint would tell the operator to undo R12.

<!-- fr:journal kind=finding scope=spec id=spr-r8 created=2026-11-21T11:42:24+00:00 state=open review_scope=in -->
### spr-r8 · finding [open] (reviewer: in scope) · Phase files omit three pages fr docs check flags once scripts/release.py changes

target: plan
docs/exit-gates-release-walk.md, docs/explainers/fr-exit-gates.md, docs/explainers/index.md cover scripts/release.py.

<!-- fr:journal kind=finding scope=spec id=spr-r9 created=2026-11-21T11:42:24+00:00 state=open review_scope=in -->
### spr-r9 · finding [open] (reviewer: in scope) · A live plan's manual phase still tells the operator to run the deleted script

target: plan
local-suite-cost 04.yaml P4.T1.S1/S2.

<!-- fr:journal kind=finding scope=spec id=spr-r10 created=2026-11-21T11:42:24+00:00 state=open review_scope=in -->
### spr-r10 · finding [open] (reviewer: in scope) · Tasks 2, 3, 4 and 6 had no REFACTOR step or reason

target: plan
TDD shape.

<!-- fr:journal kind=finding scope=spec id=spr-r11 created=2026-11-21T11:42:24+00:00 state=open review_scope=in -->
### spr-r11 · finding [open] (reviewer: in scope) · No test pins R4's fixed step order

target: plan
Row setup-script-idempotent-confirmed cites R4.

<!-- fr:journal kind=review scope=spec id=spec-plan-review-1 created=2026-11-21T11:42:24+00:00 -->
### spec-plan-review-1 · review · independent spec+plan review: 11 findings, all in scope

findings: spr-r1 to spr-r6 (spec), spr-r7 to spr-r11 (plan); all fixed in the spec and plan. Decisions d-* each followed.

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-21T11:42:24+00:00 lens=tests step=spec-plan-review -->
### lens-tests-1 · lens · The script's safety claims (no key in argv or logs, dry-run and declined prompts write nothing, write order) rest on stub gh/curl tests, so their fidelity matters

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-21T11:42:24+00:00 lens=errors step=spec-plan-review -->
### lens-errors-1 · lens · The script runs under set -euo pipefail against gh calls that answer 404/403 by design; a misread exit could skip or half-run a step

<!-- fr:journal kind=finding scope=spec id=spr-r1-resolved created=2026-11-21T11:42:24+00:00 state=fixed resolves=spr-r1 -->
### spr-r1-resolved · finding [fixed] · resolves spr-r1: R6's repo-list read through gh's OAuth token always fails, so the manual confirm becomes the only path

R8 now checks the repo list with the app's own installation token (minted from the JWT, revoked on every exit path); R6 drops the list read; R9 covers the token; with no key at hand the confirm prompt stays.

<!-- fr:journal kind=finding scope=spec id=spr-r2-resolved created=2026-11-21T11:42:24+00:00 state=fixed resolves=spr-r2 -->
### spr-r2-resolved · finding [fixed] · resolves spr-r2: Security model claims code reaches main only through a reviewed PR, but no ruleset requires a PR

Security model's 'who can read it' now says every user with write access and admins; a PR rule is named as a separate decision.

<!-- fr:journal kind=finding scope=spec id=spr-r3-resolved created=2026-11-21T11:42:24+00:00 state=fixed resolves=spr-r3 -->
### spr-r3-resolved · finding [fixed] · resolves spr-r3: Running the script before merge leaves releases failing until the merge and undoes the preflight unset in the same run

R11: the variable step also waits until main's release.yml declares environment: release (read via gh api contents?ref=main); the unset offer now states the window; Test Plan says to decline it so the merge's release goes as the app.

<!-- fr:journal kind=finding scope=spec id=spr-r4-resolved created=2026-11-21T11:42:24+00:00 state=fixed resolves=spr-r4 -->
### spr-r4-resolved · finding [fixed] · resolves spr-r4: R5's 'a declined write stops the script' conflicts with the optional offers

R5 now separates step writes (declined stops) from offers (preflight unset, .pem delete, repo-secret delete; declined continues); plan T2 tests pin both.

<!-- fr:journal kind=finding scope=spec id=spr-r5-resolved created=2026-11-21T11:42:24+00:00 state=fixed resolves=spr-r5 -->
### spr-r5-resolved · finding [fixed] · resolves spr-r5: With the old script's required check on 'protect main', stripping the bypass first blocks the release require waits for

R12 defers the history step while protect main holds required_status_checks; R14 creates require ci-ok first, then removes the check and the bypass from protect main in one write; T7 tests it.

<!-- fr:journal kind=finding scope=spec id=spr-r6-resolved created=2026-11-21T11:42:24+00:00 state=fixed resolves=spr-r6 -->
### spr-r6-resolved · finding [fixed] · resolves spr-r6: The environment pin covers only release.yml; any other workflow on main could name environment: release

R1 now covers every file under .github/workflows/; T1.S1 adds the tripwire.

<!-- fr:journal kind=finding scope=spec id=spr-r7-resolved created=2026-11-21T11:42:24+00:00 state=fixed resolves=spr-r7 -->
### spr-r7-resolved · finding [fixed] · resolves spr-r7: release.py's protection hint still names the protect main bypass list after the split

T1.S3 rewords the hint to the require ci-ok ruleset and fixes the comment near line 111.

<!-- fr:journal kind=finding scope=spec id=spr-r8-resolved created=2026-11-21T11:42:24+00:00 state=fixed resolves=spr-r8 -->
### spr-r8-resolved · finding [fixed] · resolves spr-r8: Phase files omit three pages fr docs check flags once scripts/release.py changes

Added to files:, and T8.S2 stamps or edits them and runs fr docs check.

<!-- fr:journal kind=finding scope=spec id=spr-r9-resolved created=2026-11-21T11:42:24+00:00 state=fixed resolves=spr-r9 -->
### spr-r9-resolved · finding [fixed] · resolves spr-r9: A live plan's manual phase still tells the operator to run the deleted script

04.yaml added to files:; T8.S2 rewrites those steps.

<!-- fr:journal kind=finding scope=spec id=spr-r10-resolved created=2026-11-21T11:42:24+00:00 state=fixed resolves=spr-r10 -->
### spr-r10-resolved · finding [fixed] · resolves spr-r10: Tasks 2, 3, 4 and 6 had no REFACTOR step or reason

Each now has an S3 REFACTOR step (or a recorded refactor: reason).

<!-- fr:journal kind=finding scope=spec id=spr-r11-resolved created=2026-11-21T11:42:24+00:00 state=fixed resolves=spr-r11 -->
### spr-r11-resolved · finding [fixed] · resolves spr-r11: No test pins R4's fixed step order

T2.S1's dry-run test asserts the step order; T7.S3's end-to-end test asserts the write order.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-21T11:42:25+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  release-app-setup-live: tester
  release-key-environment-scoped: none
  setup-script-app-check: none
  setup-script-environment: none
  setup-script-idempotent-confirmed: none
  setup-script-key-never-printed: none
  setup-script-rulesets: none
  setup-script-variable-last: none
row_kinds:
  release-app-setup-live: live
  release-key-environment-scoped: none
  setup-script-app-check: none
  setup-script-environment: none
  setup-script-idempotent-confirmed: none
  setup-script-key-never-printed: none
  setup-script-rulesets: none
  setup-script-variable-last: none
run_gate: tester
run_kind: candidate
```
