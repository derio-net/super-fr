<!-- fr:journal-schema=4 -->
# Journal: 2026-11-18-triage-pages-ux

<!-- fr:journal kind=decision scope=plan id=p1-rendered-at-optional created=2026-11-18T20:10:06+00:00 phase=1 -->
### p1-rendered-at-optional · decision · rendered_at is an optional keyword on every render_*; None states no render time (phase 1)

R5 says every page states its render time and the command passes the moment in. Every
command (backlog, batches, origins, architecture, history) passes `datetime.now(UTC)`;
the renderers default `rendered_at=None` (no stamp) so the ~150 existing direct render
calls in tests stay inputs-only. `render_board` already took a required `rendered_at`
and printed it through `components.when`, so it is unchanged.

<!-- fr:journal kind=decision scope=plan id=p1-stage-filter-script-whole created=2026-11-18T20:10:06+00:00 phase=1 -->
### p1-stage-filter-script-whole · decision · FOLD_SCRIPT is renamed STAGE_FILTER_SCRIPT whole; its reveal half moves with the shared fold script (spec §D, phase 2) (phase 1)

§B says the stage filter becomes `STAGE_FILTER_SCRIPT` and the reveal half becomes the
shared fold script of §D. Phase 1 owns no fold script, so the whole constant keeps its
behaviour under the new name and stays on the Backlog only. The Issues page carries
the filter-bar `SCRIPT` and `TABS_SCRIPT`; `SCRIPT` would throw on the Backlog, which
has no `#q` search box.

<!-- fr:journal kind=decision scope=plan id=p1-board-dir-fallback-shared created=2026-11-18T20:10:06+00:00 phase=1 -->
### p1-board-dir-fallback-shared · decision · with only board/ present, both pages read it, fragments included; remove_legacy deletes files, never board/ (phase 1)

`components.fragment_dir` returns the page's own directory when it exists, else its
legacy one (board/ for Backlog and Issues) with a note said on stderr and on the page.
A fragment a board/ manifest lists therefore shows on both pages, which is R3's "the
operator's order and fragments carry over for both pages". `remove_legacy` removes
only the old-named file (triage.html, board.html); the old directory stays an input.
The moved-section note is shared too: `fragments.moved_notes` names the page by its
registry title, used by Backlog, Issues, History and Architecture (whose MOVED maps
now hold page keys: waves and operator-actions map to `backlog`).

<!-- fr:journal kind=discovery scope=plan id=p1-tests-in-own-file created=2026-11-18T20:10:06+00:00 phase=1 -->
### p1-tests-in-own-file · discovery · the R4/R5 tests live in tests/unit/test_triage_pages_split.py, not test_triage_render.py (phase 1)

The split and the per-renderer stamp test import every renderer; a separate module
keeps test_triage_render.py's captured-fixture tests apart. Existing callers of the
removed `render()` were migrated to the page that owns the section they assert on
(Issues for rows, tiers, PRs, debt, awaiting live, closed in progress; Backlog for
needs, next up, waves, batches, session notes, merge stops).

<!-- fr:journal kind=discovery scope=plan id=p1-scenarios-name-the-pages created=2026-11-18T20:10:06+00:00 phase=1 -->
### p1-scenarios-name-the-pages · discovery · the shell scenarios under tests/scenarios/ also named the old pages and commands (phase 1)

The first full suite failed five `tests/integration/test_scenarios.py` cases
(triage-nav-pages, triage-config-skew, triage-cancelled-terminal, merge-train-label-gate,
merge-train-red-recovery): their scripts ran `fr triage render|board` and read
triage.html/board.html, and the nav scenario expected no Issues entry. They now use
`fr triage backlog|batches`, the new files and the six-page nav. The page-name tripwire
covers only the Python modules, so a later rename should grep tests/scenarios/ too.

<!-- fr:journal kind=discovery scope=plan id=p1-kinds-filter-owed-by-phase-2 created=2026-11-18T20:10:06+00:00 phase=1 -->
### p1-kinds-filter-owed-by-phase-2 · discovery · the triage-backlog-issues-split interactions kinds-toggle-several and kinds-none-selected are owed by phase 2 (R13) (phase 1)

The row declares two interactions on the Waves kind filter (R13), which phase 2 builds:
in phase 1 the Waves section has kind counts and no toggle. Phase 1's shots cover the
states backlog-page, issues-page and waves-all-kinds (the Waves section as it renders
now, every kind shown). No shot names the two interactions, because no page can show
them yet, so `fr.run.visual` will refuse this row until phase 2 captures them.

<!-- fr:journal kind=finding scope=plan id=p1-batches-footer-old-command created=2026-11-18T20:10:06+00:00 phase=1 state=fixed review_scope=in -->
### p1-batches-footer-old-command · finding [fixed] (reviewer: in scope) · the Batches page footer still said fr triage board (phase 1)

Found by opening the screenshots: kanban_render.py's footer named `fr triage board`,
and the drive_lock.py and snapshot.py docstrings named the old commands. Fixed in
"fix(triage): the Batches footer names fr triage batches", with a footer test per
Backlog, Issues and Batches in tests/unit/test_triage_pages_split.py.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-18T20:10:06+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a smoke run and a change fragment: no code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-18T20:10:06+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the commands were written on the registry helpers (fragment_dir, remove_legacy, moved_notes) from the start, so no duplicate was left to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-18T20:10:06+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

one keyword per renderer, printed through components.when; history's own _stamp now delegates to it, nothing else to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-11-18T20:10:06+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

docs and mirrors only: no code

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-18T20:58:14+00:00 phase=1 -->
### review-p1 · review · phase 1 review: 3 findings, all in scope, all fixed (phase 1)

Independent reviewer (separate context, read-only) over the spec's R1-R5, plan phase 1 and diff 8a84988c3..48e8c5409. Ran sync-opencode/sync-hermes/sync-readme --check, fr docs check, ruff and mypy on the touched files, and 301 targeted tests, all green. It grepped for the old names, and took its own fresh screenshots of all six pages' stamps (light/dark, 1280/390). Fixes in 5f6faf052 (p1-r1), e5455e365 (p1-r2) and c7ad6a19f (p1-r3). Full suite after the fixes: 16520 passed, 121 skipped (p1-suite3.log).

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-18T20:58:14+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · backlog/ and issues/ fragment dirs missing from state_ref.REF_FILES and state_sync.DURABLE_DIRS, so authored Backlog/Issues fragments were never exported or synced (phase 1)

Raised by the phase 1 reviewer at packages/fr/src/fr/triage/state_ref.py:53-69 and state_sync.py:54.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-18T20:58:14+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · The board/ fallback rule disagreed three ways: spec R3, the code and the skill/README; the case with backlog/ present and issues/ absent was untested (phase 1)

Raised by the phase 1 reviewer at components.py:336 against spec R3, fr-triage SKILL.md:15 and docs/triage/README.md:21.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-18T20:58:14+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · The Origins/Architecture/History mastheads showed "rendered <stamp>" right beside "rendered by fr triage … render" (phase 1)

Raised by the phase 1 reviewer at origins.py:818, architecture.py:376 and history.py:194.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-18T20:58:14+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: backlog/ and issues/ fragment dirs missing from state_ref.REF_FILES and state_sync.DURABLE_DIRS, so authored Backlog/Issues fragments were never exported or synced (phase 1)

5f6faf052: REF_FILES and DURABLE_DIRS carry backlog/ and issues/ (board/ kept as fallback input); pins, the docs/triage README and spec R3 updated.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-18T20:58:14+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: The board/ fallback rule disagreed three ways: spec R3, the code and the skill/README; the case with backlog/ present and issues/ absent was untested (phase 1)

e5455e365: spec R3, the skill (mirrors re-synced) and the README state the per-page rule the code already had; the test now asserts that Issues reads board/ when backlog/ alone exists.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-18T20:58:14+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: The Origins/Architecture/History mastheads showed "rendered <stamp>" right beside "rendered by fr triage … render" (phase 1)

c7ad6a19f: components.rendered_by() gives one span 'rendered <stamp> by <code>…</code>', with the old label when no stamp; both forms pinned, test red before the fix.

<!-- fr:journal kind=decision scope=plan id=p2-debt-fold-no-count created=2026-11-18T22:05:19+00:00 phase=2 -->
### p2-debt-fold-no-count · decision · the Issues Debt fold shows no count (phase 2) (phase 2)

The per-repo debt folds inside it carry the totals; a count of repos on the outer fold read as the debt badge and broke the visible-sum test's meaning.

<!-- fr:journal kind=decision scope=plan id=p2-next-up-reason-drops-wave created=2026-11-18T22:05:19+00:00 phase=2 -->
### p2-next-up-reason-drops-wave · decision · Next up's reason no longer names the wave or the dependencies (phase 2) (phase 2)

NextRow.wave is its own linked tag and the deps tag links each dependency, so the reason keeps only the merge order, or 'the driver starts it next'. test_next_up_carries_tier_size_dependencies_and_the_reason now asserts the field.

<!-- fr:journal kind=discovery scope=plan id=p2-sections-are-folds-tests-read-elements created=2026-11-18T22:05:19+00:00 phase=2 -->
### p2-sections-are-folds-tests-read-elements · discovery · Backlog/Issues sections are folds, so tests read an element by id with depth counting (phase 2) (phase 2)

Section ids moved onto the details element. tests/unit/triage_board_fixtures.element_by_id returns the whole element, nested same-tag elements counted; test_triage_board_views and test_triage_render use it.

<!-- fr:journal kind=discovery scope=plan id=p2-visual-rows-history-architecture created=2026-11-18T22:05:19+00:00 phase=2 -->
### p2-visual-rows-history-architecture · discovery · this phase also owes the History PR and Architecture pipeline-tab rows (phase 2) (phase 2)

R16 and R17 are this phase's, so triage-history-pr-summary and triage-architecture-pipeline-tabs are owed here and covered below: the PR cell with link, title and merge date, the dash for a batch with no PR, the pipeline as one graph on its latest tab, and stepping through the dated tabs. Batches columns and Origins groups are phase 3's and were not touched.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-18T22:05:19+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

collapsed() was replaced outright by fold() and the fold CSS split out of CHROME_CSS; nothing left to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-18T22:05:19+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

fragment loading was folded into one load() helper shared by files and fold-group members while the group was added

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-11-18T22:05:19+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

inline() was rewritten once with a plain() helper for both bold and top level; no duplicate left

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-11-18T22:05:19+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

one KIND_FILTER_SCRIPT constant and one wave_table kinds helper; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t5 created=2026-11-18T22:05:19+00:00 phase=2 -->
### no-refactor-p2-t5 · discovery · no-refactor-because P2.T5 (phase 2)

wave_table gained one optional prs argument; History passes it, no duplicate cell code

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t6 created=2026-11-18T22:05:19+00:00 phase=2 -->
### no-refactor-p2-t6 · discovery · no-refactor-because P2.T6 (phase 2)

browser check and suite only: no code

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-11-18T23:08:29+00:00 phase=2 -->
### review-p2 · review · phase 2 review: 7 findings (6 in, 1 out), all fixed (phase 2)

Independent reviewer (separate context, read-only) over spec R8, R9, R11-R13, R16, R17, plan phase 2 and diff 45f8e3ff3..613422f0b. Probed R11 with hostile prose (script tags, javascript: URLs, quote breaks, refs in code spans, non-github and look-alike bases): no XSS. Ran 330 targeted tests, ruff, mypy and fr docs check, all clean. Walked every state and interaction of the five visual rows in a real browser with its own fresh screenshots. Fixes: 700772602 (r1), f3aff71db (r2), 127ebf56f (r3), 84a27b7e9 (r4), 8163abda3 (r5), 7be908ff2 (r6), 4809de179 (r7). Full suite after the fixes: 16577 passed, 121 skipped (p2-suite2.log). The implementer wrote the phase's first commit before its tests (no red step), which is why r5 targeted test strength; the fixes were made test-first.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-18T23:08:29+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · R11 incomplete: issue-key lists (wave Issues column, batch card members, pattern/feature ids) stayed plain text (phase 2)

Raised by the phase 2 reviewer at render.py:1080, :807, :890.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-18T23:08:29+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · R12 incomplete: the wave table's Depends on batch ids were not linked to their cards (phase 2)

Raised by the phase 2 reviewer at render.py:1083.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-18T23:08:29+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · STAGE_FILTER_SCRIPT kept its own open-and-scroll reveal, duplicating FOLD_SCRIPT (phase 2)

Raised by the phase 2 reviewer at render.py:345-357, against P2.T1.S2 and decision p1-stage-filter-script-whole.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-18T23:08:29+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · A test named for the finished-wave case asserted the unfinished one; the finished branch in Next up was unreachable (phase 2)

Raised by the phase 2 reviewer at render.py:1012 and tests/unit/test_triage_board_views.py:851.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-18T23:08:29+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · Tab-hash, fold-reveal and kind-filter tests grepped the JS source, and the archived-notes test sliced the page: they would pass against broken behaviour (phase 2)

Raised by the phase 2 reviewer at tests/unit/test_triage_components.py:104, :114, test_triage_board_views.py:913 and test_triage_history.py.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-11-18T23:08:29+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · _REF linked #n inside an escaped literal entity (&#12;) (phase 2)

Raised by the phase 2 reviewer at components.py:591; cosmetic, not XSS.

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-11-18T23:08:29+00:00 phase=2 state=open review_scope=out -->
### p2-r7 · finding [open] (reviewer: out of scope) · Architecture's issue list built an href from i.url with no https-only check (phase 2)

Raised by the phase 2 reviewer at architecture.py:238; predates this change.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-18T23:08:29+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: R11 incomplete: issue-key lists (wave Issues column, batch card members, pattern/feature ids) stayed plain text (phase 2)

700772602: Linker.key_link/key_links render known keys as https-only links in the wave Issues column (Backlog and History), batch card members, pattern and feature ids; test-first.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-18T23:08:29+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: R12 incomplete: the wave table's Depends on batch ids were not linked to their cards (phase 2)

f3aff71db: Depends on links each batch id to backlog.html#batch-<id>; test seen failing first.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-18T23:08:29+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: STAGE_FILTER_SCRIPT kept its own open-and-scroll reveal, duplicating FOLD_SCRIPT (phase 2)

127ebf56f: the stage script only switches the target's stage and calls apply(); a test pins that open/scroll lives only in FOLD_SCRIPT.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-18T23:08:29+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: A test named for the finished-wave case asserted the unfinished one; the finished branch in Next up was unreachable (phase 2)

84a27b7e9: the unreachable branch is removed (Next up lists only non-terminal batches); the test is renamed and asserts no History link.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-18T23:08:29+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: Tab-hash, fold-reveal and kind-filter tests grepped the JS source, and the archived-notes test sliced the page: they would pass against broken behaviour (phase 2)

8163abda3: the tests pin the structure the scripts act on (aria-controls targets exist, default tab selected, ids inside their details, toggles start pressed, data-kinds from the closed set, empty message hidden, archived-notes fold closed and holding all three fragments). Playwright is not a project dependency, so the scripts' behaviour is evidenced by the reviewer's browser walk recorded in visual below.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-11-18T23:08:29+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: _REF linked #n inside an escaped literal entity (&#12;) (phase 2)

7be908ff2: _REF refuses a match preceded by &amp;; test added.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-11-18T23:08:29+00:00 phase=2 state=fixed resolves=p2-r7 -->
### p2-r7-resolved · finding [fixed] · resolves p2-r7: Architecture's issue list built an href from i.url with no https-only check (phase 2)

4809de179: Architecture issue links go through _safe_url (https only), with a javascript: test. Older code, fixed here because it is one line and the security lens covers it.
