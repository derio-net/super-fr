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

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-10-06T00:00:58+00:00 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · export PR merged outside the driver (or crash after pr_merge) is never marked merged; export_target pins to it forever and later waves never export, silently (phase 4)

Raised by the phase 4 reviewer (separate dispatched Opus context).

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-10-06T00:00:58+00:00 phase=4 state=open review_scope=in -->
### p4-r2 · finding [open] (reviewer: in scope) · ExportConfig accepts trailing-slash/./empty-part paths that contained() refuses every pass; _export_config rstrips '/' but _export does not (phase 4)

Raised by the phase 4 reviewer (separate dispatched Opus context).

<!-- fr:journal kind=finding scope=plan id=p4-r3 created=2026-10-06T00:00:58+00:00 phase=4 state=open review_scope=in -->
### p4-r3 · finding [open] (reviewer: in scope) · crash between pr_create and record, plus a wave finishing before the next pass, opens a second export PR (adoption looks only at the highest owed wave's branch) (phase 4)

Raised by the phase 4 reviewer (separate dispatched Opus context).

<!-- fr:journal kind=finding scope=plan id=p4-r4 created=2026-10-06T00:00:58+00:00 phase=4 state=open review_scope=in -->
### p4-r4 · finding [open] (reviewer: in scope) · pr_create ValueError (no PR URL) is not in FORGE_ERRORS: driver tracebacks instead of exiting 1 (phase 4)

Raised by the phase 4 reviewer (separate dispatched Opus context).

<!-- fr:journal kind=finding scope=plan id=p4-r5 created=2026-10-06T00:00:58+00:00 phase=4 state=open review_scope=in -->
### p4-r5 · finding [open] (reviewer: in scope) · import's mtime "newer" check is defeated by git checkout mtimes; docstring overclaims "never silently overwritten" (phase 4)

Raised by the phase 4 reviewer (separate dispatched Opus context).

<!-- fr:journal kind=finding scope=plan id=p4-r6 created=2026-10-06T00:00:58+00:00 phase=4 state=open review_scope=in -->
### p4-r6 · finding [open] (reviewer: in scope) · a recorded export PR closed unmerged blocks that repo's exports forever with no documented recovery (phase 4)

Raised by the phase 4 reviewer (separate dispatched Opus context).

<!-- fr:journal kind=finding scope=plan id=p4-r7 created=2026-10-06T00:00:58+00:00 phase=4 state=open review_scope=in -->
### p4-r7 · finding [open] (reviewer: in scope) · any fork PR named chore/triage-state-wave-N blocks the export (untrusted row); cross-repo PRs could be ignored safely (phase 4)

Raised by the phase 4 reviewer (separate dispatched Opus context).

<!-- fr:journal kind=finding scope=plan id=p4-r8 created=2026-10-06T00:00:58+00:00 phase=4 state=open review_scope=in -->
### p4-r8 · finding [open] (reviewer: in scope) · adoption after a crash pins and auto-merges whatever trusted-PR head is live, with no proof the driver pushed it (phase 4)

Raised by the phase 4 reviewer (separate dispatched Opus context).

<!-- fr:journal kind=finding scope=plan id=p4-r9 created=2026-10-06T00:00:58+00:00 phase=4 state=open review_scope=in -->
### p4-r9 · finding [open] (reviewer: in scope) · commit_paths uses git add without -f, so gitignored durable files are silently not exported (phase 4)

Raised by the phase 4 reviewer (separate dispatched Opus context).

<!-- fr:journal kind=finding scope=plan id=p4-r10 created=2026-10-06T00:00:58+00:00 phase=4 state=open review_scope=in -->
### p4-r10 · finding [open] (reviewer: in scope) · untested leftover-worktree path; non-worktree export dir fails every pass; OSError in _sync escapes as a traceback (phase 4)

Raised by the phase 4 reviewer (separate dispatched Opus context).

<!-- fr:journal kind=finding scope=plan id=p4-r11 created=2026-10-06T00:00:58+00:00 phase=4 state=open review_scope=out -->
### p4-r11 · finding [open] (reviewer: out of scope) · local check-to-write race between the symlink check and copy2 in state_sync (local attacker only) (phase 4)

Raised by the phase 4 reviewer (separate dispatched Opus context).

<!-- fr:journal kind=finding scope=plan id=p4-r12 created=2026-10-06T00:00:58+00:00 phase=4 state=open review_scope=in -->
### p4-r12 · finding [open] (reviewer: in scope) · adoption's single-commit proof is structural, not authorship: a force-pushed single commit inside the export dir is still adopted and auto-merged; compare the orphan's tree to a local re-export (phase 4)

Raised by the phase 4 reviewer (separate dispatched Opus context).

<!-- fr:journal kind=finding scope=plan id=p4-r13 created=2026-10-06T00:00:58+00:00 phase=4 state=open review_scope=in -->
### p4-r13 · finding [open] (reviewer: in scope) · a recorded-closed export PR that is reopened is never an orphan; the re-export force-pushes its branch and gh pr create fails (exit 1) every pass (phase 4)

Raised by the phase 4 reviewer (separate dispatched Opus context).

<!-- fr:journal kind=finding scope=plan id=p4-r14 created=2026-10-06T00:00:58+00:00 phase=4 state=open review_scope=in -->
### p4-r14 · finding [open] (reviewer: in scope) · names of gitignored durable files are published in the public export PR body; keep names local, put a count in the PR (phase 4)

Raised by the phase 4 reviewer (separate dispatched Opus context).

<!-- fr:journal kind=finding scope=plan id=p4-r15 created=2026-10-06T00:00:58+00:00 phase=4 state=open review_scope=in -->
### p4-r15 · finding [open] (reviewer: in scope) · export PR base branch is never checked at reuse or merge: a retargeted/orphan PR auto-merges default-branch history plus the export into an arbitrary branch (phase 4)

Raised by the phase 4 reviewer (separate dispatched Opus context).

<!-- fr:journal kind=finding scope=plan id=p4-r16 created=2026-10-06T00:00:58+00:00 phase=4 state=open review_scope=in -->
### p4-r16 · finding [open] (reviewer: in scope) · when several orphan export PRs are open only the highest is reused; the others stay open with no warn (phase 4)

Raised by the phase 4 reviewer (separate dispatched Opus context).

<!-- fr:journal kind=finding scope=plan id=p4-archive-pr-base-unchecked created=2026-10-06T00:00:58+00:00 phase=4 state=open review_scope=out -->
### p4-archive-pr-base-unchecked · finding [open] (reviewer: out of scope) · the wave driver's archive-PR merge path never checks the PR's base branch either (phase 4)

Noted by the phase 4 reviewer while verifying p4-r15. The archive merge (_archive, pre-existing) merges a trusted archive PR without comparing baseRefName to the default branch. Not caused by this change; the export path got the fix (p4-r15).

<!-- fr:journal kind=review scope=plan id=p4-review-1 created=2026-10-06T00:00:58+00:00 phase=4 -->
### p4-review-1 · review · phase 4 review: 16 findings (15 in, 1 out) over four rounds (phase 4)

Dispatched Opus reviewer read 800267752..16f136be3 adversarially against R12, R13, §G-§I, verified the five mid-phase security fixes held (symlink follow, root symlink/traversal, unpinned merge, forge file list, export backlog), and raised p4-r1..r11; re-verified after fixes and raised p4-r12..r14, then p4-r15..r16; final pass at d9eb4fc1a: all fixed, none new (1818 passed). Separate automated security reviews also caught a force-add exposure (fixed in p4-r9).

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-10-06T00:00:58+00:00 phase=4 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: export PR merged outside the driver (or crash after pr_merge) is never marked merged; export_target pins to it forever and later waves never export, silently (phase 4)

export-reconcile records the merge (4245d98e0); tests test_a_recorded_pr_merged_outside_the_driver_is_reconciled, test_after_a_reconciled_merge_the_next_wave_exports, test_an_export_pr_merged_outside_the_driver_is_recorded_and_the_next_wave_exports.

<!-- fr:journal kind=finding scope=plan id=p4-r2-resolved created=2026-10-06T00:00:58+00:00 phase=4 state=fixed resolves=p4-r2 -->
### p4-r2-resolved · finding [fixed] · resolves p4-r2: ExportConfig accepts trailing-slash/./empty-part paths that contained() refuses every pass; _export_config rstrips '/' but _export does not (phase 4)

path normalised once at load with contained()'s refusal set (bffb98f54); tests test_the_export_path_is_normalised_once_at_load, test_an_export_path_contained_would_refuse_is_refused_at_load.

<!-- fr:journal kind=finding scope=plan id=p4-r3-resolved created=2026-10-06T00:00:58+00:00 phase=4 state=fixed resolves=p4-r3 -->
### p4-r3-resolved · finding [fixed] · resolves p4-r3: crash between pr_create and record, plus a wave finishing before the next pass, opens a second export PR (adoption looks only at the highest owed wave's branch) (phase 4)

orphans on any wave branch are reused; no second PR (0ef4cb772, b154a5382); tests test_a_crash_then_a_new_wave_reuses_the_orphan_and_opens_no_second_pr, test_a_crash_after_opening_then_a_new_wave_opens_exactly_one_pr.

<!-- fr:journal kind=finding scope=plan id=p4-r4-resolved created=2026-10-06T00:00:58+00:00 phase=4 state=fixed resolves=p4-r4 -->
### p4-r4-resolved · finding [fixed] · resolves p4-r4: pr_create ValueError (no PR URL) is not in FORGE_ERRORS: driver tracebacks instead of exiting 1 (phase 4)

GhError, exit 1 (f33017b97); test test_pr_create_refuses_an_answer_with_no_pr_url.

<!-- fr:journal kind=finding scope=plan id=p4-r5-resolved created=2026-10-06T00:00:58+00:00 phase=4 state=fixed resolves=p4-r5 -->
### p4-r5-resolved · finding [fixed] · resolves p4-r5: import's mtime "newer" check is defeated by git checkout mtimes; docstring overclaims "never silently overwritten" (phase 4)

identical files skipped, mtime rule documented in docstring and --force help (47846d80f); tests test_a_byte_identical_file_is_neither_copied_nor_overwritten, test_the_newer_check_is_documented_as_mtime_based.

<!-- fr:journal kind=finding scope=plan id=p4-r6-resolved created=2026-10-06T00:00:58+00:00 phase=4 state=fixed resolves=p4-r6 -->
### p4-r6-resolved · finding [fixed] · resolves p4-r6: a recorded export PR closed unmerged blocks that repo's exports forever with no documented recovery (phase 4)

closed recorded once, waves owed again (4245d98e0); tests test_a_recorded_pr_closed_unmerged_is_recorded_closed_once, test_waves_of_a_closed_export_are_owed_again, test_a_closed_unmerged_export_pr_is_recorded_once_then_re_exported.

<!-- fr:journal kind=finding scope=plan id=p4-r7-resolved created=2026-10-06T00:00:58+00:00 phase=4 state=fixed resolves=p4-r7 -->
### p4-r7-resolved · finding [fixed] · resolves p4-r7: any fork PR named chore/triage-state-wave-N blocks the export (untrusted row); cross-repo PRs could be ignored safely (phase 4)

cross-repo PRs ignored (0ef4cb772); test test_a_fork_pr_on_the_export_branch_name_is_ignored.

<!-- fr:journal kind=finding scope=plan id=p4-r8-resolved created=2026-10-06T00:00:58+00:00 phase=4 state=fixed resolves=p4-r8 -->
### p4-r8-resolved · finding [fixed] · resolves p4-r8: adoption after a crash pins and auto-merges whatever trusted-PR head is live, with no proof the driver pushed it (phase 4)

superseded by the reuse redesign: the driver never adopts content, it force-pushes its own commit and pins to it (b154a5382); test test_an_orphan_is_reused_with_the_drivers_own_commit_never_its_foreign_one.

<!-- fr:journal kind=finding scope=plan id=p4-r9-resolved created=2026-10-06T00:00:58+00:00 phase=4 state=fixed resolves=p4-r9 -->
### p4-r9-resolved · finding [fixed] · resolves p4-r9: commit_paths uses git add without -f, so gitignored durable files are silently not exported (phase 4)

fixed by reporting, never force-adding (226176276, replacing 51c5d0f99 after a security review flagged --force as sensitive-data exposure; names local, count in the PR body 2570b389f); test test_files_the_target_repo_ignores_are_reported_never_force_added, test_commit_paths_never_forces_past_gitignore_and_ignored_names_what_it_left.

<!-- fr:journal kind=finding scope=plan id=p4-r10-resolved created=2026-10-06T00:00:58+00:00 phase=4 state=fixed resolves=p4-r10 -->
### p4-r10-resolved · finding [fixed] · resolves p4-r10: untested leftover-worktree path; non-worktree export dir fails every pass; OSError in _sync escapes as a traceback (phase 4)

(0f952056e); tests test_a_leftover_export_worktree_with_changes_is_replaced, test_a_plain_directory_at_the_export_scratch_path_is_replaced, test_a_filesystem_error_while_exporting_is_a_warn_for_the_wave, test_a_filesystem_error_is_a_clean_triage_error.

<!-- fr:journal kind=finding scope=plan id=p4-r11-resolved created=2026-10-06T00:00:58+00:00 phase=4 state=open resolves=p4-r11 out_of_scope=true -->
### p4-r11-resolved · finding [out-of-scope] · resolves p4-r11: local check-to-write race between the symlink check and copy2 in state_sync (local attacker only) (phase 4)

A local attacker who can swap files in the operator's own state dir already owns them; no privilege boundary is crossed. Not caused by an implementation error in this change's threat model.

<!-- fr:journal kind=finding scope=plan id=p4-r12-resolved created=2026-10-06T00:00:58+00:00 phase=4 state=fixed resolves=p4-r12 -->
### p4-r12-resolved · finding [fixed] · resolves p4-r12: adoption's single-commit proof is structural, not authorship: a force-pushed single commit inside the export dir is still adopted and auto-merged; compare the orphan's tree to a local re-export (phase 4)

reuse redesign: only driver-written commits are ever pinned (b154a5382, spec d6dd51bae); test test_an_orphan_is_reused_with_the_drivers_own_commit_never_its_foreign_one.

<!-- fr:journal kind=finding scope=plan id=p4-r13-resolved created=2026-10-06T00:00:58+00:00 phase=4 state=fixed resolves=p4-r13 -->
### p4-r13-resolved · finding [fixed] · resolves p4-r13: a recorded-closed export PR that is reopened is never an orphan; the re-export force-pushes its branch and gh pr create fails (exit 1) every pass (phase 4)

reopened PR reused, no pr_create (b154a5382); test test_a_reopened_pr_recorded_closed_is_reused.

<!-- fr:journal kind=finding scope=plan id=p4-r14-resolved created=2026-10-06T00:00:58+00:00 phase=4 state=fixed resolves=p4-r14 -->
### p4-r14-resolved · finding [fixed] · resolves p4-r14: names of gitignored durable files are published in the public export PR body; keep names local, put a count in the PR (phase 4)

PR body carries a count only (2570b389f); test test_files_the_target_repo_ignores_are_reported_never_force_added.

<!-- fr:journal kind=finding scope=plan id=p4-r15-resolved created=2026-10-06T00:00:58+00:00 phase=4 state=fixed resolves=p4-r15 -->
### p4-r15-resolved · finding [fixed] · resolves p4-r15: export PR base branch is never checked at reuse or merge: a retargeted/orphan PR auto-merges default-branch history plus the export into an arbitrary branch (phase 4)

baseRefName read fresh; non-default/unknown base is warned and blocked, never reused or merged (d9eb4fc1a); tests test_a_recorded_export_pr_not_based_on_the_default_branch_is_never_merged, test_an_orphan_not_based_on_the_default_branch_is_never_reused, test_a_retargeted_recorded_export_pr_is_never_merged, test_an_orphan_based_on_another_branch_is_not_reused_and_nothing_is_pushed.

<!-- fr:journal kind=finding scope=plan id=p4-r16-resolved created=2026-10-06T00:00:58+00:00 phase=4 state=fixed resolves=p4-r16 -->
### p4-r16-resolved · finding [fixed] · resolves p4-r16: when several orphan export PRs are open only the highest is reused; the others stay open with no warn (phase 4)

each extra orphan warned stale once (d9eb4fc1a); tests test_every_orphan_besides_the_reused_one_is_warned_stale_once, test_extra_orphans_are_warned_stale_once_each.

<!-- fr:journal kind=finding scope=plan id=p4-archive-pr-base-unchecked-resolved created=2026-10-06T00:00:58+00:00 phase=4 state=open resolves=p4-archive-pr-base-unchecked out_of_scope=true -->
### p4-archive-pr-base-unchecked-resolved · finding [out-of-scope] · resolves p4-archive-pr-base-unchecked: the wave driver's archive-PR merge path never checks the PR's base branch either (phase 4)

Pre-existing behaviour of the archive path; to be filed as its own issue at the merge touchpoint.

<!-- fr:journal kind=discovery scope=plan id=p5-blocked-on-969 created=2026-10-06T06:23:23+00:00 phase=5 -->
### p5-blocked-on-969 · discovery · Task 2 unblocked: PR #969 merged (phase 5)

PR #969 (chore/triage-state) merged to origin/main. Coordinator merged main into
feat branch (commit b8a528795). No rebase needed. Task 2 proceeded with fresh
import/render verification.

<!-- fr:journal kind=discovery scope=plan id=p5-t1-skills-documented created=2026-10-06T06:23:23+00:00 phase=5 -->
### p5-t1-skills-documented · discovery · Task 1 complete: Skills document pages, fragments, and fields (phase 5)

All three skills (fr-triage, fr-origins, fr-audit) now document:
- Four page goals and their use cases
- Fragment manifests for hand-written analysis
- New fields: severity, duplicate_of, fixed_by, introduced_in
- Schema versions and export config
- History verb and state export/import verbs
Tests pass: 13 new tests validate the documentation, tripwires enforce skill length and tool neutrality.

<!-- fr:journal kind=discovery scope=plan id=p5-t2-state-configured created=2026-10-06T06:23:23+00:00 phase=5 -->
### p5-t2-state-configured · discovery · Task 2 complete: Triage state configured for export (phase 5)

P5.T2.S1 completed: deleted docs/triage/sync.sh; rewrote README.md sync commands to use
`uv run fr triage state import --from docs/triage --repo derio-net/super-fr` and export;
created history/manifest.yaml with timeline, finished-waves, and three dated fragments
(closing order, origins analysis, history to 2026-10-02); dropped moved sections from
architecture manifest; added `export: {path: docs/triage}` to .fr/triage.yaml (spec R13).
P5.T2.S2 verified: import succeeded, architecture and history renders show no missing-fragment
or moved-name warnings.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t1 created=2026-10-06T06:23:23+00:00 phase=5 -->
### no-refactor-p5-t1 · discovery · no-refactor-because P5.T1 (phase 5)

Prose skills have no refactor step; documentation additions are concise and targeted

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t2 created=2026-10-06T06:23:23+00:00 phase=5 -->
### no-refactor-p5-t2 · discovery · no-refactor-because P5.T2 (phase 5)

file moves, a deleted script and one config key: no code to clean

<!-- fr:journal kind=finding scope=plan id=p5-r1 created=2026-10-06T06:31:44+00:00 phase=5 state=open review_scope=in -->
### p5-r1 · finding [open] (reviewer: in scope) · authored-src/build.py wrote history fragments into architecture/, so history/manifest.yaml entries stayed missing (phase 5)

Raised by the phase 5 reviewer (separate dispatched context), which also reviewed the merge of main (b8a528795).

<!-- fr:journal kind=finding scope=plan id=p5-r2 created=2026-10-06T06:31:44+00:00 phase=5 state=open review_scope=in -->
### p5-r2 · finding [open] (reviewer: in scope) · pipeline.py aborts on closed pinned issues, so built fragments cannot be regenerated from imported state (phase 5)

Raised by the phase 5 reviewer (separate dispatched context), which also reviewed the merge of main (b8a528795).

<!-- fr:journal kind=finding scope=plan id=p5-r3 created=2026-10-06T06:31:44+00:00 phase=5 state=open review_scope=in -->
### p5-r3 · finding [open] (reviewer: in scope) · fr-triage skill described export as a PR per wave and omitted the R13 specifics (phase 5)

Raised by the phase 5 reviewer (separate dispatched context), which also reviewed the merge of main (b8a528795).

<!-- fr:journal kind=finding scope=plan id=p5-r4 created=2026-10-06T06:31:44+00:00 phase=5 state=open review_scope=in -->
### p5-r4 · finding [open] (reviewer: in scope) · skills omitted the new check sets and the Parked/placed behaviour of duplicate_of (phase 5)

Raised by the phase 5 reviewer (separate dispatched context), which also reviewed the merge of main (b8a528795).

<!-- fr:journal kind=finding scope=plan id=p5-r5 created=2026-10-06T06:31:44+00:00 phase=5 state=open review_scope=in -->
### p5-r5 · finding [open] (reviewer: in scope) · fr-origins still said duplicate discipline was prose-only though duplicate_of is now validated (phase 5)

Raised by the phase 5 reviewer (separate dispatched context), which also reviewed the merge of main (b8a528795).

<!-- fr:journal kind=finding scope=plan id=p5-r6 created=2026-10-06T06:31:44+00:00 phase=5 state=open review_scope=in -->
### p5-r6 · finding [open] (reviewer: in scope) · "board" named three things and the skill did not disambiguate; the file table omitted board.html (phase 5)

Raised by the phase 5 reviewer (separate dispatched context), which also reviewed the merge of main (b8a528795).

<!-- fr:journal kind=finding scope=plan id=p5-r7 created=2026-10-06T06:31:44+00:00 phase=5 state=open review_scope=in -->
### p5-r7 · finding [open] (reviewer: in scope) · docs/triage/README.md was stale on manifests, timeline attribution, fragments and the recipe (phase 5)

Raised by the phase 5 reviewer (separate dispatched context), which also reviewed the merge of main (b8a528795).

<!-- fr:journal kind=review scope=plan id=p5-review-1 created=2026-10-06T06:31:44+00:00 phase=5 -->
### p5-review-1 · review · phase 5 review: 7 findings (all tagged in; p5-r2 reclassified out) (phase 5)

Dispatched reviewer read the phase 5 range and the merge resolution of b8a528795 (#969, #980) against R14, R15 and R1-R13, ran both mirror checks and the triage/skill tests, imported the repo state and rendered it. Merge resolution judged clean. Findings fixed in 591cc7a96 and re-verified (2057 passed); p5-r2 reclassified out of scope with reasoning.

<!-- fr:journal kind=finding scope=plan id=p5-r1-resolved created=2026-10-06T06:31:44+00:00 phase=5 state=fixed resolves=p5-r1 -->
### p5-r1-resolved · finding [fixed] · resolves p5-r1: authored-src/build.py wrote history fragments into architecture/, so history/manifest.yaml entries stayed missing (phase 5)

build.py writes the dated fragments to history/ (591cc7a96); docstring and README match.

<!-- fr:journal kind=finding scope=plan id=p5-r2-resolved created=2026-10-06T06:31:44+00:00 phase=5 state=open resolves=p5-r2 out_of_scope=true -->
### p5-r2-resolved · finding [out-of-scope] · resolves p5-r2: pipeline.py aborts on closed pinned issues, so built fragments cannot be regenerated from imported state (phase 5)

Reclassified: the abort is #969's deliberate guard (the build stops if a pinned issue has closed), stale because those issues closed since; choosing which open issues pin to which pipeline step is operator curation, not caused by this change. The README now says to refresh the pin table first.

<!-- fr:journal kind=finding scope=plan id=p5-r3-resolved created=2026-10-06T06:31:44+00:00 phase=5 state=fixed resolves=p5-r3 -->
### p5-r3-resolved · finding [fixed] · resolves p5-r3: fr-triage skill described export as a PR per wave and omitted the R13 specifics (phase 5)

The driver paragraph states R13 in full (591cc7a96).

<!-- fr:journal kind=finding scope=plan id=p5-r4-resolved created=2026-10-06T06:31:44+00:00 phase=5 state=fixed resolves=p5-r4 -->
### p5-r4-resolved · finding [fixed] · resolves p5-r4: skills omitted the new check sets and the Parked/placed behaviour of duplicate_of (phase 5)

fr-triage and fr-origins name every new check set; duplicate_of's Parked/placed behaviour documented (591cc7a96).

<!-- fr:journal kind=finding scope=plan id=p5-r5-resolved created=2026-10-06T06:31:44+00:00 phase=5 state=fixed resolves=p5-r5 -->
### p5-r5-resolved · finding [fixed] · resolves p5-r5: fr-origins still said duplicate discipline was prose-only though duplicate_of is now validated (phase 5)

Wording corrected; the test pinning the old claim now asserts the new one (591cc7a96).

<!-- fr:journal kind=finding scope=plan id=p5-r6-resolved created=2026-10-06T06:31:44+00:00 phase=5 state=fixed resolves=p5-r6 -->
### p5-r6-resolved · finding [fixed] · resolves p5-r6: "board" named three things and the skill did not disambiguate; the file table omitted board.html (phase 5)

Backlog page vs Kanban disambiguated, board.html in the file table (591cc7a96).

<!-- fr:journal kind=finding scope=plan id=p5-r7-resolved created=2026-10-06T06:31:44+00:00 phase=5 state=fixed resolves=p5-r7 -->
### p5-r7-resolved · finding [fixed] · resolves p5-r7: docs/triage/README.md was stale on manifests, timeline attribution, fragments and the recipe (phase 5)

README rewritten for the four page manifests, R12, the history render and the export opt-in (591cc7a96).

<!-- fr:journal kind=finding scope=plan id=p1-visual-matcher-uv-with-resolved-2 created=2026-10-06T08:01:59+00:00 state=open resolves=p1-visual-matcher-uv-with tracked_by=#999 -->
### p1-visual-matcher-uv-with-resolved-2 · finding [deferred → #999] · resolves p1-visual-matcher-uv-with: capture-script witness misreads uv run --with

Filed at closeout as #999.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved-2 created=2026-10-06T08:02:02+00:00 state=open resolves=p1-r4 tracked_by=#1000 -->
### p1-r4-resolved-2 · finding [deferred → #1000] · resolves p1-r4: cancelled-only waves count as finished and silently vanish from the board (spec'd predicate, undocumented consequence)

Filed at closeout as #1000.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved-2 created=2026-10-06T08:02:05+00:00 state=open resolves=p1-r6 tracked_by=#1001 -->
### p1-r6-resolved-2 · finding [deferred → #1001] · resolves p1-r6: board wave table is cramped at 390px (columns wrap letter by letter); predates this phase, board relayout is R2-R5

Filed at closeout as #1001.

<!-- fr:journal kind=finding scope=plan id=p2-suite-log-background-unwitnessed-resolved-2 created=2026-10-06T08:02:07+00:00 state=open resolves=p2-suite-log-background-unwitnessed tracked_by=#1002 -->
### p2-suite-log-background-unwitnessed-resolved-2 · finding [deferred → #1002] · resolves p2-suite-log-background-unwitnessed: fr cannot witness a suite log written by a run_in_background command, which the brief's own long_commands rule prescribes

Filed at closeout as #1002.
