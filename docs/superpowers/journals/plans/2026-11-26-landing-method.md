<!-- fr:journal-schema=4 -->
# Journal: 2026-11-26-landing-method

<!-- fr:journal kind=decision scope=plan id=landing-hold-budget created=2026-11-26T13:51:43+00:00 phase=1 -->
### landing-hold-budget · decision · triage_batch_cmd.py module budget moved from 8225 to 8250 (phase 1)

_landing_hold (about 20 lines) must sit in the driver because it calls merge_ctx; the pure parts (landing_refusal, REBASE_WARNING) live in queue_exec.py. The budget stays within 400 lines of the module.

<!-- fr:journal kind=discovery scope=plan id=batch-merge-method-hold-exit created=2026-11-26T13:51:43+00:00 phase=1 -->
### batch-merge-method-hold-exit · discovery · batch merge --method with a disallowed method now exits 1 with queue-held, not 2 (phase 1)

R2 makes an unchoosable method a held plan instead of a raise, so test_batch_merge_uses_the_method_it_is_given_or_the_repos_default now expects exit 1 and the held reason.

<!-- fr:journal kind=discovery scope=plan id=writing-standard-unchecked created=2026-11-26T13:51:43+00:00 phase=1 -->
### writing-standard-unchecked · discovery · the writing-standard check of the edited pages was not run locally (phase 1)

scripts/check-writing-standards.sh needs a pinned blog-craft checkout; CI's site-build job runs it. Edited pages: fr-wave-driver.md, fr-exit-gates.md (plain-language), cloud-setup.md, merge-protection.md (ste).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-26T13:51:43+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

land_push's refspec loop is now one line; nothing more to clean beyond the shared landing_refusal

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-26T13:51:43+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the cloud check reuses choose_method_source and landing_refusal; the queue block reader is a sibling of the merge_method reader, nothing to merge further

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-26T13:51:43+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

logged_prs is now a thin wrapper over logged_pr_dates; nothing else to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-26T13:51:43+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

docs and config only; stamps follow the page text

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-26T13:57:14+00:00 phase=1 state=open review_scope=out -->
### p1-r1 · finding [open] (reviewer: out of scope) · batch merge --method <disallowed> now exits 1 as queue-held rather than 2 (phase 1)

Reviewer tag: out. This change causes it (_landing_hold at triage_batch_cmd.py:7079 turns the ConfigError into a hold, test_triage_batch_merge.py:188). Spec R2 states it (a method that cannot be chosen holds the queue with the error's text and never raises), so the behaviour stays; the fix is to say so in the PR body.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-26T13:57:14+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · BUDGETS comment does not record the landing-method reason for triage_batch_cmd.py 8225->8250 (phase 1)

tests/unit/test_tripwire_module_budget.py:24; only the plan journal (landing-hold-budget) recorded it.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-26T13:57:14+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · Unrelated scripts/floors.py:75 except-clause reformat rides along; choose_method wrapper is now test-only (phase 1)

ruff format over scripts/ rewrote `except (A, B, C):` to the py3.14 bare form; CI lints only packages/ and tests/. The choose_method wrapper at batch_merge.py:138 is kept by the spec's design (R1: callers unchanged, a thin first-element wrapper).

<!-- fr:journal kind=review scope=plan id=review-p1-1 created=2026-11-26T13:57:14+00:00 phase=1 -->
### review-p1-1 · review · independent code review of phase 1: 3 findings, no correctness defects (phase 1)

Reviewer checked R1-R9 against the diff from ff14a97ae, ran the unit set (328 passed) and the queue integration files with -m "" (42 passed), and fr acceptance check (772 rows OK). Findings p1-r1 (exit 2 -> 1 for a disallowed --method, kept per R2, called out in the PR body), p1-r2 (budget comment, fixed), p1-r3 (unrelated floors.py reformat, reverted; wrapper kept by design).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-26T13:57:14+00:00 phase=1 state=refuted resolves=p1-r1 -->
### p1-r1-resolved · finding [refuted] · resolves p1-r1: batch merge --method <disallowed> now exits 1 as queue-held rather than 2 (phase 1)

Not a defect: spec R2 specifies that a method that cannot be chosen holds the queue (exit 1) and never raises, the same as every other queue hold. Nothing to change in code; the PR body's summary names the exit change for `fr triage batch merge --method <disallowed>`.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-26T13:57:14+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: BUDGETS comment does not record the landing-method reason for triage_batch_cmd.py 8225->8250 (phase 1)

BUDGETS comment now names landing-method's +25 and why (ef590a7 amended).

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-26T13:57:14+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: Unrelated scripts/floors.py:75 except-clause reformat rides along; choose_method wrapper is now test-only (phase 1)

scripts/floors.py restored to origin/main's bytes (ruff check passes); choose_method stays as the spec's thin wrapper.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-26T14:10:02+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · _landing_hold labels every ForgeReadError (incl. code-2 config-moved) as a transient merge-methods read

triage_batch_cmd.py _landing_hold's except (ForgeReadError, TransientPassFailure) branch; merge_ctx raises ForgeReadError(code=2) when main's config moved under the pass.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-26T14:10:02+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · release._closed_unmerged swallows the gh pr view failure or JSON error, so GateStateUnknownError cannot say why

scripts/release.py _closed_unmerged returned None with no reason on non-zero exit, bad JSON or another state.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-26T14:10:02+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · test_a_configured_merge_method_lifts_the_hold would pass if the queue did nothing

tests/unit/test_triage_batch_drive_cmd.py: asserted only the exit code and 'unmerged' absent.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-26T14:10:02+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · Held-queue drive tests match 'held' loosely, run dry only, and never check that nothing was built or landed

tests/unit/test_triage_batch_drive_cmd.py squash-default, squash-only and no-choosable-method tests.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-26T14:10:02+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · land_push's parents check: the multi-entry prev chain is untested and the old not-built-on-base proof may be shadowed

tests/integration/test_queue_land.py; queue_exec.py land_push prev loop.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-26T14:10:02+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · _closed_unmerged lacks tests for MERGED, CLOSED with mergedAt, and invalid JSON

tests/unit/test_release_script.py R7 tests.

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-26T14:10:02+00:00 -->
### lens-review-1 · review · lens review: docs-accuracy (none), errors (2), tests (4) — all fixed

docs-accuracy found no false claims (two optional wording points, applied to docs/merge-protection.md and docs/explainers/fr-exit-gates.md). errors: l-errors-r1, l-errors-r2. tests: l-tests-r1..r4. All six fixed in bf5e42474 and ab5805cae; drive, release, budget, queue_exec, merge and cloud-remedy unit files re-run green (606 passed), queue integration files green (44 passed).

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-26T14:10:02+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: _landing_hold labels every ForgeReadError (incl. code-2 config-moved) as a transient merge-methods read

merge_read_hold (queue_exec.py) keeps the read-again wording only for TransientPassFailure and ForgeReadError code 1; any other code says 'the merge context could not be built'. Test: test_triage_batch_drive_cmd.py::test_a_moved_config_holds_the_pass_without_promising_a_retry.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-26T14:10:02+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: release._closed_unmerged swallows the gh pr view failure or JSON error, so GateStateUnknownError cannot say why

_closed_unmerged returns the landed PR or a reason; waiting_prs names it per PR ('misses #1704 (gh pr view failed: boom)'). Test: test_release_script.py::test_r7_a_pr_the_log_names_and_the_view_does_not_confirm_is_missing_with_its_reason.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-26T14:10:02+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: test_a_configured_merge_method_lifts_the_hold would pass if the queue did nothing

Asserts no queue-held text and that a queue-open/queue-build action was planned (_opened(world)).

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-26T14:10:02+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: Held-queue drive tests match 'held' loosely, run dry only, and never check that nothing was built or landed

Exact queue-held assertion; queue_plans == [] and merged == [] in all three; new test_a_push_queue_on_a_squash_default_with_yes_is_held_and_moves_nothing.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-26T14:10:02+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: land_push's parents check: the multi-entry prev chain is untested and the old not-built-on-base proof may be shadowed

New test_a_chain_whose_second_commit_does_not_follow_the_first_is_held and test_a_correctly_built_chain_on_a_moved_base_is_held_as_not_built_on_the_base (reaches the old p3-r7 reason); the bottom-built-elsewhere test asserts the second-parent reason it now reaches.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-26T14:10:02+00:00 state=fixed resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [fixed] · resolves l-tests-r4: _closed_unmerged lacks tests for MERGED, CLOSED with mergedAt, and invalid JSON

Parametrized over OPEN, MERGED, CLOSED with mergedAt, invalid JSON and a failing view; each names #1704 and its reason.
