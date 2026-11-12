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
