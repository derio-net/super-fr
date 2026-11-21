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
