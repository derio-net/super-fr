<!-- fr:journal-schema=4 -->
# Journal: 2026-11-25-wave-plan-file-overlap

<!-- fr:journal kind=decision scope=plan id=plan-overlap-one-paragraph created=2026-11-25T15:44:18+00:00 phase=1 -->
### plan-overlap-one-paragraph · decision · A card's overlap sentences render as one paragraph (phase 1)

The spec asks for one `<p class="overlap">` per card detail, so a card in several overlaps joins its sentences with spaces inside that one paragraph, instead of one paragraph per overlap.

<!-- fr:journal kind=discovery scope=plan id=plan-overlap-checkout-paths-optional created=2026-11-25T15:44:18+00:00 phase=1 -->
### plan-overlap-checkout-paths-optional · discovery · The driver's checkout map holds optional paths (phase 1)

`checkout_paths` is `dict[str, Path | None]`, so `write_board` and `source_for_clones` take `Mapping[str, Path | None]`; a None value reads as no clone of the repo.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-25T15:44:18+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the check command change is one call and one print block; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-25T15:44:18+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

docs, fragment and acceptance moves only; no code to refactor

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-25T15:50:06+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · A branch YAML with a bad-date scalar raises ValueError and crashes fr triage check (phase 1)

plan_overlap._load caught only TriageError/YAMLError; yaml.safe_load('a: 2020-13-45') raises ValueError (reproduced), and check_command had no guard, so check exited non-zero against R6.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-25T15:50:06+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · _is_glob treats `[` as a glob, so identical bracketed literal paths never overlap (phase 1)

A literal such as app/[id]/page.tsx was moved to the glob set and never compared literal-to-literal: a false negative.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-25T15:50:06+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · fr-triage.md does not say check reads only the cwd clone's repo (phase 1)

R9: a reader running check from another repo sees every batch not compared; the page did not say so.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-25T15:50:06+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · The board re-reads every batch's plan with git subprocesses on every driver pass (phase 1)

About 3 + phases git calls per dispatched batch per pass, with no cache.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-25T15:50:06+00:00 phase=1 state=open review_scope=out -->
### p1-r5 · finding [open] (reviewer: out of scope) · overlaps() compares repo names case-sensitively (phase 1)

Relies on batch_repo's single spelling; the casing rule predates this change.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-25T15:50:06+00:00 phase=1 -->
### review-p1 · review · phase 1 code review: 5 findings (phase 1)

Dispatched reviewer read the diff 238e6c66..68f7df2f against spec R1-R9 and plan phase 1; ran 135 targeted tests green. Findings p1-r1..p1-r5 (4 in scope, 1 out). Verdict: with fixes. Fixes landed in one commit with new tests (bad-date YAML unreadable; bracketed literal path; check exits 0 when the read raises).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-25T15:50:06+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: A branch YAML with a bad-date scalar raises ValueError and crashes fr triage check (phase 1)

_load also catches ValueError and RecursionError; check_command uses the new checked_report, which turns any unexpected exception into one not-compared line. Tests: test_a_yaml_scalar_that_is_not_a_real_date_is_unreadable_never_raised, test_check_exits_zero_when_the_overlap_read_raises.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-25T15:50:06+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: _is_glob treats `[` as a glob, so identical bracketed literal paths never overlap (phase 1)

_is_glob counts only `*` and `?`; test_a_bracketed_literal_path_is_a_literal_not_a_glob pins both the literal-literal and the glob-literal case.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-25T15:50:06+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: fr-triage.md does not say check reads only the cwd clone's repo (phase 1)

fr-triage.md's plan overlap bullet now says check reads only the clone it runs in (its repo's batches), the driver's page reads every clone it was given, and an empty set means nothing overlaps, not nothing read.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-25T15:50:06+00:00 phase=1 state=refuted resolves=p1-r4 -->
### p1-r4-resolved · finding [refuted] · resolves p1-r4: The board re-reads every batch's plan with git subprocesses on every driver pass (phase 1)

The cost is bounded by the in-flight batches (the driver's max_inflight cap) at a few local git plumbing calls each (cat-file, ls-tree, show on refs the pass already fetched), beside the much larger per-pass work the driver already does (fetches, trial merges, cursor reads). A cross-pass cache would add process-global state keyed on ref commits for no measured cost; the board is a view the driver renders once per pass.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-25T15:50:06+00:00 phase=1 state=open resolves=p1-r5 out_of_scope=true -->
### p1-r5-resolved · finding [out-of-scope] · resolves p1-r5: overlaps() compares repo names case-sensitively (phase 1)

batch_repo and Facts.config_for already decide the repo spelling for every triage reader; this change adds no new casing rule, and source_for_clones lowercases where it matches a clone.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-25T15:56:34+00:00 state=open review_scope=out -->
### l-docs-accuracy-r1 · finding [open] (reviewer: out of scope) · fr-triage.md said the Batches page reads every driver clone; a standalone fr triage batches reads only the cwd clone

Reviewer tagged out. The sentence is this change's own (fr-triage.md plan overlap bullet; triage_kanban_cmd.py write_board called without checkouts at :632 and :701).

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-25T15:56:34+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · source_for_clones turned every GitError/OSError into a bare 'no clone here'

The cause (a stale --checkout path, not a git clone, no origin) was dropped, so an operator could not act on it.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-25T15:56:34+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · A plan naming no files read as compared with zero paths: a silent false 'no overlap'

No NN.yaml, empty phase docs or non-list files: returned an empty PlanPaths that joined the compared set.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3 created=2026-11-25T15:56:34+00:00 state=open review_scope=in -->
### l-errors-r3 · finding [open] (reviewer: in scope) · 'no ref origin/<branch>' gave no hint that the clone may not have fetched the branch

The read never fetches; the usual cause and its fix were unstated.

<!-- fr:journal kind=finding scope=plan id=l-errors-r4 created=2026-11-25T15:56:34+00:00 state=open review_scope=in -->
### l-errors-r4 · finding [open] (reviewer: in scope) · One unreadable run cursor aborted the batch even when a later readable cursor named the branch

read_plan_paths returned the first Unread in the cursor loop.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-25T15:56:34+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · The reader was never tested on a real git clone's happy path

Only FakeSource, which restates git semantics; the one real-git test covered the missing ref.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-25T15:56:34+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · The driver's checkouts=self.checkout_paths wiring had no test

Dropping it would silently fall back to the cwd clone.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-25T15:56:34+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · Zero-directory globs unpinned, and fnmatch misses them: tests/**/*.py did not match tests/x.py

Verified: fnmatchcase('tests/x.py','tests/**/*.py') is False. A real false negative in the rule, not only a test gap.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-25T15:56:34+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · check command tests always monkeypatched source_for_clones

The real Path.cwd() and origin resolution through the command was never exercised.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5 created=2026-11-25T15:56:34+00:00 state=open review_scope=out -->
### l-tests-r5 · finding [open] (reviewer: out of scope) · No test for a cycle or an unknown id in the after closure

Reviewer tagged out; _before is this change's code.

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-25T15:56:34+00:00 -->
### lens-review-1 · review · lens review: docs-accuracy 1, errors 4, tests 5 findings

Three dispatched reviewers, one per lens (docs-accuracy, errors, tests), each over the diff from merge base 238e6c66 to HEAD with the shape file. All 10 findings fixed in one commit with tests; two the reviewers tagged out (l-docs-accuracy-r1, l-tests-r5) stay out of scope per fr's rule, with their fixes in this PR.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-25T15:56:34+00:00 state=open resolves=l-docs-accuracy-r1 out_of_scope=true -->
### l-docs-accuracy-r1-resolved · finding [out-of-scope] · resolves l-docs-accuracy-r1: fr-triage.md said the Batches page reads every driver clone; a standalone fr triage batches reads only the cwd clone

Kept out of scope per the reviewer's tag; the fix nonetheless landed in this PR (operator may mark it fixed): the bullet now says the Batches page reads the cwd clone when you run fr triage batches yourself, and every clone the driver was given when the driver writes it.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-25T15:56:34+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: source_for_clones turned every GitError/OSError into a bare 'no clone here'

source_for_clones keeps the cause: 'no clone here: <cause>' (and '<cwd> is not inside a git clone'). Tests: test_checkouts_pointing_at_no_clone_say_no_clone_here, test_a_cwd_outside_a_clone_or_a_clone_with_no_origin_never_raises.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-25T15:56:34+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: A plan naming no files read as compared with zero paths: a silent false 'no overlap'

A plan whose phases name no files is Unread 'plan names no files (<plan>)'. Test: test_a_plan_that_names_no_files_is_not_compared.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3-resolved created=2026-11-25T15:56:34+00:00 state=fixed resolves=l-errors-r3 -->
### l-errors-r3-resolved · finding [fixed] · resolves l-errors-r3: 'no ref origin/<branch>' gave no hint that the clone may not have fetched the branch

The reason reads 'no ref origin/<branch> (not fetched in this clone? git fetch origin)'.

<!-- fr:journal kind=finding scope=plan id=l-errors-r4-resolved created=2026-11-25T15:56:34+00:00 state=fixed resolves=l-errors-r4 -->
### l-errors-r4-resolved · finding [fixed] · resolves l-errors-r4: One unreadable run cursor aborted the batch even when a later readable cursor named the branch

Unreadable cursors are skipped; the first is reported only if no cursor names the branch. Tests: test_an_unreadable_cursor_does_not_hide_the_readable_one_naming_the_branch, test_invalid_yaml_in_a_cursor_is_unreadable_when_no_cursor_names_the_branch.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-25T15:56:34+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: The reader was never tested on a real git clone's happy path

test_a_real_clone_reads_the_cursor_plan_and_phase_files commits a cursor and plan on a real ref and reads them through Checkout.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-25T15:56:34+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: The driver's checkouts=self.checkout_paths wiring had no test

test_the_drivers_board_reads_through_the_drivers_own_clones calls _Driver._write_board and asserts the checkouts map is passed.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-25T15:56:34+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: Zero-directory globs unpinned, and fnmatch misses them: tests/**/*.py did not match tests/x.py

_matches lets a `**/` segment match no directory too; test_a_double_star_segment_also_matches_no_directory pins it and a non-match.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-25T15:56:34+00:00 state=fixed resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [fixed] · resolves l-tests-r4: check command tests always monkeypatched source_for_clones

test_check_reads_plans_through_the_clone_it_runs_in runs fr triage check from a real clone with real branch refs, unpatched.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5-resolved created=2026-11-25T15:56:34+00:00 state=open resolves=l-tests-r5 out_of_scope=true -->
### l-tests-r5-resolved · finding [out-of-scope] · resolves l-tests-r5: No test for a cycle or an unknown id in the after closure

Kept out of scope per the reviewer's tag (the closure's cycle and unknown-id safety were already correct); a test nonetheless landed in this PR (operator may mark it fixed): test_an_after_cycle_or_an_unknown_id_neither_loops_nor_raises.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved-2 created=2026-11-25T17:34:45+00:00 state=fixed resolves=l-docs-accuracy-r1 answered_by=operator -->
### l-docs-accuracy-r1-resolved-2 · finding [fixed] · resolves l-docs-accuracy-r1: fr-triage.md said the Batches page reads every driver clone; a standalone fr triage batches reads only the cwd clone

operator chose fixed: the fix is in PR #1694

<!-- fr:journal kind=finding scope=plan id=l-tests-r5-resolved-2 created=2026-11-25T17:34:47+00:00 state=fixed resolves=l-tests-r5 answered_by=operator -->
### l-tests-r5-resolved-2 · finding [fixed] · resolves l-tests-r5: No test for a cycle or an unknown id in the after closure

operator chose fixed: the fix is in PR #1694

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved-2 created=2026-11-25T17:35:01+00:00 phase=1 state=open resolves=p1-r5 tracked_by=https://github.com/derio-net/super-fr/issues/1695 -->
### p1-r5-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1695] · resolves p1-r5: overlaps() compares repo names case-sensitively (phase 1)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1695.
