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

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-05T22:19:09+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · Batch stage filter with every box off shows no "no batches match" message (phase 2)

Raised by the phase 2 reviewer (separate dispatched context).

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-05T22:19:09+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · Wave table's "Why" column is clipped at 390px with no scroll affordance (phase 2)

Raised by the phase 2 reviewer (separate dispatched context).

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-10-05T22:19:09+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · Planned merge-order list is not tied to the stage filter, so it can list batches the cards hide (phase 2)

Raised by the phase 2 reviewer (separate dispatched context).

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-10-05T22:19:09+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · FOLD_SCRIPT calls reveal twice (click handler and hashchange); harmless but redundant (phase 2)

Raised by the phase 2 reviewer (separate dispatched context).

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-10-05T22:19:09+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · With every stage off the "Planned merge order" intro paragraph stays above an empty list (phase 2)

Raised by the phase 2 reviewer (separate dispatched context).

<!-- fr:journal kind=review scope=plan id=p2-review-1 created=2026-10-05T22:19:09+00:00 phase=2 -->
### p2-review-1 · review · phase 2 review: 5 findings (all in, all minor) (phase 2)

Dispatched reviewer read 18c6cc849..6666d74e2 against R2-R5 and plan phase 2, ran the triage tests (1054 passed), re-ran shots-p2.py as a command word and opened all 21 screenshots; after fixes it re-ran the capture, opened all 21 again, verified p2-r1..r4 and raised p2-r5, fixed in 3468e4a41.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-05T22:19:09+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: Batch stage filter with every box off shows no "no batches match" message (phase 2)

filter-empty message shown by apply() when no card is visible (0f9b51a88); test test_an_empty_filter_says_so_and_the_merge_order_follows_it; reviewer saw it in p2-batch-filter-every-stage-off.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-05T22:19:09+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: Wave table's "Why" column is clipped at 390px with no scroll affordance (phase 2)

scroll shadows on .tablewrap (0f9b51a88, 9d979a21a); test test_wide_tables_show_that_they_scroll; reviewer saw the edge shadow.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-10-05T22:19:09+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: Planned merge-order list is not tied to the stage filter, so it can list batches the cards hide (phase 2)

merge-order rows hide with their batch's card (0f9b51a88); reviewer verified.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-10-05T22:19:09+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: FOLD_SCRIPT calls reveal twice (click handler and hashchange); harmless but redundant (phase 2)

click path only for a link to the hash already shown (0f9b51a88); test test_a_link_reveals_once_and_only_the_same_hash_needs_the_click_path.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-10-05T22:19:09+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: With every stage off the "Planned merge order" intro paragraph stays above an empty list (phase 2)

intro and list wrapped in div.merge-plan hidden when no step is visible (3468e4a41); test test_the_merge_plan_hides_whole_when_no_step_is_shown.

<!-- fr:journal kind=finding scope=plan id=p2-suite-log-background-unwitnessed-resolved created=2026-10-05T22:19:09+00:00 phase=2 state=open resolves=p2-suite-log-background-unwitnessed out_of_scope=true -->
### p2-suite-log-background-unwitnessed-resolved · finding [out-of-scope] · resolves p2-suite-log-background-unwitnessed: fr cannot witness a suite log written by a run_in_background command, which the brief's own long_commands rule prescribes (phase 2)

A conflict between fr's suite-log witness and the brief's long_commands rule, not caused by this change; deliver re-runs the suite on the final tree.

<!-- fr:journal kind=discovery scope=plan id=p3-files-outside-list created=2026-10-05T22:30:54+00:00 phase=3 -->
### p3-files-outside-list · discovery · touched beyond the obvious files (phase 3)

commands/triage_cmd.py (collect_into adds duplicate_of targets to the judged keys, since the viewed-keys logic lives there and not in collect.py; check prints the two new sets), commands/triage_origins_cmd.py (third set), views.py (max_severity, NextRow.severity), plus the acceptance matrix and its reports (two rows to ci).

<!-- fr:journal kind=discovery scope=plan id=p3-origins-link-and-no-refactor created=2026-10-05T22:30:54+00:00 phase=3 -->
### p3-origins-link-and-no-refactor · discovery · origins issue link logic did not duplicate, so P3.T1.S3 changed nothing (phase 3)

The conclusion links batches (triage.html#batch-<id>), not issues, so the table's _original_link shares no URL logic with it. Row ids are origin-<key> with a literal #; the href percent-encodes it (origin-widgets%235), as batch refs do. The id attribute goes after data-key, since an existing test pins the attribute order.

<!-- fr:journal kind=discovery scope=plan id=p3-duplicate-checks-shape created=2026-10-05T22:30:54+00:00 phase=3 -->
### p3-duplicate-checks-shape · discovery · check sets list issue keys; duplicate_outside / duplicate_unknown name the duplicate, not the target (phase 3)

origins check's duplicate_outside and triage check's duplicate_unknown are lists of the DUPLICATE issue's key whose duplicate_of names an issue the facts do not hold. no_severity lists open judged issues with no severity (duplicates included, literal to the spec). Only duplicates with open state leave the tier sections; kind: parked issues stay in theirs, as before.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-10-05T22:30:54+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

severity pill and the Parked duplicate note are small additions on existing helpers (_row, _next_section, _parked); nothing to clean

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-10-05T22:34:47+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · Origin.duplicate_of is not validated against the key grammar or for self-reference, unlike Judgement.duplicate_of (phase 3)

Raised by the phase 3 reviewer (separate dispatched context).

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-10-05T22:34:47+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · duplicate_of cycles (A<->B) and chains (A->B->C) are accepted silently; both members vanish from tiers or link to a non-root original (phase 3)

Raised by the phase 3 reviewer (separate dispatched context).

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-10-05T22:34:47+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · no_severity includes open duplicates and parked issues, which never display a severity pill (phase 3)

Raised by the phase 3 reviewer (separate dispatched context).

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-10-05T22:34:47+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · Origin fixed_by/introduced_in are unvalidated free text (falls back to escaped plain text, same as pr:) (phase 3)

Raised by the phase 3 reviewer (separate dispatched context).

<!-- fr:journal kind=review scope=plan id=p3-review-1 created=2026-10-05T22:34:47+00:00 phase=3 -->
### p3-review-1 · review · phase 3 review: 4 findings (all in, minor) (phase 3)

Dispatched reviewer read 1bc0f5712..0fd540cfd against R10, R11, spec §E/§G/§B and plan phase 3, checked compatibility, collect cost and escaping, ran the triage tests (1080 passed). p3-r1 and p3-r2 fixed in ecf259861 (1086 passed); p3-r3 and p3-r4 refuted with reasoning.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-10-05T22:34:47+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: Origin.duplicate_of is not validated against the key grammar or for self-reference, unlike Judgement.duplicate_of (phase 3)

Origin.duplicate_of is held to KEY_RE and Origins refuses a self-reference at load, naming the key (ecf259861); tests test_an_origins_duplicate_of_off_the_key_grammar_is_refused, test_an_origins_entry_that_duplicates_itself_is_refused.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-10-05T22:34:47+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: duplicate_of cycles (A<->B) and chains (A->B->C) are accepted silently; both members vanish from tiers or link to a non-root original (phase 3)

fr triage check gains the duplicate_chained set (text and --json): every judgement whose target is itself a duplicate (ecf259861); test test_a_duplicate_of_a_duplicate_is_duplicate_chained.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-10-05T22:34:47+00:00 phase=3 state=refuted resolves=p3-r3 -->
### p3-r3-resolved · finding [refuted] · resolves p3-r3: no_severity includes open duplicates and parked issues, which never display a severity pill (phase 3)

The operator chose 'severity on every open issue' in the question round (q4), and R11 states the set as open, judged issues without a severity. A parked or duplicate issue can be unparked or turn out distinct; its severity is still owed and still shown in fr triage check and the JSON. Excluding them would contradict the recorded decision.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-10-05T22:34:47+00:00 phase=3 state=refuted resolves=p3-r4 -->
### p3-r4-resolved · finding [refuted] · resolves p3-r4: Origin fixed_by/introduced_in are unvalidated free text (falls back to escaped plain text, same as pr:) (phase 3)

Deliberately consistent with the existing pr: field, which is free text rendered through the same _pr_link (link when it parses, escaped text otherwise). Validating two of three PR-ref fields would make the schema inconsistent; nothing renders unsafely.

<!-- fr:journal kind=finding scope=plan id=p4-sec-symlink-follow created=2026-10-05T23:19:04+00:00 phase=4 state=open review_scope=in -->
### p4-sec-symlink-follow · finding [open] (reviewer: in scope) · state_sync followed symlinks on export and import (phase 4)

Security review of a82a6a0c6: base.rglob plus shutil.copy2 followed symlinks, so a symlink planted in the state dir (authored-src/x -> ~/.ssh/id_rsa, or a symlinked page dir) copied its target into the repo, which the R13 driver then commits and pushes; import from a cloned repo could copy an arbitrary local file into the cache; and a symlinked destination was written through.

<!-- fr:journal kind=finding scope=plan id=p4-sec-root-symlink-traversal created=2026-10-05T23:19:04+00:00 phase=4 state=open review_scope=in -->
### p4-sec-root-symlink-traversal · finding [open] (reviewer: in scope) · state sync trusted the repo-side root and the parts joined to build it (phase 4)

Follow-up review of ed706bdfc: the symlink checks covered entries under a root but not the root, so a cloned repo committing docs/triage or docs/triage/<scope> as a symlink made import read wherever it points and the driver export write outside its worktree; and <dir>/<scope> and <worktree>/<path>/<scope> trusted scope and every component of path (a symlinked component escapes without `..` or a leading `/`).

<!-- fr:journal kind=discovery scope=plan id=p4-files-outside-list created=2026-10-05T23:19:04+00:00 phase=4 -->
### p4-files-outside-list · discovery · touched beyond the phase's files list (phase 4)

RealGhClient.pr_create lives in packages/fr/src/fr/real_ghclient.py (the gh adapter is not in ghclient.py, which holds only the Protocol and UnsupportedBatchOps); its tests and the glab/tea refusal parametrisation are in tests/unit/test_forge_adapter_batch_ops.py, the existing home of the batch-op adapter tests. Six existing triage tests that pinned "the writer writes schema 3" or "schema 4 is refused" now pin 4 and 5.

<!-- fr:journal kind=discovery scope=plan id=p4-export-decisions created=2026-10-05T23:19:04+00:00 phase=4 -->
### p4-export-decisions · discovery · export choices the spec left open (phase 4)

Action.batch carries the repo for export actions; action_line prints `<kind> wave <N> <repo>` for any action with a wave (export warns included). Export warns name no head, so they repeat every pass, as the spec wants. A recorded export whose live PR reads MERGED (merged by hand) needs nothing and is not counted; a recorded PR not read this pass counts as closing. The group/org scope warn is not counted blocked (it would stop every group drive). A contained() refusal in _export prints as a warn, counts blocked instead of closing, and is not `acted`, so --once exits 3 and the loop stops waiting on the operator. A leftover export worktree from a dead pass is force-removed before the next export (it is driver-owned scratch; add_worktree would otherwise refuse it forever). The P4.T4.S3 command tests were written right after the implementation draft rather than strictly before; one of them failed red (the refusal counted as acted) and drove a fix.

<!-- fr:journal kind=finding scope=plan id=p4-export-backlog-of-finished-waves created=2026-10-05T23:19:04+00:00 phase=4 state=open review_scope=in -->
### p4-export-backlog-of-finished-waves · finding [open] (reviewer: in scope) · opting in on a repo with many already-finished waves opens one export PR per wave at once (phase 4)

Per the spec, step 3b acts on every finished wave with no merged export. A repo that sets export: after several waves finished (this repo, in phase 5) gets one export PR per old wave in the first pass, all carrying near-identical state. Exporting only the highest unexported finished wave, or recording older ones as superseded, would avoid that; it is a spec decision, not made here.

<!-- fr:journal kind=finding scope=plan id=p4-sec-unpinned-merge created=2026-10-05T23:19:04+00:00 phase=4 state=open review_scope=in -->
### p4-sec-unpinned-merge · finding [open] (reviewer: in scope) · the driver merged an export PR at its live head, so anyone's later commit on the branch auto-merged (phase 4)

_export_merge called pr_merge with the live head. Author trust covers the PR opener, not later commits, so anyone with push access could add a commit to chore/triage-state-wave-<N> and the driver would merge it into the default branch unreviewed. Spec amended in a3ef99637 (R13, §G, §I).

<!-- fr:journal kind=finding scope=plan id=p4-sec-file-list created=2026-10-05T23:19:04+00:00 phase=4 state=open review_scope=in -->
### p4-sec-file-list · finding [open] (reviewer: in scope) · the export file allowlist trusted the forge's files field (phase 4)

Security review of 648982163: gh's `files` names only a rename's new path, so a PR renaming .github/workflows/x.yml into docs/triage/... passed; and it stops at 100 entries, so a stray path past entry 100 passed. Spec amended in 435278157.

<!-- fr:journal kind=finding scope=plan id=p4-sec-symlink-follow-resolved created=2026-10-05T23:19:04+00:00 phase=4 state=fixed resolves=p4-sec-symlink-follow -->
### p4-sec-symlink-follow-resolved · finding [fixed] · resolves p4-sec-symlink-follow: state_sync followed symlinks on export and import (phase 4)

state_sync walks with os.scandir and never follows a symlink at any depth (durable files and dirs themselves included); a symlinked target or parent under the destination root is never written through; copy2 uses follow_symlinks=False. Each is skipped and reported in SyncReport.skipped with its reason (Skipped(path, reason)); tests in tests/unit/test_triage_state_sync.py cover all four cases.

<!-- fr:journal kind=finding scope=plan id=p4-sec-root-symlink-traversal-resolved created=2026-10-05T23:19:04+00:00 phase=4 state=fixed resolves=p4-sec-root-symlink-traversal -->
### p4-sec-root-symlink-traversal-resolved · finding [fixed] · resolves p4-sec-root-symlink-traversal: state sync trusted the repo-side root and the parts joined to build it (phase 4)

state_sync.contained(base, rel) refuses an absolute rel, an empty/./.. part, any existing symlinked component under base (the last included) and a resolve() outside base.resolve(); the base itself is trusted (macOS /var). check_scope_name refuses a scope that is not one plain part. export_state/import_state take (base, rel) and build the root through contained; the CLI passes (--to|--from, scope); the driver passes (worktree, <path>/<scope>), and a refusal there is a warn for that wave with nothing committed or pushed, counted blocked. _symlinked_dest still re-checks each target. Tests: test_triage_state_sync.py (contained, scope name, symlinked scope dir on import, symlinked root on export, base under a symlinked /var-style parent) and test_triage_batch_drive_cmd.py::test_a_symlinked_export_path_in_the_repo_is_refused_as_a_warn_with_nothing_written.

<!-- fr:journal kind=finding scope=plan id=p4-sec-unpinned-merge-resolved created=2026-10-05T23:19:04+00:00 phase=4 state=fixed resolves=p4-sec-unpinned-merge -->
### p4-sec-unpinned-merge-resolved · finding [fixed] · resolves p4-sec-unpinned-merge: the driver merged an export PR at its live head, so anyone's later commit on the branch auto-merged (phase 4)

Export gains head: the SHA commit_paths returned (recorded by _export) or the adopted PR's live head (export-adopt). Step 3b merges only when the live head equals the recorded head and every changed file (the LivePr.files the head's PR list read) lies under <path>/<scope>/; a differing or missing head, a file outside, or an unknown file list is a warn counted blocked, and export-adopt needs the same file rule. export-merge carries the recorded head and _export_merge passes it to pr_merge. Tests: test_triage_batch_drive.py (pinned merge, foreign commit, no recorded head, files outside/sibling prefix/unknown for adopt and merge) and test_triage_batch_drive_cmd.py (foreign commit leaves no pr_merge call, a file outside blocks merge and adoption, the happy path merges at the recorded SHA).

<!-- fr:journal kind=finding scope=plan id=p4-sec-file-list-resolved created=2026-10-05T23:19:04+00:00 phase=4 state=fixed resolves=p4-sec-file-list -->
### p4-sec-file-list-resolved · finding [fixed] · resolves p4-sec-file-list: the export file allowlist trusted the forge's files field (phase 4)

The driver's snapshot builder (_Driver._export_files) fetches, then reads the export PR's files with Checkout.changed_paths(origin/<default>, head) (git diff --name-only --no-renames ref...head: a rename is a delete plus an add, never truncated), for the recorded head on export-merge and the live head on export-adopt, and passes them to drive_pass as LivePr.files; the forge's files field no longer reaches the decision. An unreadable head gives no files, which _outside refuses (warn, blocked). Tests in test_triage_batch_drive_cmd.py against real temp repos: a rename from outside into the dir (both paths in changed_paths), 121 changed files with one outside sorting last, an unreadable head, and the happy path merging at the recorded SHA.

<!-- fr:journal kind=finding scope=plan id=p4-export-backlog-of-finished-waves-resolved created=2026-10-05T23:19:04+00:00 phase=4 state=fixed resolves=p4-export-backlog-of-finished-waves -->
### p4-export-backlog-of-finished-waves-resolved · finding [fixed] · resolves p4-export-backlog-of-finished-waves: opting in on a repo with many already-finished waves opens one export PR per wave at once (phase 4)

Spec amended in 1e267a0ee. batch_drive.export_target picks, per repo, the newest unmerged export PR and the waves recorded with it, or else every finished wave with no entry; step 3b decides once per repo on it, so one export (or adopt) covers all unexported finished waves on chore/triage-state-wave-<highest> (Action.covers), Summary counts one owed export per PR, and a wave finishing while a PR is open waits. The driver records one entry per covered wave with the same pr/head (pr None when unchanged), and a merge marks every entry carrying that PR merged. Pure tests (written red first) in test_triage_batch_drive.py; command tests in test_triage_batch_drive_cmd.py (three waves, one PR, three entries, merge marks all; a wave finishing mid-PR waits, then exports alone), written right after the implementation.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-10-05T23:19:04+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

state_sync is one copy loop shared by both directions; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t4 created=2026-10-05T23:19:04+00:00 phase=4 -->
### no-refactor-p4-t4 · discovery · no-refactor-because P4.T4 (phase 4)

execution reuses _archive's merge path and the gitseam/ghclient seams; the export steps are one method each, nothing to clean
