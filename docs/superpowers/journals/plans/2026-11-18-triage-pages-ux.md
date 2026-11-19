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

<!-- fr:journal kind=decision scope=plan id=p3-collect-reuses-the-pr-read created=2026-11-19T00:31:53+00:00 phase=3 -->
### p3-collect-reuses-the-pr-read · decision · origins collect keeps merged PRs from the one PR list it already reads, not a second merged-state read (phase 3)

collect_origins already lists PRs (state all) once per repo for the closing-PR map; MergedPr rows come from that same read, kept when merged_at is on or after --since. R15 asks for one list read per repo, and a second one would break it. A short page already refuses the whole collect, so no extra truncation warning is needed.

<!-- fr:journal kind=decision scope=plan id=p3-origins-pr-links-use-issues-url created=2026-11-19T00:31:53+00:00 phase=3 -->
### p3-origins-pr-links-use-issues-url · decision · an Origins PR reference the facts do not hold links to the github.com issues route, not pull (phase 3)

Origins' PR links go through the Linker (R11), so an unknown number on a github.com base links to /issues/<n>, which GitHub redirects. A PR in prs links to its own url. test_related_pr_cell asserts the issues route.

<!-- fr:journal kind=decision scope=plan id=p3-terminal-is-the-done-column created=2026-11-19T00:31:53+00:00 phase=3 -->
### p3-terminal-is-the-done-column · decision · the cutoff's terminal is the Done column (phase 3)

Card.terminal is column == done (cancelled, abandoned, merged and archived), the same set finished_waves uses; a merged batch still owed its close-out is not terminal. cutoff_hidden_waves is the Python statement of the rule the script applies.

<!-- fr:journal kind=discovery scope=plan id=p3-scope-key-is-the-scope-name created=2026-11-19T00:31:53+00:00 phase=3 -->
### p3-scope-key-is-the-scope-name · discovery · the storage key carries the scope name, owner--repo (phase 3)

body data-scope is Board.scope, which is the directory-safe name, so keys read fr-triage:example-org--widgets:col:running and fr-triage:example-org--widgets:cutoff.

<!-- fr:journal kind=discovery scope=plan id=p3-column-test-helpers-matched-the-old-class created=2026-11-19T00:31:53+00:00 phase=3 -->
### p3-column-test-helpers-matched-the-old-class · discovery · a kanban cmd test helper and a shell scenario matched the exact column class (phase 3)

test_triage_kanban_cmd._column and tests/scenarios/triage-cancelled-terminal.sh matched class=col; a collapsed column adds a class, so both now allow more classes.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-11-19T00:31:53+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

the gh#1417 empty-column rule was replaced by the collapsed-state rule in the same edit; nothing left over

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-19T00:31:53+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

one pure helper and one script block; no duplicate of the rule

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-11-19T00:31:53+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

collect reuses the PR list it already read; no second read or code path to tidy

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t5 created=2026-11-19T00:31:53+00:00 phase=3 -->
### no-refactor-p3-t5 · discovery · no-refactor-because P3.T5 (phase 3)

browser check, docs and suite only: no code

<!-- fr:journal kind=review scope=plan id=review-p3 created=2026-11-19T02:13:14+00:00 phase=3 -->
### review-p3 · review · Phase 3 review: Batches columns and cutoff, Origins groups, filter and merged PRs (phase 3)

Independent review of da54b59dc..73ce5d5a1 against R10, R14, R15, R18, design D/G/H, plan 03.yaml
and the three visual rows, with the reviewer's own browser walk (26 shots, light/dark 1280, light 390,
a legacy origins file with no prs, storage blocked). Holds: column toggles with aria-expanded and
remembered state; storage try/catch; the cutoff hides only terminal waves idle past 30 days; Origins
groups folded in CATEGORIES order with counts, the state filter's counts, a hash opening only its fold;
merged PRs kept from the one PR read, "not collected" for a missing one; escaping and https-only hrefs;
reuse of fold, Linker, stamp_text, PAGE_SCRIPT; docs accurate. Five findings, all in scope, all fixed.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-19T02:13:14+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · Column-toggle and cutoff browser logic tested only by searching script text (phase 3)

cutoff_hidden_waves was a Python copy no render path called; the JS date rule could drift with tests green.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-19T02:13:14+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · Card.terminal narrower than R18's merged, archived, cancelled or abandoned (phase 3)

column == "done" left a merged batch that never archived visible past the cutoff indefinitely.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-19T02:13:14+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · origins collect silently drops a PR created before --since but merged inside the window (phase 3)

The PR list is creation-ordered; a long-lived PR beyond the page is lost with no warning.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-11-19T02:13:14+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · Origins Ended cell renders closing PRs as bare #n text (phase 3)

Linker.from_origins holds their URLs; R11 says every PR reference links to the forge.

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-11-19T02:13:14+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · State filter leaves a header-only table when it hides every row of a group (phase 3)

A group empty at render shows "No issue."; the filtered-empty state should match.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-19T02:13:14+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: Column-toggle and cutoff browser logic tested only by searching script text (phase 3)

f23c85d65: render marks cards of hidden waves with data-cutoff-hidden from cutoff_hidden_waves; the script only applies the marker. Tests pin the boundary and the selectors the script reads.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-19T02:13:14+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: Card.terminal narrower than R18's merged, archived, cancelled or abandoned (phase 3)

cbbf53400: Card.terminal reads the engine's stage and close-out state: merged, cancelled, abandoned or archived. One test per terminal kind.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-19T02:13:14+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: origins collect silently drops a PR created before --since but merged inside the window (phase 3)

29cc2550d (+2bc8e717a): a full PR list warns, naming the repo, that an older PR merged in the window may show not collected; documented in fr-triage.md.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-11-19T02:13:14+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: Origins Ended cell renders closing PRs as bare #n text (phase 3)

6ff3c2399: closing PRs in the Ended cell link through the Linker, https only.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-11-19T02:13:14+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: State filter leaves a header-only table when it hides every row of a group (phase 3)

6070901a6: each group carries a hidden No issue. row the state filter shows when no row is visible.

<!-- fr:journal kind=decision scope=plan id=p4-wave-finish-is-owed-until-the-pages-are-written created=2026-11-19T04:01:56+00:00 phase=4 -->
### p4-wave-finish-is-owed-until-the-pages-are-written · decision · a wave finish is remembered until a page-writing pass sees it (phase 4) (phase 4)

run_pass compares the previous pass's unfinished set with the new one before reassigning
self._unfinished and sets _wave_owed; the pass that writes the pages takes and clears it.
A wave that finishes on an essential-only pass (no pages written) is therefore not lost:
the next page-writing pass stores the snapshot and re-measures Architecture. A pass that
writes pages with no wave owed stores none after the first.

<!-- fr:journal kind=decision scope=plan id=p4-writers-read-state-without-sync created=2026-11-19T04:01:56+00:00 phase=4 -->
### p4-writers-read-state-without-sync · decision · the page writers read the state directory without a ref sync (phase 4) (phase 4)

write_backlog/history/origins/architecture load facts through _load_state(read_only=True):
the command resolves and syncs the state directory once, so the driver's five writers do
not each fetch the state ref in a pass. A broken manifest or state file raises TriageError
from the writer; each command turns it into its exit 2, the driver into one warning.

<!-- fr:journal kind=discovery scope=plan id=p4-first-snapshot-needs-distinct-clock-reads created=2026-11-19T04:01:56+00:00 phase=4 -->
### p4-first-snapshot-needs-distinct-clock-reads · discovery · store_snapshot names a file by the second, so a test clock must move between stores (phase 4) (phase 4)

Snapshots are named by the stored moment, so a frozen fake clock overwrites one file.
tests/unit/test_triage_drive_pages.py moves its clock one hour per read.

<!-- fr:journal kind=discovery scope=plan id=p4-a-drive-ends-when-its-last-wave-finishes created=2026-11-19T04:01:56+00:00 phase=4 -->
### p4-a-drive-ends-when-its-last-wave-finishes · discovery · a loop whose every batch is cancelled ends on the pass that finds the wave finished (phase 4) (phase 4)

The wave-finish snapshot test therefore asserts the count after the drive returns, not from
a hook after that pass.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t2 created=2026-11-19T04:01:56+00:00 phase=4 -->
### no-refactor-p4-t2 · discovery · no-refactor-because P4.T2 (phase 4)

_write_pages is new code beside _write_board; the four command bodies were already lifted into writers in T1, so there was nothing left to tidy

<!-- fr:journal kind=review scope=plan id=review-p4 created=2026-11-19T04:53:11+00:00 phase=4 -->
### review-p4 · review · Phase 4 review: the driver re-renders every page and snapshots at a wave's finish (phase 4)

Independent review of 2adefd2..a322faa42 against R6, R7 and design §C, after reading batch_drive.py,
driver.py, the drive loop in triage_batch_cmd.py and fr triage drive pass end to end. Holds: the drive
pass stays pure; pages are written only on --yes passes that are neither quiet nor essential-only; Origins
and Architecture wait for their inputs; per-page failure sets warn once per cause; atomic writes; the
refactored commands keep their output, refusals and warnings; the cloud loader and ci_none are passed.
Five findings, all in scope, all fixed: chiefly the drive's page memory now persists in drive-pages.json,
carried by the state ref, so host restarts and cloud wakes keep the R6/R7 rules.

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-11-19T04:53:11+00:00 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · A single-repo scope with no usable clone prints a red error line every pass (phase 4)

_scope_clone went through _open_checkout/_fail, printing before raising, uncached and not once per cause.

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-11-19T04:53:11+00:00 phase=4 state=open review_scope=in -->
### p4-r2 · finding [open] (reviewer: in scope) · The cloud driver builds a fresh _Driver per wake, losing the drive's page memory (phase 4)

Architecture re-measured every wake, a snapshot whenever the board changed, and the wave-finish rule never fired.

<!-- fr:journal kind=finding scope=plan id=p4-r3 created=2026-11-19T04:53:11+00:00 phase=4 state=open review_scope=in -->
### p4-r3 · finding [open] (reviewer: in scope) · Docs state the measurement and snapshot rules without saying they held only for the host loop (phase 4)

fr-wave-driver.md and docs/triage/README.md misled a cloud-driver reader.

<!-- fr:journal kind=finding scope=plan id=p4-r4 created=2026-11-19T04:53:11+00:00 phase=4 state=open review_scope=in -->
### p4-r4 · finding [open] (reviewer: in scope) · A wave-finish snapshot is lost on an early drive exit or a failing Backlog write (phase 4)

The finish was seen only by a later pass the drive might not run, and the owed flag was cleared before the write.

<!-- fr:journal kind=finding scope=plan id=p4-r5 created=2026-11-19T04:53:11+00:00 phase=4 state=open review_scope=in -->
### p4-r5 · finding [open] (reviewer: in scope) · The purity test only greps for datetime.now (phase 4)

Other clock, git or subprocess use in batch_drive.py passed it.

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-11-19T04:53:11+00:00 phase=4 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: A single-repo scope with no usable clone prints a red error line every pass (phase 4)

f7427b4f8: _scope_clone probes with _checkout_refusal once per driver, caches hit or miss, and a miss is one once-per-cause warning.

<!-- fr:journal kind=finding scope=plan id=p4-r2-resolved created=2026-11-19T04:53:11+00:00 phase=4 state=fixed resolves=p4-r2 -->
### p4-r2-resolved · finding [fixed] · resolves p4-r2: The cloud driver builds a fresh _Driver per wake, losing the drive's page memory (phase 4)

209f66595: drive-pages.json (fr/triage/drive_pages.py) holds the unfinished waves, the owed flag and the serialised measurement, written atomically and carried by state_ref.REF_FILES; two drives in sequence keep the rules.

<!-- fr:journal kind=finding scope=plan id=p4-r3-resolved created=2026-11-19T04:53:11+00:00 phase=4 state=fixed resolves=p4-r3 -->
### p4-r3-resolved · finding [fixed] · resolves p4-r3: Docs state the measurement and snapshot rules without saying they held only for the host loop (phase 4)

958b8df56: both pages describe the memory file for host and cloud drivers, with reviewed stamps.

<!-- fr:journal kind=finding scope=plan id=p4-r4-resolved created=2026-11-19T04:53:11+00:00 phase=4 state=fixed resolves=p4-r4 -->
### p4-r4-resolved · finding [fixed] · resolves p4-r4: A wave-finish snapshot is lost on an early drive exit or a failing Backlog write (phase 4)

209f66595: a new process sees a wave finished while no driver ran; the owed flag clears only after the Backlog write and snapshot succeed.

<!-- fr:journal kind=finding scope=plan id=p4-r5-resolved created=2026-11-19T04:53:11+00:00 phase=4 state=fixed resolves=p4-r5 -->
### p4-r5-resolved · finding [fixed] · resolves p4-r5: The purity test only greps for datetime.now (phase 4)

b8ff83fdd: an AST check refuses clock calls, time/subprocess/gitseam imports in batch_drive.py, and is shown to catch an impure source.

<!-- fr:journal kind=review scope=plan id=review-lenses created=2026-11-19T05:49:38+00:00 -->
### review-lenses · review · Lens review: docs-accuracy, security and tests over the whole feature

Three independent reviewers, one per lens, over cbf001bc..HEAD.
docs-accuracy: commands, files, the Backlog/Issues split, Batches, Origins, driver page writing, snapshot
rules and state carriage hold against the code; two findings. security: escaping before linkification,
https-only hrefs, entity lookbehind, URL-quoted wave/batch targets, no innerHTML or selector injection from
location.hash, fixed-name state carriage, no new subprocess or dependency all hold, probed with payloads;
the drive memory's measurement was the gap. tests: markup contracts pinned for tabs, folds, kind filter,
state filter and the kanban scripts; renamed tests not weakened; gaps in failure paths and two
script-source greps. Decision: the drive memory no longer carries the Architecture measurement (per-process
only), which closes l-security-r1, l-security-r2 and l-docs-accuracy-r1; R6/R7 amended to memory-based
baselining. Two out-of-scope findings filed as derio-net/super-fr#1556 and #1557.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-19T05:49:38+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · A no-clone driver was documented as rendering Architecture unmeasured but reused a remembered measurement

fr-wave-driver.md and docs/triage/README.md against _write_pages' reuse of the drive-pages.json measurement.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-19T05:49:38+00:00 state=open review_scope=in -->
### l-docs-accuracy-r2 · finding [open] (reviewer: in scope) · The herdr control page's reviewed note misdescribed this feature's change to triage_batch_cmd.py

The stamp said a docstring reword; later phases added the page writer and memory there.

<!-- fr:journal kind=finding scope=plan id=l-security-r1 created=2026-11-19T05:49:38+00:00 state=open review_scope=in -->
### l-security-r1 · finding [open] (reviewer: in scope) · drive-pages.json was loaded without type checks; a planted measurement reached architecture.html unescaped

Measure(**raw) accepted any JSON; _num returned str(n) unescaped; a non-int lines crashed every pass.

<!-- fr:journal kind=finding scope=plan id=l-security-r2 created=2026-11-19T05:49:38+00:00 state=open review_scope=in -->
### l-security-r2 · finding [open] (reviewer: in scope) · drive-pages.json joined the state ref unchecked by the privacy guard

A private scope repo's commit SHAs and line counts could reach a public state repo.

<!-- fr:journal kind=finding scope=plan id=l-security-r3 created=2026-11-19T05:49:38+00:00 state=open review_scope=out -->
### l-security-r3 · finding [open] (reviewer: out of scope) · The carried snapshots hold issue keys the privacy guard never reads

Predates this change; unjudged private issue keys can reach a public state repo.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-19T05:49:38+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · The driver's reuse of the Architecture measurement was unpinned

The test counted measure calls with a spy whose value rendered like no measurement.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-19T05:49:38+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · R7's baseline per drive was implemented per memory file with no test telling them apart

Only an unchanged-board second drive was tested; the spec was not amended.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-19T05:49:38+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · Once-per-distinct-cause page warnings were tested with one cause on one writer

No second cause, no reset after success, no other writer, no TriageError.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-19T05:49:38+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · Stage-filter and cutoff-choice tests grepped the script source

The href^= to href*= change for backlog.html#batch- links was unpinned.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5 created=2026-11-19T05:49:38+00:00 state=open review_scope=in -->
### l-tests-r5 · finding [open] (reviewer: in scope) · remove_legacy raising OSError had no test

triage backlog and triage batches turn it into a warning; nothing pinned that.

<!-- fr:journal kind=finding scope=plan id=l-tests-r6 created=2026-11-19T05:49:38+00:00 state=open review_scope=in -->
### l-tests-r6 · finding [open] (reviewer: in scope) · load_memory was tested only for bad JSON and a missing file

Schema mismatch, wrong-typed fields and the driver's first-pass fallback were untested.

<!-- fr:journal kind=finding scope=plan id=l-tests-r7 created=2026-11-19T05:49:38+00:00 state=open review_scope=out -->
### l-tests-r7 · finding [open] (reviewer: out of scope) · The Issues page filter script throws when its filter bar is absent

Predates this change (carried over from triage.html); no test renders Issues without backlog-by-tier.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-19T05:49:38+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: A no-clone driver was documented as rendering Architecture unmeasured but reused a remembered measurement

0ce1ead4f: the measurement is per-process only; a no-clone driver always renders dashes; both pages updated.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-19T05:49:38+00:00 state=fixed resolves=l-docs-accuracy-r2 -->
### l-docs-accuracy-r2-resolved · finding [fixed] · resolves l-docs-accuracy-r2: The herdr control page's reviewed note misdescribed this feature's change to triage_batch_cmd.py

5f3ad1e9a, 34c08e752: the stamp names the page writer and memory; session control unchanged.

<!-- fr:journal kind=finding scope=plan id=l-security-r1-resolved created=2026-11-19T05:49:38+00:00 state=fixed resolves=l-security-r1 -->
### l-security-r1-resolved · finding [fixed] · resolves l-security-r1: drive-pages.json was loaded without type checks; a planted measurement reached architecture.html unescaped

0ce1ead4f (+534508ef5): drive-pages.json holds only unfinished wave ids and the owed flag, load_memory validates strictly, _num int-coerces; a planted measurement never reaches the page.

<!-- fr:journal kind=finding scope=plan id=l-security-r2-resolved created=2026-11-19T05:49:38+00:00 state=fixed resolves=l-security-r2 -->
### l-security-r2-resolved · finding [fixed] · resolves l-security-r2: drive-pages.json joined the state ref unchecked by the privacy guard

0ce1ead4f: no SHA or line count is persisted, so nothing of the scope repo's code leaves the process.

<!-- fr:journal kind=finding scope=plan id=l-security-r3-resolved created=2026-11-19T05:49:38+00:00 state=open resolves=l-security-r3 out_of_scope=true -->
### l-security-r3-resolved · finding [out-of-scope] · resolves l-security-r3: The carried snapshots hold issue keys the privacy guard never reads

Predates this change, which neither adds nor touches snapshot carriage; filed as derio-net/super-fr#1556.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-19T05:49:38+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: The driver's reuse of the Architecture measurement was unpinned

0ce1ead4f: a spy returning real numbers shows every pass in one process rendering them with one measure call; no clone renders dashes.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-19T05:49:38+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: R7's baseline per drive was implemented per memory file with no test telling them apart

a1ab842fc: spec R6/R7 amended to memory-based baselining; a second drive over a changed board stores none unless a wave finished.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-19T05:49:38+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: Once-per-distinct-cause page warnings were tested with one cause on one writer

df98ade1f: second cause, reset after a good write, per-page failure sets for History/Origins/Architecture, and a broken manifest warned and never raised.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-19T05:49:38+00:00 state=fixed resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [fixed] · resolves l-tests-r4: Stage-filter and cutoff-choice tests grepped the script source

67dff9951: an attribute-selector checker runs the stage script's selector against the rendered batch links (a ^= revert fails); the cutoff id and scope are checked against the markup.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5-resolved created=2026-11-19T05:49:38+00:00 state=fixed resolves=l-tests-r5 -->
### l-tests-r5-resolved · finding [fixed] · resolves l-tests-r5: remove_legacy raising OSError had no test

4f98f2aa5: an OSError from remove_legacy is a warning; both commands exit 0 with the page written.

<!-- fr:journal kind=finding scope=plan id=l-tests-r6-resolved created=2026-11-19T05:49:38+00:00 state=fixed resolves=l-tests-r6 -->
### l-tests-r6-resolved · finding [fixed] · resolves l-tests-r6: load_memory was tested only for bad JSON and a missing file

0ce1ead4f: each wrong-shaped memory loads as no memory, and the driver then takes the first-pass decisions.

<!-- fr:journal kind=finding scope=plan id=l-tests-r7-resolved created=2026-11-19T05:49:38+00:00 state=open resolves=l-tests-r7 out_of_scope=true -->
### l-tests-r7-resolved · finding [out-of-scope] · resolves l-tests-r7: The Issues page filter script throws when its filter bar is absent

Predates this change (the old triage.html had it; the split carried it over); filed as derio-net/super-fr#1557.

<!-- fr:journal kind=finding scope=plan id=l-security-r3-resolved-2 created=2026-11-19T06:36:28+00:00 state=open resolves=l-security-r3 tracked_by=derio-net/super-fr#1556 -->
### l-security-r3-resolved-2 · finding [deferred → derio-net/super-fr#1556] · resolves l-security-r3: The carried snapshots hold issue keys the privacy guard never reads

Predates this change; filed as derio-net/super-fr#1556.
