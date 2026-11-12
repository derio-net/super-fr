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

<!-- fr:journal kind=discovery scope=plan id=p2-row-count-before-after created=2026-11-12T04:08:45+00:00 phase=2 -->
### p2-row-count-before-after · discovery · This repo's migration kept all 617 rows, by status, in 121 fragments (phase 2)

Before (docs/acceptance/matrix.yaml at v5): 617 rows: ci 513, walk-owed 40, walked 40,
not-implemented 21, manual 1, scheduled 1, unwired 1. After `fr migrate artifacts --yes`
(commit "chore(fr): migrate artifacts"): `fr acceptance status --brief` reports the same
617 by status, from 120 spec fragments plus legacy.yaml (the rows citing no single spec:
debug journals, two-spec origins, code). `fr validate artifacts` and `fr acceptance check`
pass; the three committed reports were deleted. One row
(archive-retargets-matrix-refs) cited the deleted retarget tests and was re-pointed with
`fr acceptance set-status`.

<!-- fr:journal kind=decision scope=plan id=p2-anchor-repair-folded-into-split created=2026-11-12T04:08:45+00:00 phase=2 -->
### p2-anchor-repair-folded-into-split · decision · The matrix name-anchor repair is unregistered; the split applies its conversion (phase 2)

The runner runs repairs after schema steps, and the 5 -> 6 hop deletes the matrix, so the
`matrix-name-anchors` Repair could never run again (and would be reported "skipped",
i.e. already done, when it had not run). It is no longer registered; the split
(`fr.artifacts.matrix_fragments.split_texts`) maps every ref through its `conversions`
before converting refs to logical. Pinned by
test_migration_matrix_fragments.py#test_the_split_converts_line_anchors.

<!-- fr:journal kind=decision scope=plan id=p2-new-row-feature-resolution created=2026-11-12T04:08:45+00:00 phase=2 -->
### p2-new-row-feature-resolution · decision · A new row's fragment is its one origin spec, else --feature, else the run's spec (phase 2)

`fr acceptance add` writes a new row to the fragment of its one origin spec (a spec path
origin is converted to `spec:<slug>` first); a row naming no single spec is refused unless
`--feature <slug>` names the fragment (`legacy` for none). The record kind's shape is
unchanged (phase 3 owns the 10 -> 11 bump), so `--feature` and `--repo` ride on
`RecordTarget`, and a run record's new row with no single-spec origin goes to the run's
spec fragment. `repo:` comes from a sibling fragment, else the origin remote, else
`--repo`. `fr acceptance init` writes `docs/acceptance/features/.gitkeep` so the
directory survives a clone; an empty matrix splits into no fragment.

<!-- fr:journal kind=decision scope=plan id=p2-reports-not-written created=2026-11-12T04:08:45+00:00 phase=2 -->
### p2-reports-not-written · decision · Writers and init write no report now; check's drift gate and report --deterministic stay for phase 4 (phase 2)

add / set-status / record apply / init write only fragments (R20). The committed set is
deleted by the migration, so check's existence-gated report-drift gate is inert in a
migrated repo; `fr acceptance report --deterministic` still renders the set, through
`fr.acceptance.logical.path_view` (logical refs shown as the paths they resolve to).
Phase 4 finalises the report surfaces. test_tripwire_acceptance_report_sync now asserts
no report (and no matrix) is tracked.

<!-- fr:journal kind=finding scope=plan id=p2-interim-set-status-on-merged-row created=2026-11-12T04:08:45+00:00 phase=2 state=open review_scope=in -->
### p2-interim-set-status-on-merged-row · finding [open] (reviewer: in scope) · Interim in-place set-status on a merged row is invisible to the fold (phase 2)

phase-1's fold keeps a merged row's merged definition and adds a notice when the working
tree edits it in place (decision fold-pending-is-the-working-tree). Until phase 3's
amendments land, `set-status` on a merged row rewrites the owning fragment in place
(test_acceptance_fragment_writes.py#test_interim_set_status_on_a_merged_row_edits_its_owning_fragment_in_place
pins only the file), so every reader keeps the old status. With no default ref, HEAD
stands in for merged history, so the same holds for rows committed on the branch
(tests/scenarios/exit-gates-verify-without-section.sh now commits each rewrite).
In this repo no fragment is on origin/main yet, so every row is pending and set-status
is visible. Phase 3 (set-status on a merged row becomes an amendment) must land before
this PR merges.

<!-- fr:journal kind=discovery scope=plan id=p2-suite-slower created=2026-11-12T04:08:45+00:00 phase=2 -->
### p2-suite-slower · discovery · The acceptance-heavy tests got slower because every reader now folds over git (phase 2)

load_effective runs a handful of git calls per fold (memoised per ref sha and
working-tree digest, but the default-ref and toplevel probes run on every call), so
tests that seed a fresh repo per case and call several readers pay for it. The full
suite took 22 min on this host under a load average near 60 from other processes; it
was not measured against a baseline, so the fold's share is unknown. Worth a timing
pass (and maybe memoising the default-ref probe per root) before CI's time budget
notices.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-12T04:08:45+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

a frozen reader is a verbatim copy of the V4 pattern by rule; nothing may be factored out of a sha-pinned class

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-12T04:08:45+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

the retiring branch is one early return beside the stamp path; folding it into the stamp path would make every existing hop take the new branch

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-11-12T04:08:45+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

the reader cutover replaced each call site in place through load_effective / has_fragments / path_view; the duplication left (fragment existence checks) is already one helper

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t5 created=2026-11-12T04:08:45+00:00 phase=2 -->
### no-refactor-p2-t5 · discovery · no-refactor-because P2.T5 (phase 2)

the writer reuses edit.insert_row/replace_row unchanged on fragment text; the one new renderer (render_fragment) is shared with the migration

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t6 created=2026-11-12T04:08:45+00:00 phase=2 -->
### no-refactor-p2-t6 · discovery · no-refactor-because P2.T6 (phase 2)

the fixture sweep went through one helper module (acceptance_helpers.write_fragments, write_matrix_fragments, fragments_text) and one scenario helper (matrix_fragment); no second copy to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t7 created=2026-11-12T04:08:45+00:00 phase=2 -->
### no-refactor-p2-t7 · discovery · no-refactor-because P2.T7 (phase 2)

data migration, rule and doc prose, and a scenario script; no code to clean

<!-- fr:journal kind=review scope=plan id=review-phase-2 created=2026-11-12T04:41:29+00:00 phase=2 -->
### review-phase-2 · review · Phase 2 review (migration and cutover): five in-scope findings, all fixed (phase 2)

Independent reviewer over `git diff ac0a524af..c9d21686f`. Frozen MatrixV5, the
retiring step, write-once, crash window, edge repos, the chain, and this repo's data
(617 rows in, 617 out, each placed once by the one-spec rule, every fragment
`repo: derio-net/super-fr`) all held; no code reader is left on matrix.yaml.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-12T04:41:29+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · A v4 matrix with a partial committed report set fails the migration commit (4->5 writes reports 5->6 deletes; git add of a vanished path) (phase 2)

Reproduced with only report_local.html tracked.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-12T04:41:29+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · The split deletes an untracked report.github.html and lists it as changed, failing the commit (phase 2)

Also silently removed an uncommitted user file.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-12T04:41:29+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · The matrix 4->5 hop still validates with the live parse_matrix instead of the frozen MatrixV5 (phase 2)

artifact-versioning rule point 2; no tripwire existed for the matrix hops.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-12T04:41:29+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · An in-flight branch still editing matrix.yaml has no way forward after this merges (phase 2)

The split refused over existing fragments and the gate then blocked every command; open PRs #1107, #1080, #1079, #476 affected.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-12T04:41:29+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · With the archive retarget removed, archived journal path refs dangle and check's warning names a removed fix (phase 2)

Only spec:/plan: refs are logical; the archive-retargets-matrix-refs row text was also false.

<!-- fr:journal kind=decision scope=plan id=matrix-split-carries-in-flight-rows created=2026-11-12T04:41:29+00:00 phase=2 -->
### matrix-split-carries-in-flight-rows · decision · An in-flight matrix.yaml is carried over onto existing fragments, never merged silently (phase 2)

When fragments already exist, the 5→6 split adds only the rows whose id their fold lacks,
each to its spec's fragment (or legacy.yaml) by the one-spec rule, and drops rows the fold
holds identically. A row the fold holds with different content refuses the matrix,
byte-identical, naming each id: restore or delete the row, migrate, then re-apply the
change with `fr acceptance set-status` (later `amend`). The crash window is the same rule:
nothing to carry, so the matrix is just deleted.

<!-- fr:journal kind=decision scope=plan id=archived-refs-resolve-at-read-time created=2026-11-12T04:41:29+00:00 phase=2 -->
### archived-refs-resolve-at-read-time · decision · Path refs under specs/journals/plans resolve at their archived twin at read time (phase 2)

Replaces the removed archive retarget: `check.archived_counterpart` (reusing archive_twin
and the plans mapping) accepts a same-repo ref whose `implemented/` counterpart exists;
no fragment is rewritten, so merged rows stay immutable.

<!-- fr:journal kind=finding scope=plan id=p3-set-status-on-merged-row-is-an-amendment created=2026-11-12T04:41:29+00:00 phase=3 state=open review_scope=in -->
### p3-set-status-on-merged-row-is-an-amendment · finding [open] (reviewer: in scope) · Refiled from p2-interim-set-status-on-merged-row: set-status on a merged row must become an amendment (phase 3)

Phase 2's interim set-status rewrites a merged row in place, which the fold ignores
(keeps the merged copy, adds a notice). This is phase 3's deliverable (R16: set-status
on a merged row becomes an amendment); filed against phase 3 so it gates that review
and this PR, rather than phase 2's.

<!-- fr:journal kind=finding scope=plan id=p2-interim-set-status-on-merged-row-resolved created=2026-11-12T04:41:29+00:00 phase=2 state=open resolves=p2-interim-set-status-on-merged-row tracked_by=derio-net/super-fr#1379 -->
### p2-interim-set-status-on-merged-row-resolved · finding [deferred → derio-net/super-fr#1379] · resolves p2-interim-set-status-on-merged-row: Interim in-place set-status on a merged row is invisible to the fold (phase 2)

Refiled against phase 3 of this same PR as p3-set-status-on-merged-row-is-an-amendment, which gates phase 3's review; #1379 tracks the acceptance-fragments-amendments row.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-12T04:41:29+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: A v4 matrix with a partial committed report set fails the migration commit (4->5 writes reports 5->6 deletes; git add of a vanished path) (phase 2)

2c4d75fd2: the 4->5 hop renders no reports; commit_paths drops paths neither on disk nor in the index. Test red on old code.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-12T04:41:29+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: The split deletes an untracked report.github.html and lists it as changed, failing the commit (phase 2)

2ac63080e: the split deletes and lists only reports git tracks (ls-files). Test red on old code.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-12T04:41:29+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: The matrix 4->5 hop still validates with the live parse_matrix instead of the frozen MatrixV5 (phase 2)

e9eacca8a: legacy.parse_matrix_v5_body used by every 4->5 check; tripwire forbids parse_matrix/load_matrix in fr/artifacts/matrix_*.py.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-12T04:41:29+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: An in-flight branch still editing matrix.yaml has no way forward after this merges (phase 2)

89435b564: carry-over per decision matrix-split-carries-in-flight-rows; documented in docs/reference/acceptance-matrix.md and the acceptance-matrix rule.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-12T04:41:29+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: With the archive retarget removed, archived journal path refs dangle and check's warning names a removed fix (phase 2)

764cb9c19 (read-time archived twin, warning reworded), c98958648 + 1dfba07cd (row refs, notes and text).

<!-- fr:journal kind=decision scope=plan id=p3-merged-means-on-the-default-ref created=2026-11-12T05:58:36+00:00 phase=3 -->
### p3-merged-means-on-the-default-ref · decision · A row is merged when the default ref's fragments define it; with no default ref nothing is merged (phase 3) (phase 3)

`set-status` routes to amendments only for a row the fragments at the default
ref's tip define (`fold.default_ref_fold`, the remote-tracking default ref).
A repo with no default ref (no remote, or none fetched) has no merged row, so
set-status edits in place there, and `check`'s immutability rule has nothing to
hold (the fold still orders by HEAD's history, as phase 1 decided).

<!-- fr:journal kind=decision scope=plan id=p3-set-status-amendment-verify-scenario created=2026-11-12T05:58:36+00:00 phase=3 -->
### p3-set-status-amendment-verify-scenario · decision · The set-status amendment carries optional verify and scenario; harnesses on a merged row are refused (phase 3) (phase 3)

`set-status --verify/--scenario` must still work on a merged row, so the
fragment's SetStatus amendment gains optional `verify` and `scenario`, replaced
when given. The acceptance-fragment kind is new in this unreleased PR, so no
released fr reads it and no stamp moves. No op carries `harnesses`; a record
move adding one to a merged row is refused, naming the rule.

<!-- fr:journal kind=decision scope=plan id=p3-set-status-owner-fallback created=2026-11-12T05:58:36+00:00 phase=3 -->
### p3-set-status-owner-fallback · decision · set-status with no feature in play appends a merged row's amendments to the row's own fragment; amend refuses (phase 3) (phase 3)

The plan said the feature is --feature, else the branch's run's spec, else
refused. That refused every command fr itself prints after a merge (`fr gate
pass --keep`'s walk line, deliver's `set-status --issue` link, the walk close-out),
which run on a branch with no run: tests/unit/test_printed_commands_run.py and
the printed-commands-run scenario went red. So `set-status` falls back to the
row's owning feature: the change is still an appended amendment (never an
in-place edit), ordered by its first-parent introduction. `amend`, the
authoring verb, keeps the plan's refusal naming --feature. Worth the reviewer's
eye: R16 says "its own fragment" of a later feature, and a post-merge walk has none.

<!-- fr:journal kind=decision scope=plan id=p3-rebase-verb created=2026-11-12T05:58:36+00:00 phase=3 -->
### p3-rebase-verb · decision · The stale-base fix is `fr acceptance amend --rebase` (phase 3) (phase 3)

R17 names the refusal, not the fix. `amend --rebase` sets each stale pending
amendment's `base` to its row's revision when it applies (the fold's
`stale_pending.revision`), line surgery on the `base:` line only, one commit
holding the fragments. The refusal tells the operator to review the row first.

<!-- fr:journal kind=decision scope=plan id=p3-immutability-judged-against-the-merge-base created=2026-11-12T05:58:36+00:00 phase=3 -->
### p3-immutability-judged-against-the-merge-base · decision · check's merged-row rule skips entries equal to the merge base, so a branch behind main is not an edit (phase 3) (phase 3)

A row (or amendment) on the default ref that the working tree lacks or holds
differently is refused only when the working tree also differs from the merge
base of HEAD and the default ref: an entry merged after the branch forked is
the branch being behind, not an in-place edit.

<!-- fr:journal kind=decision scope=plan id=p3-fetch-failure-refuses-in-ci-only created=2026-11-12T05:58:36+00:00 phase=3 -->
### p3-fetch-failure-refuses-in-ci-only · decision · A failed fetch of the default ref refuses in CI and warns elsewhere (phase 3) (phase 3)

`check` and `deliver` fetch `+refs/heads/<b>:refs/remotes/<remote>/<b>` first.
Under a CI marker (`fr.artifacts.trigger.in_ci`) a failed fetch is a refusal,
never a pass; on an operator's machine it is a warning and the last fetched
ref is judged, so an offline laptop still checks. `check --no-fetch` skips it.

<!-- fr:journal kind=decision scope=plan id=p3-debt-report-contested-fields created=2026-11-12T05:58:36+00:00 phase=3 -->
### p3-debt-report-contested-fields · decision · DebtReport gains defaulted contested fields; is_debt is the one definition (phase 3) (phase 3)

`AcceptanceDebt.contested` (rows contested whose status is not already debt)
and `DebtRow.contested` are optional and defaulted; `debt_total` counts them.
The issue figures (`parse_figures`) carry counts only and are unchanged.
`fr.acceptance.model.is_debt(status, contested=)` is what debt, status and
`open_rows` share.

<!-- fr:journal kind=discovery scope=plan id=p3-no-live-records-to-migrate created=2026-11-12T05:58:36+00:00 phase=3 -->
### p3-no-live-records-to-migrate · discovery · `fr migrate artifacts --yes` found every artifact current: this run had no live record when the record kind moved (phase 3) (phase 3)

The record kind moved 10 -> 11, but no record file was live under
docs/superpowers/runs/*.records/ at the time, so the migration wrote nothing and
there was no migration commit to make. This record is written at stamp 11.

<!-- fr:journal kind=finding scope=plan id=p3-stray-r1-records-dir created=2026-11-12T05:58:36+00:00 phase=3 state=open review_scope=out -->
### p3-stray-r1-records-dir · finding [open] (reviewer: out of scope) · An empty untracked docs/superpowers/runs/r1.records/ sits in the workspace, created before phase 3 (phase 3) (phase 3)

Created 2026-11-12 02:05, before this phase started, untracked and empty, so
nothing commits it. `r1` is the run id several record tests use, which suggests
a test once created a records dir under the repo instead of its tmp path. Not
reproduced in this phase's runs.

<!-- fr:journal kind=finding scope=plan id=p3-set-status-on-merged-row-is-an-amendment-resolved created=2026-11-12T05:58:36+00:00 phase=3 state=fixed resolves=p3-set-status-on-merged-row-is-an-amendment -->
### p3-set-status-on-merged-row-is-an-amendment-resolved · finding [fixed] · resolves p3-set-status-on-merged-row-is-an-amendment: Refiled from p2-interim-set-status-on-merged-row: set-status on a merged row must become an amendment (phase 3)

`set-status` on a row merged on the default ref now appends set-status,
add-level and drop-level amendments to this feature's fragment and leaves the
owner's fragment untouched; a row pending on this branch is still edited in
place, and `check` refuses an in-place edit of a merged row. Tests:
tests/unit/test_acceptance_amend.py#test_set_status_on_a_merged_row_appends_amendments_and_leaves_its_owner_alone,
#test_set_status_on_a_row_pending_on_this_branch_still_edits_in_place and
#test_check_refuses_an_in_place_edit_of_a_merged_row. Phase 2's interim
in-place test is removed.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-11-12T05:58:36+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

the in-place-vs-amend routing is one branch in _acceptance_writes calling the one _Amending helper, which both the record's amendment item and set-status's merged-row move go through; no second copy to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-12T05:58:36+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

a stamp-only migration that reuses record_exit_gates' guard and an AmendmentItem that delegates validation to the fragment's own Amendment union; nothing duplicated to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-11-12T05:58:36+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

stale_pending is recorded inside the fold's existing apply loop and both check and deliver read the one branch_refusals; is_debt is the one contested-or-debt-status test that debt, status and open_rows share

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t4 created=2026-11-12T05:58:36+00:00 phase=3 -->
### no-refactor-p3-t4 · discovery · no-refactor-because P3.T4 (phase 3)

skill, rule and explainer prose, regenerated mirrors and a scenario script; no code to clean

<!-- fr:journal kind=review scope=plan id=review-phase-3 created=2026-11-12T06:40:25+00:00 phase=3 -->
### review-phase-3 · review · Phase 3 review (amendments): four in-scope findings, all fixed (phase 3)

Independent reviewer over `git diff 378340641..4856be6d0`. Amendment bases, --rebase,
in-place edits of pending rows, the stale-base refusal's network behaviour, the record
10->11 migration and the scenario held; check on this branch is clean (617 rows).

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-12T06:40:25+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · set-status owner fallback wrote into another feature's merged fragment, contradicting R16 ('its own fragment') (phase 3)

Reintroduced shared-file conflicts (legacy.yaml hotspot); the explainer's 'two different files' sentence became false.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-12T06:40:25+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · check compared merged amendments as a multiset, so reordering or inserting above them passed and changed the post-merge fold (phase 3)

Reproduced: walk-owed became unwired, contested after merge.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-12T06:40:25+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · branch_refusals silently skipped fetch, immutability and stale checks when the default ref could not be resolved, so CI passed (phase 3)

Contrary to R17 and the CI fail-closed decision.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-11-12T06:40:25+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · Retired-but-contested rows were counted by acceptance status but by no debt reader (phase 3)

status said contested: 1 while fr debt and the digest counted 0.

<!-- fr:journal kind=decision scope=plan id=p3-set-status-feature-required created=2026-11-12T06:40:25+00:00 phase=3 -->
### p3-set-status-feature-required · decision · Supersedes p3-set-status-owner-fallback: set-status with no feature refuses; printed post-merge commands name the feature they close (phase 3)

R16 writes an amendment to the fragment of the feature making it, so the owner fallback
is gone: `set-status` with no `--feature` and no run refuses, as `amend` does. A
post-merge walk or issue link belongs to the feature whose gate or delivery it closes,
so every command fr prints for one carries `--feature` (the run's spec, else the row's
one origin spec, else a `<spec-slug>` placeholder). legacy.yaml never takes amendments
by default.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-12T06:40:25+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: set-status owner fallback wrote into another feature's merged fragment, contradicting R16 ('its own fragment') (phase 3)

992e9515f: fallback removed; feature_flag() adds --feature to every printed post-merge command; printed-commands scenario asserts the link lands in the feature's own fragment.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-12T06:40:25+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: check compared merged amendments as a multiset, so reordering or inserting above them passed and changed the post-merge fold (phase 3)

ecf32e7dc: merged amendments (at the merge base) must be an exact prefix of the working list; tests for swap, insert-above, append-after.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-12T06:40:25+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: branch_refusals silently skipped fetch, immutability and stale checks when the default ref could not be resolved, so CI passed (phase 3)

0cd01545d: a remote with no resolvable default ref is refused in CI, warned elsewhere; this repo's acceptance-report.yml and the scaffold templates check out full history.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-11-12T06:40:25+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: Retired-but-contested rows were counted by acceptance status but by no debt reader (phase 3)

dcb086cff: retired contested rows are debt in status, open_rows, fr debt, the digest, fr status and summary (DebtRow.retired).

<!-- fr:journal kind=finding scope=plan id=p3-stray-r1-records-dir-resolved created=2026-11-12T06:40:25+00:00 phase=3 state=open resolves=p3-stray-r1-records-dir out_of_scope=true -->
### p3-stray-r1-records-dir-resolved · finding [out-of-scope] · resolves p3-stray-r1-records-dir: An empty untracked docs/superpowers/runs/r1.records/ sits in the workspace, created before phase 3 (phase 3) (phase 3)

An empty untracked dir that predates phase 3 (created 02:05, before any phase ran), likely from a test run in the workspace; nothing in this change writes it. Removed locally (empty, never tracked).

<!-- fr:journal kind=decision scope=plan id=p4-comment-job-github-only created=2026-11-12T07:57:44+00:00 phase=4 -->
### p4-comment-job-github-only · decision · The PR report comment job and the Pages job exist per forge capability (phase 4) (phase 4)

A comment job is scaffolded for GitHub Actions only, because comment_pr is unsupported on the GitLab and Gitea clients (UnsupportedBatchOps); init prints a notice when report_comment is on elsewhere. A Pages job is scaffolded for GitHub Actions and GitLab CI only (Gitea has no visibility read). `pages_visibility(repo)` takes the same owner/repo string as the other client reads and answers controlled|public|unknown, never raising. The settings rule report-comment-needs-repo-placement is data, dormant until quiet/stealth can be served.

<!-- fr:journal kind=decision scope=plan id=p4-pages-fixtures-provenance created=2026-11-12T07:57:44+00:00 phase=4 -->
### p4-pages-fixtures-provenance · decision · Pages fixtures: one capture, the rest from the forge docs (phase 4) (phase 4)

tests/fixtures/acceptance_pages/github-pages-public.json is a capture of GET /repos/{o}/{r}/pages on this public derio-net repo. The public:false, GitLab pages_access_level/visibility and Gitea shapes were not capturable (no private repo or GitLab/Gitea instance); the tests say so and cite the GitHub and GitLab API docs.

<!-- fr:journal kind=decision scope=plan id=p4-glab-repo-visibility created=2026-11-12T07:57:44+00:00 phase=4 -->
### p4-glab-repo-visibility · decision · RealGlabClient gained repo_visibility (phase 4) (phase 4)

Without it a public GitLab repo could never satisfy pages_allowed (the generic reader raised unsupported). It reads the project's visibility from projects/:id, raising when unreadable as the GhClient contract says.

<!-- fr:journal kind=finding scope=plan id=p4-gitlab-pages-fail-open created=2026-11-12T07:57:44+00:00 phase=4 state=open review_scope=in -->
### p4-gitlab-pages-fail-open · finding [open] (reviewer: in scope) · GitLab Pages visibility failed open on enabled and unconfirmed private (phase 4) (phase 4)

pages_access_level `enabled` means everyone with access to the project (everyone on a public project) and `private` holds only where the instance enforces Pages access control; the first cut treated both as controlled. Now private is controlled only with access control confirmed (gitlab.com always; a self-managed host is never proven by the API), enabled only with that AND a private or internal project, and everything else is unknown. Pinned by TestGitlab in test_acceptance_pages_visibility.py; shape source is the GitLab Projects API and Pages access-control docs.

<!-- fr:journal kind=finding scope=plan id=p4-comment-marker-hijack created=2026-11-12T07:57:44+00:00 phase=4 state=open review_scope=in -->
### p4-comment-marker-hijack · finding [open] (reviewer: in scope) · fr acceptance comment edited a marker comment from any author (phase 4) (phase 4)

The marker is public text, so anyone could plant it and have fr overwrite their comment. It now edits only a marker comment whose author is the credentials' own login (authenticated_login), or the workflow bot inside GitHub Actions when the forge will not name the identity; with no known identity it always posts fresh. Tests: foreign author, workflow bot, unknown identity in test_acceptance_scaffold_publish.py.

<!-- fr:journal kind=finding scope=plan id=p4-gitlab-pages-fail-open-resolved created=2026-11-12T07:57:44+00:00 phase=4 state=fixed resolves=p4-gitlab-pages-fail-open -->
### p4-gitlab-pages-fail-open-resolved · finding [fixed] · resolves p4-gitlab-pages-fail-open: GitLab Pages visibility failed open on enabled and unconfirmed private (phase 4) (phase 4)

commit fix(acceptance): GitLab Pages are controlled only where access control is confirmed

<!-- fr:journal kind=finding scope=plan id=p4-comment-marker-hijack-resolved created=2026-11-12T07:57:44+00:00 phase=4 state=fixed resolves=p4-comment-marker-hijack -->
### p4-comment-marker-hijack-resolved · finding [fixed] · resolves p4-comment-marker-hijack: fr acceptance comment edited a marker comment from any author (phase 4) (phase 4)

commit fix(acceptance): the report comment edits only a comment its own identity wrote

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-11-12T07:57:44+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

the committed-set machinery was deleted outright and the one local renderer (render_report) gained a format argument; nothing left to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t2 created=2026-11-12T07:57:44+00:00 phase=4 -->
### no-refactor-p4-t2 · discovery · no-refactor-because P4.T2 (phase 4)

pages.py is the one place the visibility decision lives and each client holds only its forge's read; no duplication

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t3 created=2026-11-12T07:57:44+00:00 phase=4 -->
### no-refactor-p4-t3 · discovery · no-refactor-because P4.T3 (phase 4)

templates share the existing placeholder mechanism; the publish blocks are one constant per CI type, so nothing to factor

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t4 created=2026-11-12T07:57:44+00:00 phase=4 -->
### no-refactor-p4-t4 · discovery · no-refactor-because P4.T4 (phase 4)

docs, workflow and scenario edits only

<!-- fr:journal kind=review scope=plan id=review-phase-4 created=2026-11-12T08:44:04+00:00 phase=4 -->
### review-phase-4 · review · Phase 4 review (derived reports): seven in-scope findings, all fixed (phase 4)

Independent reviewer over `git diff 46eead987..f9ed61e76`. Both security fixes held on
review: GitLab `from_gitlab` maps only confirmed-access-control `private` (and `enabled` on a
private/internal project) to controlled, everything else unknown, and `pages_allowed` refuses
every non-controlled answer and exception; `fr acceptance comment` edits only a marker
comment its own login wrote and posts fresh when the identity is unknown. Tracked-report
refusal covers new and legacy paths; GitHub Pages jobs gate every later step on the check.

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-11-12T08:44:04+00:00 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · Skipping a Pages deploy leaves the already-published site live; the explainer claimed a repo turned private keeps no public site, and the skip was only a warning (phase 4)

R21's 'no wider than the repo' breaks silently once visibility narrows on a plan whose Pages stay public.

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-11-12T08:44:04+00:00 phase=4 state=open review_scope=in -->
### p4-r2 · finding [open] (reviewer: in scope) · Scaffolded GitLab pages job ran pages-check with no forge credential, so it could never pass (phase 4)

Fails closed, but the scaffolded feature never works and nothing says why.

<!-- fr:journal kind=finding scope=plan id=p4-r3 created=2026-11-12T08:44:04+00:00 phase=4 state=open review_scope=in -->
### p4-r3 · finding [open] (reviewer: in scope) · RealGlabClient inferred gitlab.com (Pages access control confirmed) from host=None, which GITLAB_HOST or glab's default host can contradict (phase 4)

A self-managed instance could be assumed to enforce Pages access control without proof.

<!-- fr:journal kind=finding scope=plan id=p4-r4 created=2026-11-12T08:44:04+00:00 phase=4 state=open review_scope=in -->
### p4-r4 · finding [open] (reviewer: in scope) · GitLab pages job had no needs on acceptance-report, so a failing matrix still published (phase 4)

The GitHub job has needs: matrix.

<!-- fr:journal kind=finding scope=plan id=p4-r5 created=2026-11-12T08:44:04+00:00 phase=4 state=open review_scope=in -->
### p4-r5 · finding [open] (reviewer: in scope) · pages.yml rendered the folded report from a shallow checkout; the first merged amendment would make every deploy ship the placeholder (phase 4)

fold raises FoldHistoryError on shallow history once a fragment carries amendments.

<!-- fr:journal kind=finding scope=plan id=p4-r6 created=2026-11-12T08:44:04+00:00 phase=4 state=open review_scope=in -->
### p4-r6 · finding [open] (reviewer: in scope) · Rows describing the removed committed-report behaviour stayed status ci with no retire/reword amendment (phase 4)

Their refs are whole-file, so check could not see the behaviour inside surviving files was gone.

<!-- fr:journal kind=finding scope=plan id=p4-r7 created=2026-11-12T08:44:04+00:00 phase=4 state=open review_scope=in -->
### p4-r7 · finding [open] (reviewer: in scope) · Leftover committed-report references: .gitattributes LF block, report.py docstrings, stale .test_durations entries (phase 4)

Describes machinery that no longer exists.

<!-- fr:journal kind=discovery scope=plan id=p4-file-level-refs-cannot-go-stale created=2026-11-12T08:44:04+00:00 phase=4 -->
### p4-file-level-refs-cannot-go-stale · discovery · A file-level acceptance ref (no #name anchor) cannot go stale: check only resolves the file (phase 4)

p4-r6's rows kept `status: ci` after their behaviour was removed because each ref named a
whole test file that still exists. Name-anchored refs are caught (acceptance-ci-built-reports
was). Worth a follow-up so a removed behaviour cannot hide behind a surviving file.

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-11-12T08:44:04+00:00 phase=4 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: Skipping a Pages deploy leaves the already-published site live; the explainer claimed a repo turned private keeps no public site, and the skip was only a warning (phase 4)

d62e056b7: the pre-deploy re-check emits ::error:: naming how to unpublish by hand and exits 1 (GitHub template, GitLab pages script, this repo's pages.yml, where docs and report are one deployment so the refusal fails it whole); the explainer says the re-check stops new deploys and cannot unpublish.

<!-- fr:journal kind=finding scope=plan id=p4-r2-resolved created=2026-11-12T08:44:04+00:00 phase=4 state=fixed resolves=p4-r2 -->
### p4-r2-resolved · finding [fixed] · resolves p4-r2: Scaffolded GitLab pages job ran pages-check with no forge credential, so it could never pass (phase 4)

d62e056b7: the GitLab pages job sets GITLAB_TOKEN: $FR_PAGES_TOKEN; the init notice names the masked read_api variable and glab-in-image for self-managed hosts; goldens regenerated.

<!-- fr:journal kind=finding scope=plan id=p4-r3-resolved created=2026-11-12T08:44:04+00:00 phase=4 state=fixed resolves=p4-r3 -->
### p4-r3-resolved · finding [fixed] · resolves p4-r3: RealGlabClient inferred gitlab.com (Pages access control confirmed) from host=None, which GITLAB_HOST or glab's default host can contradict (phase 4)

2f32f77ca: access control is confirmed only when the project API answer's web_url host is gitlab.com; GITLAB_HOST/GL_HOST pointing elsewhere, or no web_url, gives unknown. The three new tests were confirmed red on the pre-fix client by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p4-r4-resolved created=2026-11-12T08:44:04+00:00 phase=4 state=fixed resolves=p4-r4 -->
### p4-r4-resolved · finding [fixed] · resolves p4-r4: GitLab pages job had no needs on acceptance-report, so a failing matrix still published (phase 4)

d62e056b7: needs: [acceptance-report] on the GitLab pages job, asserted in tests.

<!-- fr:journal kind=finding scope=plan id=p4-r5-resolved created=2026-11-12T08:44:04+00:00 phase=4 state=fixed resolves=p4-r5 -->
### p4-r5-resolved · finding [fixed] · resolves p4-r5: pages.yml rendered the folded report from a shallow checkout; the first merged amendment would make every deploy ship the placeholder (phase 4)

d62e056b7: fetch-depth: 0 on pages.yml's checkout, asserted in test_pages_workflow.

<!-- fr:journal kind=finding scope=plan id=p4-r6-resolved created=2026-11-12T08:44:04+00:00 phase=4 state=fixed resolves=p4-r6 -->
### p4-r6-resolved · finding [fixed] · resolves p4-r6: Rows describing the removed committed-report behaviour stayed status ci with no retire/reword amendment (phase 4)

164a4a006, 0e83725d6, 2186d33b5 reword acceptance-report-formats, acceptance-report-dual, acceptance-report-drift-gate to the derived-report claims; 149b6c80a, db21de751, 221b1ebdb, 4ad379fca retire acceptance-report-dual-gate, acceptance-report-tracked, acceptance-report-cli-regen, acceptance-ci-built-reports; notes cite R20; fr acceptance check passes.

<!-- fr:journal kind=finding scope=plan id=p4-r7-resolved created=2026-11-12T08:44:04+00:00 phase=4 state=fixed resolves=p4-r7 -->
### p4-r7-resolved · finding [fixed] · resolves p4-r7: Leftover committed-report references: .gitattributes LF block, report.py docstrings, stale .test_durations entries (phase 4)

e9fdf227b: .gitattributes removed (it held only the report block), the aggregates=False path removed from report.py with docstrings rewritten, 137 stale .test_durations keys dropped (each verified absent from collection). Path constants and the migration's delete list keep naming the retired files on purpose.

<!-- fr:journal kind=finding scope=plan id=p3-stray-r1-records-dir-resolved-2 created=2026-11-12T09:15:55+00:00 state=fixed resolves=p3-stray-r1-records-dir -->
### p3-stray-r1-records-dir-resolved-2 · finding [fixed] · resolves p3-stray-r1-records-dir: An empty untracked docs/superpowers/runs/r1.records/ sits in the workspace, created before phase 3 (phase 3)

The empty untracked directory was removed from the workspace; it was never tracked, so nothing remains to file.

<!-- fr:journal kind=decision scope=plan id=fold-retired-rows-keep-the-base-rule created=2026-11-12T09:18:08+00:00 phase=1 -->
### fold-retired-rows-keep-the-base-rule · decision · Retired rows stay under R17's base rule: a stale retire marks the row contested, and a correctly based amendment on a retired row clears it (phase 1)

Resolves pr1408-r1 and pr1408-r2 with one design. A retired row keeps its revision count, and every amendment that names it, pending or merged, goes through the same base check as a live row. A pending stale one is a stale-pending refusal (the normal check/deliver path), never a FoldError; a merged stale one marks the row contested (debt via DebtRow.retired). A correctly based amendment applies to the retired snapshot, counts a revision and clears contested; the row stays retired, because R16 has no op that un-retires. A retire is checked like any amendment and no longer clears contested unconditionally: a stale retire that merged leaves the row retired AND contested; a correctly based retire clears it. An amendment naming an unknown row is unchanged (pending raises, merged is a notice). Within R17 as written; no spec change.

<!-- fr:journal kind=finding scope=plan id=pr1408-r1 created=2026-11-12T09:18:47+00:00 phase=1 state=open review_scope=in -->
### pr1408-r1 · finding [open] (reviewer: in scope) · A retired row that became contested can never be cleared: every pending amendment naming a retired row raises FoldError, whatever its base (phase 1)

Pre-merge review of PR #1408 (operator's independent review), item 1. fold.py retired-row branch. R17: the next correctly based amendment clears a contested row; here none can exist, and the FoldError breaks every reader on that branch.

<!-- fr:journal kind=finding scope=plan id=pr1408-r2 created=2026-11-12T09:18:49+00:00 phase=1 state=open review_scope=in -->
### pr1408-r2 · finding [open] (reviewer: in scope) · A stale retire that merged anyway is silent: contested.discard runs unconditionally on retire (phase 1)

PR #1408 review item 2. A's set-status (base 0) merges, then B's retire (base 0) merges: retired, not contested, no debt. Only the opposite order was tested.

<!-- fr:journal kind=finding scope=plan id=pr1408-r3 created=2026-11-12T09:18:51+00:00 phase=3 state=open review_scope=in -->
### pr1408-r3 · finding [open] (reviewer: in scope) · Scaffolded GitHub matrix job checks out with persist-credentials: false, so check's default-ref fetch fails in CI on a private repo and every run is refused (phase 3)

PR #1408 review item 3. scaffold.py GitHub matrix job + amend.py default-ref fetch. Reproduced with an unreachable origin and CI=true: exit 1 'cannot fetch the default ref'. The checkout already has the default branch (fetch-depth: 0).

<!-- fr:journal kind=finding scope=plan id=pr1408-r4 created=2026-11-12T09:18:52+00:00 phase=2 state=open review_scope=in -->
### pr1408-r4 · finding [open] (reviewer: in scope) · An in-flight branch whose matrix.yaml holds a row this PR retired gets 'duplicate row ids' with no fix named (phase 2)

PR #1408 review item 4. matrix_fragments.py builds known from live fold rows only. Fails closed; the defect is the dead-end message.

<!-- fr:journal kind=finding scope=plan id=pr1408-r5 created=2026-11-12T09:18:54+00:00 phase=2 state=open review_scope=in -->
### pr1408-r5 · finding [open] (reviewer: in scope) · matrix-parse-libyaml and archive-retargets-matrix-refs, owned by other features, were edited in place after the migration instead of amended (phase 2)

PR #1408 review item 5 (commits 9281ed6dc, c98958648, 1dfba07cd, 488341fa6), still at revision 0. R16 forbids in-place edits of merged rows: restore the owners' rows and redo the changes as amendments in this feature's fragment.

<!-- fr:journal kind=finding scope=plan id=pr1408-r6 created=2026-11-12T09:18:55+00:00 phase=1 state=open review_scope=in -->
### pr1408-r6 · finding [open] (reviewer: in scope) · A branch's pending amendments are ordered by feature slug, not by the order written, so a branch's own correct sequence across two fragments is refused as stale (phase 1)

PR #1408 review item 6. Amending one row through fragment zz (base 0) then aa (base 1) is refused by the branch's own check/deliver while the same commits on main fold clean. Pending amendments must be ordered the way the merged fold will order them.

<!-- fr:journal kind=finding scope=plan id=pr1408-r7 created=2026-11-12T09:18:57+00:00 phase=4 state=open review_scope=in -->
### pr1408-r7 · finding [open] (reviewer: in scope) · Rendered reports still say 'from docs/acceptance/matrix.yaml' (phase 4)

PR #1408 review item 7, report.py:218,324.

<!-- fr:journal kind=finding scope=plan id=pr1408-r8 created=2026-11-12T09:18:59+00:00 phase=1 state=open review_scope=in -->
### pr1408-r8 · finding [open] (reviewer: in scope) · Merged amendment order is inferred from list position and counts in _introductions, so a list with a later amendment above an earlier one folds in the wrong order (phase 1)

PR #1408 review item 8. merged_row_edits refuses that shape before merge, so reaching it needs a check bypass. Fix if small, else defer with an issue.

<!-- fr:journal kind=finding scope=plan id=pr1408-r9 created=2026-11-12T09:19:00+00:00 phase=2 state=open review_scope=in -->
### pr1408-r9 · finding [open] (reviewer: in scope) · _companions swallows the frozen reader's failure for a pre-v5 matrix, so the uncommitted-changes veto covers only the reports (phase 2)

PR #1408 review item 9 (read only), matrix_fragments.py:213-222. Fix if small, else defer with an issue.

<!-- fr:journal kind=finding scope=plan id=pr1408-r10 created=2026-11-12T09:19:02+00:00 phase=3 state=open review_scope=in -->
### pr1408-r10 · finding [open] (reviewer: in scope) · The record 10->11 hop validates with the live StepRecord via guard_v9_record (phase 3)

PR #1408 review item 10 (read only). Additive today; the artifact-versioning rule's freeze obligation lands on the first removal. Fix if small, else defer with an issue.

<!-- fr:journal kind=finding scope=plan id=pr1408-r1-resolved created=2026-11-12T09:29:29+00:00 state=fixed resolves=pr1408-r1 -->
### pr1408-r1-resolved · finding [fixed] · resolves pr1408-r1: A retired row that became contested can never be cleared: every pending amendment naming a retired row raises FoldError, whatever its base

b9475854b: fold checks every amendment naming a retired row against its revision; a stale pending one is stale_pending, a correctly based one clears contested. Red: test_a_stale_pending_amendment_to_a_retired_row_is_stale_not_an_error, test_a_contested_retired_row_is_cleared_by_a_correctly_based_amendment

<!-- fr:journal kind=finding scope=plan id=pr1408-r2-resolved created=2026-11-12T09:29:31+00:00 state=fixed resolves=pr1408-r2 -->
### pr1408-r2-resolved · finding [fixed] · resolves pr1408-r2: A stale retire that merged anyway is silent: contested.discard runs unconditionally on retire

b9475854b: retire no longer discards contested unconditionally; a stale retire that merged leaves the row retired and contested. Red: test_a_stale_retire_that_merged_anyway_leaves_the_row_contested

<!-- fr:journal kind=finding scope=plan id=pr1408-r3-resolved created=2026-11-12T09:32:31+00:00 state=fixed resolves=pr1408-r3 -->
### pr1408-r3-resolved · finding [fixed] · resolves pr1408-r3: Scaffolded GitHub matrix job checks out with persist-credentials: false, so check's default-ref fetch fails in CI on a private repo and every run is refused

bb30cc024: a failed fetch reads refs/remotes/<default> when the checkout holds it, BranchCheck.source + check's 'default ref:' line name the source; CI with no local ref still refuses. Red: test_a_failed_fetch_in_ci_reads_the_checkouts_local_default_ref_and_says_so

<!-- fr:journal kind=finding scope=plan id=pr1408-r4-resolved created=2026-11-12T09:33:44+00:00 state=fixed resolves=pr1408-r4 -->
### pr1408-r4-resolved · finding [fixed] · resolves pr1408-r4: An in-flight branch whose matrix.yaml holds a row this PR retired gets 'duplicate row ids' with no fix named

2eccfadea: split_texts refuses a matrix row the on-disk fold retired, naming the ids and the fix (delete from matrix.yaml, re-run fr migrate artifacts --yes; new id via fr acceptance add if still needed). Red: test_an_in_flight_matrix_holding_a_retired_row_names_it_and_the_fix

<!-- fr:journal kind=finding scope=plan id=pr1408-r5-resolved created=2026-11-12T09:36:47+00:00 state=fixed resolves=pr1408-r5 -->
### pr1408-r5-resolved · finding [fixed] · resolves pr1408-r5: matrix-parse-libyaml and archive-retargets-matrix-refs, owned by other features, were edited in place after the migration instead of amended

68f14ff5c restores both owners' fragments with git from migration commit ae7791862 (rows equal the split of origin/main's matrix.yaml); 9 amendments in 2026-11-04-repo-feature-settings's fragment (fae5b63df..753c24d93, via fr acceptance amend) re-apply the changes; the effective rows are byte-identical before/after (JSON dump compared). Red: scratch check comparing other features' rows with the split of origin/main's matrix.yaml listed both rows

<!-- fr:journal kind=decision scope=plan id=fold-ties-break-by-base created=2026-11-12T09:39:25+00:00 phase=1 -->
### fold-ties-break-by-base · decision · Fold ties inside one first-parent commit break by base, then feature slug, then list index (supersedes the slug-first tie) (phase 1)

Supersedes the plan's 'ties break by feature slug, then list index' (_prose.md, 01.yaml). R17 orders amendments by the first-parent commit that introduced each and says nothing about ties; a merge commit or a squash lands a whole branch in one commit, so the tie-break decides the order of a branch's own amendments. Slug-first applied a branch's sequence on one row across two fragments (zz base 0, then aa base 1) out of order, contested on merge and refused as stale by the branch's own check (pr1408-r6). Ties now break by base first: amendments to one row written in sequence carry increasing bases (amend defaults to the current revision), so base order is the order written; amendments to different rows do not interact, so their relative order is immaterial. Equal bases (two features' stale amendments) still break by slug, then list index. The pending path uses the same key, so a branch's view orders its own amendments the way their merge will. Plan-level only; no spec change. Implemented in dd2b99806.

<!-- fr:journal kind=finding scope=plan id=pr1408-r6-resolved created=2026-11-12T09:39:26+00:00 state=fixed resolves=pr1408-r6 -->
### pr1408-r6-resolved · finding [fixed] · resolves pr1408-r6: A branch's pending amendments are ordered by feature slug, not by the order written, so a branch's own correct sequence across two fragments is refused as stale

dd2b99806: merged ties and pending amendments both order by (base, feature slug, list index); decision fold-ties-break-by-base. Red: test_a_branchs_own_sequence_across_two_fragments_is_not_stale, test_the_same_sequence_merged_by_merge_commit_folds_clean, test_the_same_sequence_merged_by_squash_folds_clean (the merged fold was contested too)

<!-- fr:journal kind=finding scope=plan id=pr1408-r7-resolved created=2026-11-12T09:42:02+00:00 state=fixed resolves=pr1408-r7 -->
### pr1408-r7-resolved · finding [fixed] · resolves pr1408-r7: Rendered reports still say 'from docs/acceptance/matrix.yaml'

df844f367: render and render_markdown say 'from the folded fragments in docs/acceptance/features/'. Red: test_both_renderings_name_the_folded_fragments_as_their_source

<!-- fr:journal kind=finding scope=plan id=pr1408-r8-resolved created=2026-11-12T09:43:37+00:00 state=fixed resolves=pr1408-r8 -->
### pr1408-r8-resolved · finding [fixed] · resolves pr1408-r8: Merged amendment order is inferred from list position and counts in _introductions, so a list with a later amendment above an earlier one folds in the wrong order

7f72df065: _introductions matches each tip amendment by value (n-th copy -> first commit holding n+1 copies) instead of by index/count. Red: test_an_amendment_inserted_above_a_merged_one_takes_its_own_merge_position

<!-- fr:journal kind=finding scope=plan id=pr1408-r9-resolved created=2026-11-12T09:44:29+00:00 state=fixed resolves=pr1408-r9 -->
### pr1408-r9-resolved · finding [fixed] · resolves pr1408-r9: _companions swallows the frozen reader's failure for a pre-v5 matrix, so the uncommitted-changes veto covers only the reports

d060bb715: _companions falls back to every fragment on disk when split_texts cannot name its own. Red: test_a_pre_v5_matrix_still_names_every_fragment_the_split_may_touch

<!-- fr:journal kind=finding scope=plan id=pr1408-r5-resolved-2 created=2026-11-12T09:47:10+00:00 state=fixed resolves=pr1408-r5 -->
### pr1408-r5-resolved-2 · finding [fixed] · resolves pr1408-r5: matrix-parse-libyaml and archive-retargets-matrix-refs, owned by other features, were edited in place after the migration instead of amended

Corrects the range in the previous record: 68f14ff5c restores both owners' fragments with git from migration commit ae7791862; 13 amendments in 2026-11-04-repo-feature-settings's fragment, 5bdb2c831..753c24d93 (fr acceptance amend: 1 reword, 4 drop-level, 6 add-level, 2 set-status), re-apply the changes; the effective rows are identical before and after (JSON dump compared).
