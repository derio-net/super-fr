# Journal: 2026-10-05-triage-pages-goal

<!-- fr:journal kind=discovery scope=plan id=p1-preselected-wave-signature created=2026-10-05T21:44:33+00:00 phase=1 -->
### p1-preselected-wave-signature · discovery · preselected_wave keeps facts as its first argument (phase 1)

The plan wrote preselected_wave(judgements, among=...) but the real signature is (facts, judgements); stage derivation needs facts. Added among as a keyword only. Wave keys are strings.

<!-- fr:journal kind=discovery scope=plan id=p1-board-https-href-test created=2026-10-05T21:44:33+00:00 phase=1 -->
### p1-board-https-href-test · discovery · page chrome adds relative hrefs to the board (phase 1)

test_a_non_https_url_produces_no_href asserted every anchor on the board is https; the nav bar links triage.html/origins.html/architecture.html/history.html. The test now allows exactly the PAGES file names (constants, never untrusted).

<!-- fr:journal kind=discovery scope=plan id=p1-architecture-drops-kind-counts created=2026-10-05T21:44:33+00:00 phase=1 -->
### p1-architecture-drops-kind-counts · discovery · architecture summary loses open/defect counts (phase 1)

Spec background lists kind counts as a fact on the board and the architecture summary. R6's summary is lines then/now plus Where it hurts, so the open-issues and defects figures (and issues filed, batches merged) left the architecture page: one home per fact. History also got a small MOVED map {waves: board} so an old manifest naming it is noted, not reported missing; architecture render_architecture lost its snapshots parameter since the timeline moved.

<!-- fr:journal kind=discovery scope=plan id=p1-files-outside-list created=2026-10-05T21:44:33+00:00 phase=1 -->
### p1-files-outside-list · discovery · touched beyond the obvious files (phase 1)

components.py gained BASE_CSS (shared prelude for architecture and history); origins.py lost the origin_counts/filings_chart re-exports (dead); triage_cmd.py registers the history command; tests/unit/test_triage_render.py and test_triage_board_views.py hold the board and finished-wave tests.

<!-- fr:journal kind=finding scope=plan id=p1-visual-matcher-uv-with created=2026-10-05T21:44:33+00:00 phase=1 state=open review_scope=out -->
### p1-visual-matcher-uv-with · finding [open] (reviewer: out of scope) · capture-script witness misreads uv run --with (phase 1)

fr's capture-script witness misreads `uv run --with <pkg> python <script>` (value-taking flag read as the program), so a correctly run capture is reported unwitnessed

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-10-05T21:44:33+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

constant + smoke test only

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-05T21:44:33+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

nothing to clean beyond the views re-export

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-10-05T21:44:33+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

no refactor needed beyond ordering

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t8 created=2026-10-05T21:44:33+00:00 phase=1 -->
### no-refactor-p1-t8 · discovery · no-refactor-because P1.T8 (phase 1)

board change is a filter plus a header call; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-10-05T21:44:33+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

the board/origins/architecture CSS preludes differ in table width, code styling and tab rules, so only the architecture/history shared prelude moved (BASE_CSS); folding origins and board in would change their rendering

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-05T21:51:53+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · history.py imports private render._wave_table (and FONTS); make it a public name (phase 1)

Raised by the phase 1 reviewer (separate dispatched context).

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-05T21:51:53+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · fragments._fragment slug id can collide for differently-named collapsed fragment files (duplicate id) (phase 1)

Raised by the phase 1 reviewer (separate dispatched context).

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-05T21:51:53+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · validate_fragment is a denylist (no formaction etc.) and rejects optional-end-tag HTML; harmless today but brittle (phase 1)

Raised by the phase 1 reviewer (separate dispatched context).

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-05T21:51:53+00:00 phase=1 state=open review_scope=out -->
### p1-r4 · finding [open] (reviewer: out of scope) · cancelled-only waves count as finished and silently vanish from the board (spec'd predicate, undocumented consequence) (phase 1)

Raised by the phase 1 reviewer (separate dispatched context).

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-10-05T21:51:53+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · shots.py lacks a board no-finished-waves shot, nav clicks from every page and keyboard tab check (phase 1)

Raised by the phase 1 reviewer (separate dispatched context).

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-10-05T21:51:53+00:00 phase=1 state=open review_scope=out -->
### p1-r6 · finding [open] (reviewer: out of scope) · board wave table is cramped at 390px (columns wrap letter by letter); predates this phase, board relayout is R2-R5 (phase 1)

Raised by the phase 1 reviewer (separate dispatched context).

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-10-05T21:51:53+00:00 phase=1 -->
### p1-review-1 · review · phase 1 review: 6 findings (4 in, 2 out) (phase 1)

Dispatched reviewer read the diff 3caf6417a..71ba41a95 against spec R1, R6-R9 and plan phase 1, ran the triage tests (1042 passed), re-ran the capture script and opened all 19 screenshots itself. Findings p1-r1..p1-r6. After fixes (b30c470fe + capture script extension) it verified r1, r2, r5 and judged the phase ready.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-05T21:51:53+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: history.py imports private render._wave_table (and FONTS); make it a public name (phase 1)

wave_table made public; history.py imports it by that name (b30c470fe).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-05T21:51:53+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: fragments._fragment slug id can collide for differently-named collapsed fragment files (duplicate id) (phase 1)

splice numbers slug-alike collapsed fragment ids; test test_collapsed_fragments_whose_names_slug_alike_get_distinct_ids (b30c470fe).

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-05T21:51:53+00:00 phase=1 state=refuted resolves=p1-r3 -->
### p1-r3-resolved · finding [refuted] · resolves p1-r3: validate_fragment is a denylist (no formaction etc.) and rejects optional-end-tag HTML; harmless today but brittle (phase 1)

The validator moved verbatim from architecture.py on main (same _URL_ATTRS denylist, same end-tag rule); spec R9 deliberately keeps today's validate_fragment refusals, and the forbidden <form>/<iframe> close the attributes cited. Changing the refusal set is a spec change, not a defect of this move. The reviewer withdrew it.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-05T21:51:53+00:00 phase=1 state=open resolves=p1-r4 out_of_scope=true -->
### p1-r4-resolved · finding [out-of-scope] · resolves p1-r4: cancelled-only waves count as finished and silently vanish from the board (spec'd predicate, undocumented consequence) (phase 1)

Follows the spec'd R8 predicate (cancelled is terminal). Not caused by an implementation error; documenting it falls to the skills text in phase 5.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-10-05T21:51:53+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: shots.py lacks a board no-finished-waves shot, nav clicks from every page and keyboard tab check (phase 1)

Capture script now covers the board's every-wave-finished state, nav from every page to every other, and keyboard tab switching; all assertions pass and the reviewer opened every fresh shot.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-10-05T21:51:53+00:00 phase=1 state=open resolves=p1-r6 out_of_scope=true -->
### p1-r6-resolved · finding [out-of-scope] · resolves p1-r6: board wave table is cramped at 390px (columns wrap letter by letter); predates this phase, board relayout is R2-R5 (phase 1)

The wave table markup predates this change; phase 2 (R2-R5) owns the board layout and is briefed to keep its wave table usable at phone width.

<!-- fr:journal kind=finding scope=plan id=p1-visual-matcher-uv-with-resolved created=2026-10-05T21:51:53+00:00 phase=1 state=open resolves=p1-visual-matcher-uv-with out_of_scope=true -->
### p1-visual-matcher-uv-with-resolved · finding [out-of-scope] · resolves p1-visual-matcher-uv-with: capture-script witness misreads uv run --with (phase 1)

A defect in fr's capture-script witness (fr/run/telemetry.py _executes), not caused by this change; worked around with a shebang so the script is its own command word.

<!-- fr:journal kind=discovery scope=plan id=p2-files-outside-list created=2026-10-05T22:13:18+00:00 phase=2 -->
### p2-files-outside-list · discovery · touched beyond the obvious files (phase 2)

components.py gained GRID_CSS (shared by board and history so the wave tables scroll sideways at 390px instead of wrapping by the letter: min-width 720px inside .tablewrap, nowrap headers); history.py uses it; triage_cmd.py reads <state>/board/manifest.yaml (BOARD_DIR); the acceptance matrix and its reports moved (two rows to ci, board-decision-views re-pointed at the renamed ordering test).

<!-- fr:journal kind=discovery scope=plan id=p2-section-shapes created=2026-10-05T22:13:18+00:00 phase=2 -->
### p2-section-shapes · discovery · fold bodies keep the old wrapper tags, ids are new (phase 2)

PRs, Batches and Patterns keep a <section class=prs|batches|patterns> inside their fold so the existing tests still address them. Fold ids: backlog-by-tier, backlog-tier-<n|unranked>, ranked-features, parked, patterns, prs, batches. Empty features, parked, patterns and batches render no fold (as before); Backlog and PRs always render. The board ordering test replaced lives in test_triage_board_views.py, not test_triage_render.py as the plan says.

<!-- fr:journal kind=discovery scope=plan id=p2-link-opens-filtered-card created=2026-10-05T22:13:18+00:00 phase=2 -->
### p2-link-opens-filtered-card · discovery · a link to a filtered-off card re-checks its stage (phase 2)

FOLD_SCRIPT turns the target card's stage checkbox back on before opening the card and its ancestors, so a link never lands on a hidden card. A same-hash re-click is handled by a click listener, since hashchange does not fire.

<!-- fr:journal kind=discovery scope=plan id=p2-unreachable-no-judgement-tier-dash created=2026-10-05T22:13:18+00:00 phase=2 -->
### p2-unreachable-no-judgement-tier-dash · discovery · the Tier dash cannot arise from a valid board (phase 2)

Judgements validation requires every batch member to be judged, so the em-dash tier is reachable only through wave_table on a hand-built Batch; the test builds it that way.

<!-- fr:journal kind=finding scope=plan id=p2-suite-log-background-unwitnessed created=2026-10-05T22:13:18+00:00 phase=2 state=open review_scope=out -->
### p2-suite-log-background-unwitnessed · finding [open] (reviewer: out of scope) · fr cannot witness a suite log written by a run_in_background command, which the brief's own long_commands rule prescribes (phase 2)

implement-phase refuses evidence.tests when the full suite ran via a background Bash call (the call returns at once, so the log's writes fall outside the command's window). The dispatch brief's long_commands rule tells executors to do exactly that for the suite. Not caused by this change; the deliver step re-runs the suite on the final tree.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-10-05T22:13:18+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

cards, filter and script are one small addition on the P2.T2 helpers; nothing to clean
