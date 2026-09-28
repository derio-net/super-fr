# Journal: 2026-09-28-phase-sizing

<!-- fr:journal kind=decision scope=plan id=plan-one-phase created=2026-09-28T20:19:10+00:00 -->
### plan-one-phase · decision · One agentic phase, dogfooding the rule this plan implements

The change serves one independently reviewable ask (size phases to the asks, with its checks and prose), so the plan has one agentic phase, tier hard: no skeleton, no phase-split decisions, no [manual] phase. The post-merge fr-goal check is a Test Plan line; the before/after audit is #793.

<!-- fr:journal kind=discovery scope=plan id=p1-sizing-gate-reaches-run-fixtures created=2026-09-28T21:00:17+00:00 phase=1 -->
### p1-sizing-gate-reaches-run-fixtures · discovery · The sizing gate reached every run-walk fixture whose spec seed_requirements gives a Requirements table (phase 1)

`tests/unit/requirements_support.seed_requirements` appends a parsing `## Requirements`
table to the fixture spec, so once `_phase_sizing_issues` landed, plan-review (which
executes `fr plan self-review`) failed for every test walking a run past it: 50 tests in
test_record_apply / test_record_review_fixes / test_record_template / test_record_verbs /
test_run_question_rounds / test_deliver_pr_body* / test_migration_record_input_unconfirmed
(all via `tests/unit/record_support._plan`) plus 3 in tests/integration/test_fr_goal_shape.py
(`_toy_plan` and the tier-join test). Their phases link no acceptance rows. Fixed in the
fixtures, not the gate: a new `requirements_support.write_phase_splits` records a
`phase-split-<plan>-p<N>` waiver decision (`review-size:` / `tier:`) per phase, the same
pattern record_support already used for `skeleton-override-*`.

<!-- fr:journal kind=decision scope=plan id=p1-deviation-requirements-helper created=2026-09-28T21:00:17+00:00 phase=1 -->
### p1-deviation-requirements-helper · decision · DEVIATION: added fr.requirements.has_requirements_table, and two extra proportionality lines (phase 1)

Not named in the plan. §B's fail-open warning needs to tell a broken
`| id | requirement | source |` table from a legacy prose section; the section locator and
row splitter are private to fr.requirements, so a small public predicate lives there
rather than a copy in plan_ops. In proportionality's `## Phases`, two cases the spec does
not word got their own line instead of a misleading one: a cross-repo spec ("spec lives in
another repo; asks cannot be counted.") and a matrix that fails to parse at HEAD
("acceptance matrix unreadable at HEAD; asks cannot be derived."). A plan with no spec
prints the spec's no-Requirements line.

<!-- fr:journal kind=decision scope=plan id=p1-deviation-skill-tokens-and-line-cap created=2026-09-28T21:00:17+00:00 phase=1 -->
### p1-deviation-skill-tokens-and-line-cap · decision · DEVIATION: updated test_skill_tokens' 4–6-phases pin and joined two fr-plan bullets onto single lines (phase 1)

`tests/unit/test_skill_tokens.py::test_fr_plan_names_phase_granularity_guidance` asserted
"4–6 phases" and "fr run status" were in fr-plan — the exact guidance R7 removes. It now
asserts the phrase is gone, the one-phase-per-ask rule is present, and the cost pointer is
`fr run cost` (where per-step cost has lived since run schema 7). The rewritten "Size phases
to the asks" and "Pure agentic phases" bullets pushed fr-plan/SKILL.md to 133 lines against
test_skill_validation's 120-line cap, so those two bullets are each one long line (the file
already carries long single-line bullets, e.g. Tier); it is 115 lines now. P1.T6.S1's full
suite ran in the background with a bounded poll, per the dispatch brief's override.

<!-- fr:journal kind=discovery scope=plan id=p1-proportionality-spec-ref-from-meta created=2026-09-28T21:00:17+00:00 phase=1 -->
### p1-proportionality-spec-ref-from-meta · discovery · proportionality's Phases section takes the spec PATH from the parsed plan meta, everything else from HEAD (phase 1)

`_phases` reads the spec text, the matrix and the spec journal with `_show_head`, and the
phase headers via `_phases_at_head`, but the spec path and plan slug come from the parsed
working-tree `Plan` (as `_justifiers` already did for the slug). An uncommitted edit of
`_meta.yaml`'s `spec:` would change the report; editing the spec reference mid-run is not a
realistic path, so this was left as is rather than reading `_meta.yaml` at HEAD too.

<!-- fr:journal kind=discovery scope=plan id=p1-full-suite-flake created=2026-09-28T21:00:17+00:00 phase=1 -->
### p1-full-suite-flake · discovery · test_suite_isolation_inherited_columns timed out once under the loaded full suite, passes alone (phase 1)

Final full run: 1 failed, 6953 passed, 97 skipped. The one failure was a
subprocess.TimeoutExpired in tests/unit/test_suite_isolation_inherited_columns.py (a nested
pytest run) during an 11.7-minute xdist run on a loaded host; rerun alone it passed. It
touches no code this phase changed.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-09-28T21:00:17+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

The Phases section is one helper (_phases) beside _size; it reuses _show_head, _rel, _bullets and fr.phase_sizing, and the module docstring was updated in the green step — nothing duplicated to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-09-28T21:00:17+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

Prose-only task: the skill edits were written once in their final form and both mirrors regenerated; no code to refactor.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-09-28T21:00:17+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

Docs, a change fragment and matrix status moves through fr acceptance set-status; no code to refactor.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-09-28T21:20:39+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · phase-split fix paths named an id `fr journal add` refuses, wedging plan-review (phase 1)

severity: important
scope reason: this change introduced the only fix path it suggests

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-09-28T21:20:39+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · proportionality's Phases section read the spec path and plan slug from the working tree (phase 1)

severity: minor
scope reason: new section, breaks the HEAD-only contract deliver hashes

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-09-28T21:20:39+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · an existing but unreadable matrix was reported as 'no matrix' and the floor skipped silently (phase 1)

severity: minor
scope reason: new message is wrong for that case

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-09-28T21:20:39+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · unparseable-table warning blamed the Requirements table when Deferred was broken (phase 1)

severity: minor
scope reason: new warning wording

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-09-28T21:20:39+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · skill prose said --slug <spec-slug>, a stem that writes to a journal nothing reads (phase 1)

severity: minor
scope reason: new prose

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-09-28T21:20:39+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · split decisions naming a non-agentic or missing phase were silently ignored (or errored unfixably when malformed) (phase 1)

severity: minor
scope reason: new behaviour

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-09-28T21:20:39+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · run-walk fixtures passed the gate only via waivers, never the normal own-ask path (phase 1)

severity: minor
scope reason: fixture change in this PR

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-09-28T21:20:39+00:00 phase=1 state=open review_scope=in -->
### p1-r8 · finding [open] (reviewer: in scope) · an ask: phase could claim an ask a waived phase also serves (phase 1)

severity: minor
scope reason: RECLASSIFIED: the reviewer tagged it out (follows spec §A as written), but the waiver exclusion is this change's own s2 rule, so the hole it opens is this change's

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-09-28T21:20:39+00:00 phase=1 -->
### p1-review · review · Independent review of phase 1: 8 findings (1 important, 7 minor), all fixed (phase 1)

Reviewer (dispatched, separate context) checked spec §A–§E, the rule table, s1/s2, cut-off, §C, proportionality HEAD purity, fixtures, prose and explainer; ran 102 targeted tests + tripwires. Findings p1-r1..p1-r8 raised; all verified against the code (r1: journal_cmd.py:238 refuses an existing id) and fixed by the implementer with tests first (commits 0977b94d, 46cb1b24, aa8a2556, 219fbbeb; targeted suites 494 passed). r8 reclassified out->in by the orchestrator (see its finding).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-09-28T21:20:39+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: phase-split fix paths named an id `fr journal add` refuses, wedging plan-review (phase 1)

0977b94d: superseding ids phase-split-<plan>-p<N>-<k> (highest k wins), next_split_id named in floor/ceiling/malformed messages; CliRunner test drives the suggested command.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-09-28T21:20:39+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: proportionality's Phases section read the spec path and plan slug from the working tree (phase 1)

46cb1b24: _meta.yaml read at HEAD, spec probed per spec folder at HEAD; tests for uncommitted spec: edit, uncommitted git mv, archived-at-HEAD.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-09-28T21:20:39+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: an existing but unreadable matrix was reported as 'no matrix' and the floor skipped silently (phase 1)

0977b94d: 'acceptance matrix unreadable (<e>); ask floor not checked' when the file exists; tested.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-09-28T21:20:39+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: unparseable-table warning blamed the Requirements table when Deferred was broken (phase 1)

0977b94d: worded 'Requirements/Deferred tables do not parse (<e>)'; tested.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-09-28T21:20:39+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: skill prose said --slug <spec-slug>, a stem that writes to a journal nothing reads (phase 1)

aa8a2556: --slug <spec-journal-slug> explained as the stem without -design; mirrors regenerated; prose tests.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-09-28T21:20:39+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: split decisions naming a non-agentic or missing phase were silently ignored (or errored unfixably when malformed) (phase 1)

0977b94d: orphan decisions warn and never raise the malformed error; tested for manual, nonexistent and malformed orphans.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-09-28T21:20:39+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: run-walk fixtures passed the gate only via waivers, never the normal own-ask path (phase 1)

219fbbeb: phase 1 of record_support._plan and _toy_plan link the seeded req-r1 row; waivers kept only on later toy phases.

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-09-28T21:20:39+00:00 phase=1 state=fixed resolves=p1-r8 -->
### p1-r8-resolved · finding [fixed] · resolves p1-r8: an ask: phase could claim an ask a waived phase also serves (phase 1)

0977b94d: an ask: phase subtracts every other agentic phase incl. waived; s2 pair still passes; spec §A and docstring updated; unit + gate tests.
