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
