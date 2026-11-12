<!-- fr:journal-schema=3 -->
# Journal: 2026-11-12-acceptance-fragments

<!-- fr:journal kind=decision scope=plan id=plan-four-phases created=2026-11-12T00:29:22+00:00 -->
### plan-four-phases · decision · Four agentic phases, one row each; fold library first, then the migration and cutover together

Phase 1 lands the fold as a library nothing reads yet (risk first). Phase 2 cannot split the
migration from the reader cutover: moving the matrix kind's version makes this repo stale until it
is migrated. Phases 3 (amendments) and 4 (reports) depend only on phase 2. The planning-time row
acceptance-effective-matrix-fold (R17/R18) was added so the fold phase owns a row of its own.

<!-- fr:journal kind=discovery scope=plan id=runner-cannot-delete-artifact created=2026-11-12T00:29:22+00:00 phase=2 -->
### runner-cannot-delete-artifact · discovery · The migration runner re-stamps the migrated path after fn, so a migration cannot delete its own artifact (phase 2)

fr/artifacts/runner.py _apply_to_one always calls kind.write_version(path, ...) after fn returns.
Retiring the matrix kind needs a retiring step (no stamp, path must be gone, removal staged).

<!-- fr:journal kind=decision scope=plan id=fold-batched-blob-reads created=2026-11-12T01:33:01+00:00 phase=1 -->
### fold-batched-blob-reads · decision · The fold reads blobs in git cat-file --batch calls, so its git call count is constant (phase 1)

P1.T4.S2 allowed one `git show` per historical fragment revision (O(fragments-with-amendments
+ 1)). fold() instead lists the tip with one ls-tree, reads every tip blob in one
`cat-file --batch`, runs the one first-parent log, and reads every needed historical
revision in a second `cat-file --batch`: six runner calls whatever the history
(test_the_git_call_count_does_not_grow_with_history asserts <= 8 over 120 fragments and
20 amendments). A repeat fold over the same ref commit and working-tree fragments costs
one rev-parse (memo key: repo, ref sha, sha256 of the working-tree fragments, include_pending).
The default ref is resolved by fr.git.remote_default_ref (the settings helper), outside the
injectable runner.

<!-- fr:journal kind=decision scope=plan id=fold-pending-is-the-working-tree created=2026-11-12T01:33:01+00:00 phase=1 -->
### fold-pending-is-the-working-tree · decision · Pending entries are read from the working tree, by value against the merged tip (phase 1)

The plan left "the branch's own entries" open. fold() reads the working tree's fragments:
a row is pending when no merged fragment defines its id; an amendment is pending when the
merged tip of the same fragment does not carry an equal one (multiset subtraction, so an
un-rebased branch that lacks later merged amendments of its own fragment adds nothing).
A merged row edited in place in the working tree keeps its merged definition and adds a
notice (a merged row changes only by amendment). With no default ref, HEAD is the merged
history and only uncommitted edits are pending.

<!-- fr:journal kind=decision scope=plan id=fold-op-semantics created=2026-11-12T01:33:01+00:00 phase=1 -->
### fold-op-semantics · decision · Amendment op semantics the spec left open (phase 1)

set-status replaces status and notes, appends its optional walk, and unions its issues;
add-level is idempotent; drop-level of a ref not on the row is a no-op (still a revision);
retire replaces notes and moves the row to `retired`. An amendment naming a retired row is
a FoldError, like one naming an unknown row. `feature` must equal the file stem in every
fragment, so legacy.yaml carries `feature: legacy`. Logical refs take an optional anchor on
both kinds (`spec:<slug>[#a]`, `plan:<slug>[#a]`); to_logical converts only a spec file
or a plan FOLDER (a file inside a plan keeps its path), and with own_repo leaves another
repo's refs alone. Row.origin now refuses a malformed `spec:`/`plan:` origin; other origins
are unchanged (check.py still treats a logical origin as a path: phase 2's reader cutover).

<!-- fr:journal kind=discovery scope=plan id=reviewed-stamps-for-library-only created=2026-11-12T01:33:01+00:00 phase=1 -->
### reviewed-stamps-for-library-only · discovery · fr docs check flags the acceptance pages for any change under fr/acceptance/ (phase 1)

docs/reference/acceptance-matrix.md and docs/explainers/fr-acceptance.md cover
packages/fr/src/fr/acceptance/**, so this library-only phase restamped both `reviewed`
lines (still true: no reader uses the fold). Phases 2 and 4 owe real edits to both pages.

<!-- fr:journal kind=finding scope=plan id=docs-check-scenario-gnu-sed created=2026-11-12T01:33:01+00:00 phase=1 state=fixed review_scope=out -->
### docs-check-scenario-gnu-sed · finding [fixed] (reviewer: out of scope) · docs-check-flags-uncovered-change.sh used GNU-only `sed -i`, red on a macOS host (phase 1)

The scenario (from #1401) ran `sed -i 's/…/' docs/a.md`, which BSD sed reads as
`-i` with the script as its backup suffix, so the local full suite failed on macOS
(CI is Linux and passed). Fixed in this phase as a test-only change:
`sed -i.bak … && rm -f docs/a.md.bak`, portable to both.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-12T01:33:01+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

two stubs and a change fragment; T2 and T4 replace the stubs wholesale

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-12T01:33:01+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

logical.py is one small module whose resolve/problem pair already shares one _resolve; nothing duplicated

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-12T01:33:01+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

the validator reuses _load_mapping, _model_problems, parse_fragment and _matrix_strategy_problems; nothing new to extract

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-11-12T01:33:01+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

a scenario script and one row move; no code to clean

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-11-12T01:41:02+00:00 phase=1 -->
### review-phase-1 · review · Phase 1 review (fold library): two in-scope findings, both fixed (phase 1)

Independent reviewer over `git diff 7358c8b21..e9f35cfa4`. Ordering, pending
subtraction, contested, the shallow refusal, git call count, op semantics, the
validator, logical refs, the scenario's portability and fixture privacy all held
(279 targeted tests passed). Two findings, both in scope, fixed in 4ec919d15.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-12T01:41:02+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · A merged amendment naming a retired or unknown row raised FoldError for the whole fold (phase 1)

fold.py raised on any amendment naming a retired/unknown row. R17 says a stale
amendment that merged anyway applies in order and marks its row contested; a
merged entry is immutable, so raising would break every default-ref reader with
no legal fix (B retires X, C's concurrent set-status on X merges after it).

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-12T01:41:02+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · The fold memo key omitted the merged-ref source, so the cached notice could be wrong (phase 1)

With no remote, fold(root) cached "HEAD stands in"; fold(root, ref="HEAD") at the
same sha then returned that notice, and a later fetched origin/main at the same sha
still claimed no default ref.

<!-- fr:journal kind=decision scope=plan id=fold-merged-stale-targets created=2026-11-12T01:41:02+00:00 phase=1 -->
### fold-merged-stale-targets · decision · Supersedes part of fold-op-semantics: only a PENDING amendment on a retired/unknown row is an error (phase 1)

A merged amendment naming a retired row is not applied, bumps the row's revision
and marks it contested (debt, R17 "merged anyway"); one naming an unknown row is
not applied and yields a notice. A pending one still raises, so the branch is
refused before it merges. The merged-ref notice is added per call, outside the memo.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-12T01:41:02+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: A merged amendment naming a retired or unknown row raised FoldError for the whole fold (phase 1)

4ec919d15: merged entries become contested/notice; pending ones still raise. Tests test_a_merged_amendment_to_a_row_retired_meanwhile_marks_it_contested, test_a_merged_amendment_naming_an_unknown_row_is_a_notice_not_an_error, test_a_pending_amendment_to_a_retired_row_is_an_error (red on the old code).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-12T01:41:02+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: The fold memo key omitted the merged-ref source, so the cached notice could be wrong (phase 1)

4ec919d15: the notice is applied outside the cached value. Test test_the_no_default_ref_notice_is_not_served_from_the_cache_to_an_explicit_ref (red on the old code).
