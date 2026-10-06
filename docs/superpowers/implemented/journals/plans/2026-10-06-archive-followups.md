# Journal: 2026-10-06-archive-followups

<!-- fr:journal kind=discovery scope=plan id=p1-wrapper-decorator created=2026-10-06T17:40:04+00:00 phase=1 -->
### p1-wrapper-decorator · discovery · follow-ups wired by a signature-preserving decorator, not an edited body (phase 1)

`archive_command` keeps its typer signature; `_with_followups` (functools.wraps) opens the MoveLog and runs `_after_moves` in a finally, so every entry mode and exit path is covered without touching the body. Typer follows __wrapped__.

<!-- fr:journal kind=discovery scope=plan id=p1-green-in-smoke created=2026-10-06T17:40:04+00:00 phase=1 -->
### p1-green-in-smoke · discovery · MoveLog/recording_moves landed with the T1 smoke commit (phase 1)

T1's stub was the real implementation (a few lines), so T2's RED test passed on first run; the RED for the seam is the import test in T1 and the CLI-level `_after_moves` spies in T3, which failed before the wrapper existed.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-06T17:52:08+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · refresh_archived parses every archived cursor before checking for unpriced sessions (phase 1)

backfill.py:156-163; every archive parsed 67 cursors.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-06T17:52:08+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Permanently-unpriced sessions re-read on every archive, unbounded (phase 1)

backfill.py:121-130 via archive_cmd.py:406; 28 of 67 usage files carry usd null.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-06T17:52:08+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · skip=paths_dirty treats staged-only changes as uncommitted edits (phase 1)

archive_cmd.py:406, archive.py:356-364.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-06T17:52:08+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · No _after_moves test for --branch nor --all owed-only path (phase 1)

test_archive_followups.py:103-150; P1.T3.S1, spec §0.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-10-06T17:52:08+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · --sweep-only spy test passes on an empty log (phase 1)

test_archive_followups.py:127.

<!-- fr:journal kind=review scope=plan id=p1-review-r1 created=2026-10-06T17:52:08+00:00 phase=1 -->
### p1-review-r1 · review · phase 1 code review: 5 findings (phase 1)

Independent reviewer (feature-dev:code-reviewer, opus) over spec §0/§A, 01.yaml and the phase-1 diff. Raised p1-r1..p1-r5, all in scope; each verified against the code and fixed with a test (ab267ee70, 53b901337). Suite after fixes: 9703 passed, 105 skipped.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-06T17:52:08+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: refresh_archived parses every archived cursor before checking for unpriced sessions (phase 1)

Fixed in ab267ee70: load_usage + unpriced check first; the cursor is parsed only when needed (test: a priced file with an unparseable cursor is skipped).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-06T17:52:08+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Permanently-unpriced sessions re-read on every archive, unbounded (phase 1)

Fixed in ab267ee70: max_age_days=30 on the archive path (spec R1 amended in 2df521c3d); backfill stays unbounded; both sides of the bound tested.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-06T17:52:08+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: skip=paths_dirty treats staged-only changes as uncommitted edits (phase 1)

Fixed in ab267ee70: _edited_in_worktree via git diff --quiet; a real refresh of a staged-unedited file is tested.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-06T17:52:08+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: No _after_moves test for --branch nor --all owed-only path (phase 1)

Fixed in 53b901337: --branch and --all owed-debug-journal spy tests added.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-10-06T17:52:08+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: --sweep-only spy test passes on an empty log (phase 1)

Fixed in 53b901337: the fixture really moves a spec and the spy asserts [True].

<!-- fr:journal kind=decision scope=plan id=p2-dirty-is-worktree-vs-index created=2026-10-06T18:12:15+00:00 phase=2 -->
### p2-dirty-is-worktree-vs-index · decision · matrix retarget dirty check is worktree-vs-index, not paths_dirty (phase 2)

Reuses phase 1's _edited_in_worktree (git diff --quiet) for matrix.yaml and the three reports, so a staged-only change is not an edit; consistent with p1-r3. A dirty file raises inside the step and surfaces as the standard `note: matrix retarget skipped` line; nothing is written.

<!-- fr:journal kind=discovery scope=plan id=p2-baseline-was-120-refs created=2026-10-06T18:12:15+00:00 phase=2 -->
### p2-baseline-was-120-refs · discovery · the zero baseline held 120 stale archived refs, not one (phase 2)

fr acceptance check showed twin warnings for 20 distinct archived specs/journals across 120 refs (many with #fragments), not only the spec-ref-writers ref. All were retargeted with retarget_text (moves derived from the warnings, fragment stripped) plus `fr acceptance report --deterministic`; the matrix diff touches only `super-fr:docs/superpowers` ref lines and check now prints no twin warning.

<!-- fr:journal kind=discovery scope=plan id=p2-flow-lists-not-retargeted created=2026-10-06T18:12:15+00:00 phase=2 -->
### p2-flow-lists-not-retargeted · discovery · retarget_text handles block-list refs only (per spec) (phase 2)

Flow-style `origin: [..]` lists are not rewritten (spec §B names block-list items). The matrix writers emit block lists, so none exist in the real matrix; a flow list would simply keep warning in check rather than be corrupted.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-10-06T18:12:15+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

the step is one short function reusing phase 1's _edited_in_worktree; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-10-06T18:12:15+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

a one-string reword of an existing warning; nothing to clean

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-06T18:32:30+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · _verify adds origin to rows that omit it, so any such row makes every retarget raise (phase 2)

retarget.py:126; model.py:186 allows rows without origin.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-06T18:32:30+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · The retarget refusal prints note: with the exception type instead of a warning: line (phase 2)

archive_cmd.py:399/471 vs spec §B/R6.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-10-06T18:32:30+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · No test exercises _verify's equality-mismatch branch with real input (phase 2)

test_acceptance_retarget.py:93 covers only the YAML-error branch; the archive test mocks retarget_text.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-10-06T18:32:30+00:00 phase=2 state=open review_scope=out -->
### p2-r4 · finding [open] (reviewer: out of scope) · Main archived verification-strategies (#1035), so the branch's 31 live refs to it become twin warnings after a rebase (phase 2)

matrix.yaml:6884-7072; e407f87bd on main.

<!-- fr:journal kind=review scope=plan id=p2-review-r1 created=2026-10-06T18:32:30+00:00 phase=2 -->
### p2-review-r1 · review · phase 2 code review: 4 findings (phase 2)

Independent reviewer (feature-dev:code-reviewer, opus) over spec §0/§B, 02.yaml and the phase-2 code. Raised p2-r1..p2-r3 (in scope, all fixed with tests: 3ff279232, f8ee87e7c) and p2-r4 (out of scope). Suite after fixes: 9719 passed, 105 skipped.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-06T18:32:30+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: _verify adds origin to rows that omit it, so any such row makes every retarget raise (phase 2)

Fixed in 3ff279232: only present keys are mapped; a test with a row lacking origin (red before the fix).

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-06T18:32:30+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: The retarget refusal prints note: with the exception type instead of a warning: line (phase 2)

Fixed in f8ee87e7c: _retarget_matrix prints `warning: matrix retarget skipped — <reason>`; tests pin the prefix and the absence of the type name.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-10-06T18:32:30+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: No test exercises _verify's equality-mismatch branch with real input (phase 2)

Fixed in 3ff279232: a walker-skipped `# keep` item next to a rewritten one raises RetargetError.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-10-06T18:32:30+00:00 phase=2 state=open resolves=p2-r4 out_of_scope=true -->
### p2-r4-resolved · finding [out-of-scope] · resolves p2-r4: Main archived verification-strategies (#1035), so the branch's 31 live refs to it become twin warnings after a rebase (phase 2)

Not caused by this change: concurrent main work archived that spec after this branch was cut. The orchestrator rebases onto main at deliver and re-runs the retarget so the baseline stays zero.

<!-- fr:journal kind=decision scope=plan id=p3-validate-in-wrapper created=2026-10-06T18:57:12+00:00 phase=3 -->
### p3-validate-in-wrapper · decision · --issues with --no-issues is refused in the _with_followups wrapper (phase 3)

The usage error fires in the decorator before recording_moves opens, so nothing moves and no follow-up runs (the finally would otherwise honour the explicit qids). Exit 2.

<!-- fr:journal kind=decision scope=plan id=p3-services-text-shared created=2026-10-06T18:57:12+00:00 phase=3 -->
### p3-services-text-shared · decision · closeout.services_invalid_text is the one invalid-services wording (phase 3)

The brief and archive's open-ends step both print it; the brief appends its own suffix about the --issues line.

<!-- fr:journal kind=discovery scope=plan id=p3-skill-resolve-example-gone created=2026-10-06T18:57:12+00:00 phase=3 -->
### p3-skill-resolve-example-gone · discovery · fr-goal keeps no fr journal resolve example any more (phase 3)

The close-out line was the only one, so test_the_scan_finds_the_fr_goal_examples became a pin that fr-goal routes through fr archive --issues and carries no resolve example.

<!-- fr:journal kind=discovery scope=plan id=p3-explainer-regenerated created=2026-10-06T18:57:12+00:00 phase=3 -->
### p3-explainer-regenerated · discovery · 01-fr-goal.html regenerated (phase 3)

The unmodified render was byte-identical to the committed html first (from /, --isolated); the edited render then differs only in the close-out paragraph. Nothing owed.

<!-- fr:journal kind=discovery scope=plan id=p3-explicit-qid-no-moves created=2026-10-06T18:57:12+00:00 phase=3 -->
### p3-explicit-qid-no-moves · discovery · explicit --issues <qids> runs the open-ends step on an empty move log (phase 3)

_after_moves now builds its step list: usage/matrix only on a non-empty log, open ends when the log is non-empty or --issues is given.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-10-06T18:57:12+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

the extraction itself was the refactor; apply.py lost its inline builder and the duplicate _CARRIED_OPEN

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-10-06T18:57:12+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

new pure module with no duplication to remove

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t4 created=2026-10-06T18:57:12+00:00 phase=3 -->
### no-refactor-p3-t4 · discovery · no-refactor-because P3.T4 (phase 3)

the closeout change replaced one line shape with another; the shared services_invalid_text helper was extracted in T3

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-10-06T19:20:01+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · Marker dedup adopts any open issue carrying the marker, regardless of author (tracked_by hijack) (phase 3)

archive_followups.py:179-193/217-219.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-10-06T19:20:01+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · Issue Context lists every moved spec/plan on every issue, and none for explicit qids with nothing moved (phase 3)

archive_cmd.py:544-548.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-10-06T19:20:01+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · No test compares archive's deferred record with what fr journal resolve --state deferred writes (phase 3)

tests/unit/test_archive_open_ends.py:33-52.

<!-- fr:journal kind=review scope=plan id=p3-review-r1 created=2026-10-06T19:20:01+00:00 phase=3 -->
### p3-review-r1 · review · phase 3 code review: 3 findings (phase 3)

Independent reviewer (feature-dev:code-reviewer, opus) over spec §0/§C, 03.yaml and the phase-3 code, briefed on the forge-trust question. Raised p3-r1 (security), p3-r2 and p3-r3, all in scope and fixed with tests in a88cc2386; also applied the below-threshold resolution_entry scope note (the journal scope is passed explicitly). Suite after fixes: 9751 passed, 106 skipped.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-10-06T19:20:01+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: Marker dedup adopts any open issue carrying the marker, regardless of author (tracked_by hijack) (phase 3)

Fixed in a88cc2386: reuse only when author == viewer_login() and the marker is the final body line; viewer/listing error → no dedup; parametrized tests. Spec R11 narrowed in 3bf8ef7f9.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-10-06T19:20:01+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: Issue Context lists every moved spec/plan on every issue, and none for explicit qids with nothing moved (phase 3)

Fixed in a88cc2386: context_for(repo_root, end) derives it per finding (plan dir / spec file, live or archived; none for debug); tests for --all with two plans and empty-log qids. Spec §C wording updated in 3bf8ef7f9.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-10-06T19:20:01+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: No test compares archive's deferred record with what fr journal resolve --state deferred writes (phase 3)

Fixed in a88cc2386: a parity test defers through the real CLI and through write_back; serialized entries match with created stripped.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved-2 created=2026-10-06T20:31:27+00:00 state=fixed resolves=p2-r4 -->
### p2-r4-resolved-2 · finding [fixed] · resolves p2-r4: Main archived verification-strategies (#1035), so the branch's 31 live refs to it become twin warnings after a rebase

Handled at deliver: the branch was rebased onto main and retargeted, so all 27 verification-strategies refs on main name implemented/specs and fr acceptance check reports no twin warnings (checked at closeout, 2026-10-06).
