<!-- fr:journal-schema=4 -->
# Journal: 2026-11-21-release-app-hardening

<!-- fr:journal kind=discovery scope=plan id=setup-script-test-stub-shell-gotchas created=2026-11-21T12:15:43+00:00 phase=1 -->
### setup-script-test-stub-shell-gotchas · discovery · Stub gh in tests: positional-parameter pattern removal and here-string temp files (phase 1)

In the stub, `${*##*/}` applies per positional parameter, so copy `$*` to a variable first. Write bodies are logged compacted (`jq -c`) so a multi-line body stays one log line.

<!-- fr:journal kind=decision scope=plan id=setup-script-require-waits-exit-0 created=2026-11-21T12:15:43+00:00 phase=1 -->
### setup-script-require-waits-exit-0 · decision · require step: a missing variable that step 4 already reported as waiting exits 0 (phase 1)

R14 exits 0 only for the release check. The Test Plan's pre-merge run reaches require with the variable still waiting for the merge, so that case prints the wait and exits 0. A missing environment secret, or a variable missing with no reported wait, still refuses (exit 1). With no key at hand the installation-repositories check is a printed settings URL rather than a blocking prompt, so a rerun with no stdin stays a no-op.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-21T12:15:43+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

read_json and the shared step helpers already served the app step; nothing else to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-21T12:15:43+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the environment body and its desired projection are constants compared with jq -S from the start

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-11-21T12:15:43+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

the variable step reuses read_json and act; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t8 created=2026-11-21T12:15:43+00:00 phase=1 -->
### no-refactor-p1-t8 · discovery · no-refactor-because P1.T8 (phase 1)

documentation only, no code to refactor

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-21T12:24:08+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · setup-release-app.sh env/repo secret checks turned any gh failure into 'absent' via && echo 1 || echo 0 (phase 1)

setup-release-app.sh env/repo secret checks turned any gh failure into 'absent' via && echo 1 || echo 0

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-21T12:24:08+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · R8 said the no-key path asks for a confirm; the code (rightly) only prints the settings URL (phase 1)

R8 said the no-key path asks for a confirm; the code (rightly) only prints the settings URL

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-21T12:24:08+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · --dry-run skipped the require step's variable wait and printed a POST a real run would not make (phase 1)

--dry-run skipped the require step's variable wait and printed a POST a real run would not make

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-21T12:24:08+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · The variable-never-set test only exercised the key step's early exit; tangled and/or assertion; R14's variable-wait exit 0 lacked spec wording (phase 1)

The variable-never-set test only exercised the key step's early exit; tangled and/or assertion; R14's variable-wait exit 0 lacked spec wording

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-21T12:24:08+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · HUP/QUIT untrapped; make_jwt under || ran with set -e off, so a signing failure became a misleading HTTP 401 (phase 1)

HUP/QUIT untrapped; make_jwt under || ran with set -e off, so a signing failure became a misleading HTTP 401

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-21T12:24:08+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · main_release_declares_env grep missed quoted/commented/mapping forms and accepted one job (phase 1)

main_release_declares_env grep missed quoted/commented/mapping forms and accepted one job

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-11-21T12:24:08+00:00 phase=1 state=open review_scope=out -->
### p1-r7 · finding [open] (reviewer: out of scope) · Earlier features' acceptance notes still name configure-main-protection (phase 1)

Earlier features' acceptance notes still name configure-main-protection

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-11-21T12:24:08+00:00 phase=1 -->
### p1-review-1 · review · phase 1 review: 7 findings (6 in scope, 1 out) (phase 1)

Reviewer read script, tests, docs, workflow and fragment against R1-R15. No critical findings; secret handling sound. p1-r1..p1-r6 fixed with tests; p1-r7 out of scope. Suggested lens live-api-fidelity is not an effective lens; the tests lens covers stub fidelity.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-21T12:24:08+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: setup-release-app.sh env/repo secret checks turned any gh failure into 'absent' via && echo 1 || echo 0 (phase 1)

secret_present runs in the caller's shell, stops with the gh error on any failure, and sets PRESENT from jq under set -e; test_a_failing_secret_list_stops_the_script_and_is_never_read_as_absent covers both lists.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-21T12:24:08+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: R8 said the no-key path asks for a confirm; the code (rightly) only prints the settings URL (phase 1)

Spec R8 reworded (tells the operator to confirm there; asks nothing, so a rerun stays non-interactive); the test renamed to test_an_existing_environment_secret_is_ok_and_points_at_the_installation_to_confirm and its row ref updated.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-21T12:24:08+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: --dry-run skipped the require step's variable wait and printed a POST a real run would not make (phase 1)

Dropped the dry-run condition; test_dry_run_require_waits_on_the_variable_like_a_real_run.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-21T12:24:08+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: The variable-never-set test only exercised the key step's early exit; tangled and/or assertion; R14's variable-wait exit 0 lacked spec wording (phase 1)

Added test_a_declined_key_store_never_sets_the_variable and linked it on setup-script-variable-last; untangled the half-done assertion; R14 now states that a waiting variable makes require wait (real run and dry-run). The guard in step_variable is defensive: no path reaches it without the secret.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-21T12:24:08+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: HUP/QUIT untrapped; make_jwt under || ran with set -e off, so a signing failure became a misleading HTTP 401 (phase 1)

Traps for HUP and QUIT added; make_jwt returns non-zero on every failed part or empty segment; test_a_key_openssl_cannot_sign_with_is_refused_before_any_curl_call.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-21T12:24:08+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: main_release_declares_env grep missed quoted/commented/mapping forms and accepted one job (phase 1)

An awk parse accepts the scalar form (quoted or not, trailing comment) and the mapping form's name:, and requires both prepare and publish; parametrised form test and test_the_variable_waits_while_only_one_app_token_job_declares_the_environment.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-11-21T12:24:08+00:00 phase=1 state=open resolves=p1-r7 out_of_scope=true -->
### p1-r7-resolved · finding [out-of-scope] · resolves p1-r7: Earlier features' acceptance notes still name configure-main-protection (phase 1)

Historical notes on rows earlier features merged: main-protection-script is retired by amendment here and ci-ok-required-on-main's note is amended in this feature's fragment; the original lines stay as the fold's history and are not caused by this change.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-21T12:36:09+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · release.py's reworded protection-refusal hint had no assertion on its new text

release.py's reworded protection-refusal hint had no assertion on its new text

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-21T12:36:09+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · No test of repairing an existing wrong require ci-ok or tag ruleset

No test of repairing an existing wrong require ci-ok or tag ruleset

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-21T12:36:09+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · Environment drift tested only for admin bypass and reviewers

Environment drift tested only for admin bypass and reviewers

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-21T12:36:09+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · No test that an interrupt revokes the token and removes the temp dir

No test that an interrupt revokes the token and removes the temp dir

<!-- fr:journal kind=finding scope=plan id=l-tests-r5 created=2026-11-21T12:36:09+00:00 state=open review_scope=out -->
### l-tests-r5 · finding [open] (reviewer: out of scope) · release.yml header test is substring-only

release.yml header test is substring-only

<!-- fr:journal kind=finding scope=plan id=l-tests-r6 created=2026-11-21T12:36:09+00:00 state=open review_scope=in -->
### l-tests-r6 · finding [open] (reviewer: in scope) · Newest-tag selection untested beyond pagination

Newest-tag selection untested beyond pagination

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-21T12:36:09+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · release_pushed_by_app read a gh failure as no release

release_pushed_by_app read a gh failure as no release

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-21T12:36:09+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · prove_key dropped GitHub's error message and openssl stderr

prove_key dropped GitHub's error message and openssl stderr

<!-- fr:journal kind=finding scope=plan id=l-errors-r3 created=2026-11-21T12:36:09+00:00 state=open review_scope=in -->
### l-errors-r3 · finding [open] (reviewer: in scope) · revoke_token ignored the DELETE result

revoke_token ignored the DELETE result

<!-- fr:journal kind=finding scope=plan id=l-errors-r4 created=2026-11-21T12:36:09+00:00 state=open review_scope=in -->
### l-errors-r4 · finding [open] (reviewer: in scope) · Installations read unpaginated; a user-owned repo got a bare 404

Installations read unpaginated; a user-owned repo got a bare 404

<!-- fr:journal kind=finding scope=plan id=l-errors-r5 created=2026-11-21T12:36:09+00:00 state=open review_scope=in -->
### l-errors-r5 · finding [open] (reviewer: in scope) · act turned EOF into declined; a failed confirmed write did not name the step

act turned EOF into declined; a failed confirmed write did not name the step

<!-- fr:journal kind=finding scope=plan id=l-errors-r6 created=2026-11-21T12:36:09+00:00 state=open review_scope=out -->
### l-errors-r6 · finding [open] (reviewer: out of scope) · environment: release fails generically on another ref or auto-creates an unprotected environment

environment: release fails generically on another ref or auto-creates an unprotected environment

<!-- fr:journal kind=finding scope=plan id=l-security-r1 created=2026-11-21T12:36:09+00:00 state=open review_scope=in -->
### l-security-r1 · finding [open] (reviewer: in scope) · A kept repository-level key ended the run with done and exit 0

A kept repository-level key ended the run with done and exit 0

<!-- fr:journal kind=finding scope=plan id=l-security-r2 created=2026-11-21T12:36:09+00:00 state=open review_scope=in -->
### l-security-r2 · finding [open] (reviewer: in scope) · With an existing env secret the installation's repository scope is not proven

With an existing env secret the installation's repository scope is not proven

<!-- fr:journal kind=finding scope=plan id=l-security-r3 created=2026-11-21T12:36:09+00:00 state=open review_scope=out -->
### l-security-r3 · finding [open] (reviewer: out of scope) · prove_key mints an installation token before any confirm

prove_key mints an installation token before any confirm

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-21T12:36:09+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · merge-protection.md implied the environment applies only in app mode

merge-protection.md implied the environment applies only in app mode

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-21T12:36:09+00:00 state=open review_scope=in -->
### l-docs-accuracy-r2 · finding [open] (reviewer: in scope) · Step 4 said the bypass is always removed from protect main

Step 4 said the bypass is always removed from protect main

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3 created=2026-11-21T12:36:09+00:00 state=open review_scope=in -->
### l-docs-accuracy-r3 · finding [open] (reviewer: in scope) · 'Write down the App ID' and an unconditional .pem prompt

'Write down the App ID' and an unconditional .pem prompt

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r4 created=2026-11-21T12:36:09+00:00 state=open review_scope=in -->
### l-docs-accuracy-r4 · finding [open] (reviewer: in scope) · Runbook step 5 said to rerun only if you unset the variable; a fresh adoption never set it

Runbook step 5 said to rerun only if you unset the variable; a fresh adoption never set it

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r5 created=2026-11-21T12:36:09+00:00 state=open review_scope=in -->
### l-docs-accuracy-r5 · finding [open] (reviewer: in scope) · 'Revoking the key ends all of it at once' ignored already-minted installation tokens

'Revoking the key ends all of it at once' ignored already-minted installation tokens

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-21T12:36:09+00:00 -->
### lens-review-1 · review · lens review: security, tests, errors, docs-accuracy; 20 findings (16 in scope, 4 out)

One reviewer per lens over the diff 396e444d..HEAD. All in-scope findings fixed with tests except l-security-r2, refuted against R8. docs-accuracy was re-dispatched (the first return named a file outside the feature's diff); its r4 and r5 are fixed and it confirmed r1-r3's fixes.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-21T12:36:09+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: release.py's reworded protection-refusal hint had no assertion on its new text

test_a_protection_refusal_fails_at_once_naming_the_bypass_actor now asserts the 'require ci-ok' ruleset, never on 'protect main', scripts/setup-release-app.sh, and no configure-main-protection.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-21T12:36:09+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: No test of repairing an existing wrong require ci-ok or tag ruleset

test_a_wrong_tag_ruleset_is_repaired_in_place and test_a_wrong_require_ruleset_is_repaired_in_place (not strict, pull_request bypass, a second actor, no ci-ok).

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-21T12:36:09+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: Environment drift tested only for admin bypass and reviewers

test_other_environment_drift_is_corrected covers a wait timer and a protected-branches policy.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-21T12:36:09+00:00 state=fixed resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [fixed] · resolves l-tests-r4: No test that an interrupt revokes the token and removes the temp dir

test_a_signal_mid_run_revokes_the_token_and_removes_the_temp_dir sends SIGTERM while the installation token is live.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5-resolved created=2026-11-21T12:36:09+00:00 state=open resolves=l-tests-r5 out_of_scope=true -->
### l-tests-r5-resolved · finding [out-of-scope] · resolves l-tests-r5: release.yml header test is substring-only

The style of the existing P3-R8 header tests; the structural R1 invariant is pinned by the environment and secret tripwires, so the header test adds wording only.

<!-- fr:journal kind=finding scope=plan id=l-tests-r6-resolved created=2026-11-21T12:36:09+00:00 state=fixed resolves=l-tests-r6 -->
### l-tests-r6-resolved · finding [fixed] · resolves l-tests-r6: Newest-tag selection untested beyond pagination

The script filters vX.Y.Z and vX.Y.Z-rc.N and ranks a final above its RCs; test_the_newest_release_tag_ignores_other_tags_and_ranks_a_final_above_its_rcs.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-21T12:36:09+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: release_pushed_by_app read a gh failure as no release

Explicit exits on a failed tags or runs read; test_a_failing_tags_read_stops_and_is_never_read_as_no_release.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-21T12:36:09+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: prove_key dropped GitHub's error message and openssl stderr

Refusals now show GitHub's message field (never any other field, never a success body) and openssl's first error line, plus a hint for 401; test_the_refusal_names_github_s_message_and_never_a_token and the BODYSECRET check.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3-resolved created=2026-11-21T12:36:09+00:00 state=fixed resolves=l-errors-r3 -->
### l-errors-r3-resolved · finding [fixed] · resolves l-errors-r3: revoke_token ignored the DELETE result

A non-204 revoke warns that the token stays valid until it expires; test_a_failed_revoke_is_reported.

<!-- fr:journal kind=finding scope=plan id=l-errors-r4-resolved created=2026-11-21T12:36:09+00:00 state=fixed resolves=l-errors-r4 -->
### l-errors-r4-resolved · finding [fixed] · resolves l-errors-r4: Installations read unpaginated; a user-owned repo got a bare 404

--paginate with per_page=100, merged pages; a 404 refuses with 'organisation-owned repos only'; two tests.

<!-- fr:journal kind=finding scope=plan id=l-errors-r5-resolved created=2026-11-21T12:36:09+00:00 state=fixed resolves=l-errors-r5 -->
### l-errors-r5-resolved · finding [fixed] · resolves l-errors-r5: act turned EOF into declined; a failed confirmed write did not name the step

EOF says 'no answer (stdin closed)'; a failed write names itself and says earlier writes stay applied and a rerun reads state first; two tests. It also exposed a test that passed only because the half-done offer consumed its answer, now fixed.

<!-- fr:journal kind=finding scope=plan id=l-errors-r6-resolved created=2026-11-21T12:36:09+00:00 state=open resolves=l-errors-r6 out_of_scope=true -->
### l-errors-r6-resolved · finding [out-of-scope] · resolves l-errors-r6: environment: release fails generically on another ref or auto-creates an unprotected environment

GitHub's behaviour, not a defect of the diff; docs/merge-protection.md now explains both cases (l-docs-accuracy-r1).

<!-- fr:journal kind=finding scope=plan id=l-security-r1-resolved created=2026-11-21T12:36:09+00:00 state=fixed resolves=l-security-r1 -->
### l-security-r1-resolved · finding [fixed] · resolves l-security-r1: A kept repository-level key ended the run with done and exit 0

Declining that offer now ends the run 'incomplete' with exit 1; test_a_kept_repository_secret_leaves_the_setup_incomplete and test_a_declined_offer_continues.

<!-- fr:journal kind=finding scope=plan id=l-security-r2-resolved created=2026-11-21T12:36:09+00:00 state=refuted resolves=l-security-r2 -->
### l-security-r2-resolved · finding [refuted] · resolves l-security-r2: With an existing env secret the installation's repository scope is not proven

Spec R8 (reworded after phase review p1-r2) decides this: gh's OAuth token cannot read the list, and only the key can. Every key this script stores is proven before it is stored, and --rotate-key proves it again. The run now says in its summary that the list was not proven (test_a_run_without_the_key_says_the_repository_list_was_not_proven).

<!-- fr:journal kind=finding scope=plan id=l-security-r3-resolved created=2026-11-21T12:36:09+00:00 state=open resolves=l-security-r3 out_of_scope=true -->
### l-security-r3-resolved · finding [out-of-scope] · resolves l-security-r3: prove_key mints an installation token before any confirm

A read-equivalent proof: the token is scoped to this repo and revoked at once; minting it is part of the check R8 requires, not a settings write.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-21T12:36:09+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: merge-protection.md implied the environment applies only in app mode

New paragraph: both jobs declare the environment in both modes; a main-only environment limits GITHUB_TOKEN-mode runs too; a missing environment is auto-created without a policy.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-21T12:36:09+00:00 state=fixed resolves=l-docs-accuracy-r2 -->
### l-docs-accuracy-r2-resolved · finding [fixed] · resolves l-docs-accuracy-r2: Step 4 said the bypass is always removed from protect main

Step 4 now names the deferral while protect main holds the old ci-ok rule.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3-resolved created=2026-11-21T12:36:09+00:00 state=fixed resolves=l-docs-accuracy-r3 -->
### l-docs-accuracy-r3-resolved · finding [fixed] · resolves l-docs-accuracy-r3: 'Write down the App ID' and an unconditional .pem prompt

The App ID note says the script reads it; the .pem prompt is conditional on no env secret or --rotate-key.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r4-resolved created=2026-11-21T12:36:09+00:00 state=fixed resolves=l-docs-accuracy-r4 -->
### l-docs-accuracy-r4-resolved · finding [fixed] · resolves l-docs-accuracy-r4: Runbook step 5 said to rerun only if you unset the variable; a fresh adoption never set it

Step 5 (and the spec's Test Plan step 3) now say to rerun the script after the merge whenever the variable is not set.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r5-resolved created=2026-11-21T12:36:09+00:00 state=fixed resolves=l-docs-accuracy-r5 -->
### l-docs-accuracy-r5-resolved · finding [fixed] · resolves l-docs-accuracy-r5: 'Revoking the key ends all of it at once' ignored already-minted installation tokens

The security model and the revoke steps (page and spec) now say deleting the key stops new tokens at once, and a minted token stays valid for at most 1 hour.
