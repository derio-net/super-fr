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
