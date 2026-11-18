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
