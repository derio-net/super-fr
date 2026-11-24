<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-show-me-visuals

<!-- fr:journal kind=decision scope=plan id=p1-run-cmd-budget created=2026-11-24T17:55:32+00:00 phase=1 -->
### p1-run-cmd-budget · decision · run_cmd.py's line budget moves 9100 -> 9120 for three fr.shape call sites (phase 1)

run_cmd.py sat at 9097 of 9100. Every shape check lives in fr/shape.py
(`spec_shape_refusal`, `deliver_shape_refusal`, `shape_path`); what remains in
run_cmd.py is the `_refuse_spec_shape` sibling the plan names, the deliver
refusal's three lines and the lens brief's `shape_path` argument (9113 lines).
The budget moves by 20 in tests/unit/test_tripwire_module_budget.py, with a
comment; the PR body should say why (the tripwire's own instruction).

<!-- fr:journal kind=decision scope=plan id=p1-run-shape-one-decision created=2026-11-24T17:55:32+00:00 phase=1 -->
### p1-run-shape-one-decision · decision · fr.shape.run_shape is the one "does this run owe a shape" decision (phase 1)

`run_shape(repo_root, state)` returns no-spec | unreadable | predates | owed and
the spec's path; `shape_section` (the PR body) and `deliver_shape_refusal`
(the deliver gate, run first in `_deliver_pr_gate`, before the render) both read
it (P1.T3.S3). A spec that cannot be read renders the shape file or
`No shape file was written.`, but deliver refuses it before any render anyway.

<!-- fr:journal kind=decision scope=plan id=p1-empty-lens-set-no-shape created=2026-11-24T17:55:32+00:00 phase=1 -->
### p1-empty-lens-set-no-shape · decision · an empty lens set's brief carries no `shape` key (phase 1)

`lens_review_brief` adds `shape` (absolute path, or null when the file does not
exist) only beside a non-empty `set`: an empty set dispatches no reviewer, and
`test_an_empty_set_says_so_and_owes_no_reviewer` pins its keys as exactly
{set, note}. R16's reader is the lens reviewer, who exists only for a non-empty set.

<!-- fr:journal kind=discovery scope=plan id=p1-fixture-shape created=2026-11-24T17:55:32+00:00 phase=1 -->
### p1-fixture-shape · discovery · fixture specs gain a design shape and walked runs a shape file, in two helpers (phase 1)

`tests/unit/requirements_support.seed_requirements` now appends a
`## Design shape` (`none — ...`) to the spec it seeds, and
`tests/integration/test_fr_goal_shape._drive_to_implement` writes the run's shape
file (`write_shape_file`), so every template that walks brainstorm -> deliver
(started_run, at_deliver, at_spec_review) passes both gates. Specs written
inline by a test that resolves brainstorm or a spec review need the section
themselves (test_closeout_e2e).

<!-- fr:journal kind=decision scope=plan id=p1-demotion-keyword created=2026-11-24T17:55:32+00:00 phase=1 -->
### p1-demotion-keyword · decision · the Test Plan heading repair stops at `## Design shape` (phase 1)

`fr.artifacts.spec_test_plan_heading._KEYWORD_RE` gains `Design shape`:
`test_the_demotion_keywords_are_exactly_the_sections_fr_reads_by_keyword` pins
every `## <Keyword>` spec reader (fr.shape.DESIGN_SHAPE_HEADING is one) to the
repair's stop set, so demoting a misplaced Test Plan region never pushes the
design shape below level two where `design_shape_section` would stop finding it.
Repair logic only; no artifact's shape moves, so no stamp.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-24T19:05:18+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · fr.shape's path display duplicated run_cmd._shown_path without resolving (phase 1)

`shape.py` `_shown` took `relative_to` on unresolved paths, unlike `run_cmd._shown_path`, so on a
symlinked checkout (macOS /var) the deliver shape refusal could print an absolute path while the
PR-body refusal printed a relative one.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-24T19:05:18+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · test_fr_shape_imports only asserted the module imports (phase 1)

Every other test in tests/unit/test_shape.py already imports fr.shape; the smoke test added nothing once they existed.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-24T19:05:18+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · an already-archived cursor left its live shape file behind (phase 1)

`archive_run_cursor`'s early-return branch (cursor archived, usage file live) moved only the usage
file, so a re-run after a partial archive left `<run-id>.shape.md` (and `.pr-body.md`) in runs/.

<!-- fr:journal kind=review scope=plan id=p1-review-r1 created=2026-11-24T19:05:18+00:00 phase=1 -->
### p1-review-r1 · review · phase 1 review: 3 findings in scope, all fixed (phase 1)

An independent reviewer read the phase 1 diff against R6–R12, R16–R18. It found no correctness bug in
the requirement surfaces and three low-severity findings, all in scope and fixed in one commit.
No lens suggested.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-24T19:05:18+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: fr.shape's path display duplicated run_cmd._shown_path without resolving (phase 1)

`fr.shape.shown_path` resolves both sides and is the one helper; `run_cmd._shown_path` aliases it.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-24T19:05:18+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: test_fr_shape_imports only asserted the module imports (phase 1)

Deleted the import-only test; the rest of the file still exercises the module.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-24T19:05:18+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: an already-archived cursor left its live shape file behind (phase 1)

The early-return branch also moves the PR body render and the shape file; tests/unit/test_archive_cmd.py::test_an_already_archived_cursor_carries_its_live_shape_file (red without the fix).

<!-- fr:journal kind=discovery scope=plan id=p2-skill-line-cap created=2026-11-24T20:35:53+00:00 phase=2 -->
### p2-skill-line-cap · discovery · a skill is capped at 120 lines by test_skill_validation, not the plan's ~150 (phase 2)

`tests/unit/test_skill_validation.py::test_under_120_lines` fails any SKILL.md over 120
lines, and fr-goal and fr-brainstorming already sit at exactly 120. fr-show-me is 117
lines; the fr-goal and fr-brainstorming sentences were added inside existing paragraphs
so neither file grew a line.

<!-- fr:journal kind=discovery scope=plan id=p2-new-skill-surfaces created=2026-11-24T20:35:53+00:00 phase=2 -->
### p2-new-skill-surfaces · discovery · a new skill also needs `fr skills`, the README summary line and a covering page (phase 2)

Beyond the mirrors, a new skill must be listed in `fr.commands.skills_cmd.SKILLS`
(`test_skills_cmd.py::test_skill_files_match_skills_list`), have a line in
`scripts/readme-skill-summaries.yaml` (the README sync), and be covered by an explainer
(`test_tripwire_readme_sync.py::test_every_shipped_skill_row_links_to_a_page`). So
docs/explainers/fr-show-me.md was written in Task 1, not Task 4, to keep Task 1's commit
green; Task 4 then edited the other pages.

<!-- fr:journal kind=decision scope=plan id=p2-shape-file-before-journal-check created=2026-11-24T20:35:53+00:00 phase=2 -->
### p2-shape-file-before-journal-check · decision · fr-goal §7a tells the agent to write the shape file before the last review-phase resolve (phase 2)

The lens-review brief is built when the last `review-phase` resolve's journal-check pass
prints it, and `lens_review_brief` sets `shape` to null when the file does not exist yet.
To make the brief name the file (as the spec's sequence diagram draws it: write, commit,
journal-check passes, brief with `shape`), §7a says to write and commit
`<run-id>.shape.md` before that resolve, and to pass the path anyway when the brief says
null. No code change: `fr run advance --redispatch` exists but re-briefing for this would
be a misuse of it.

<!-- fr:journal kind=decision scope=plan id=p2-reviewer-fourth-check created=2026-11-24T20:35:53+00:00 phase=2 -->
### p2-reviewer-fourth-check · decision · fr-spec-reviewer's design-shape check is a fourth numbered check (phase 2)

"What you check — three things" became four, with `**Design shape.**` after Internal
consistency; the light-path paragraph says "the four checks above", and
test_spec_reviewer_agent.py's ordering test now names four. A `none — <reason>` shape is
a finding only when the Design moves files or boundaries a picture would show. The agents
kind moved 6 -> 7 with a registered rerender hop; `.claude/agents/` re-rendered in its own
`chore(fr): migrate artifacts` commit.

<!-- fr:journal kind=decision scope=plan id=p2-docs-pages created=2026-11-24T20:35:53+00:00 phase=2 -->
### p2-docs-pages · decision · pages edited where incomplete, re-stamped where still true (phase 2)

Edited: 01-fr-goal.md (design shape in the spec, the reviewer's check, the shape file
before the lens reviewers, the PR's Shape of the change), fr-brainstorming-and-plan.md
(the `## Design shape` bullet), review-lenses.md (the brief's `shape` key and the return
rule). Re-stamped with a note: index.md, why-fr.md, ops.md, reference/cli.md,
reference/workflow-shapes.md. `fr docs check --base origin/main`: 33 pages current.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-24T20:35:53+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

the skill was written to the 120-line cap from the start (117 lines); the reread found nothing to cut and the neutrality tripwire stayed green

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-24T20:35:53+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

each added fr-goal sentence names a different place (§1 the spec, §7a the file and the brief key, §8 the render and refusal, light path a pointer back), and §7a matches lens_review_brief's `shape` key as built; nothing repeated

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-11-24T20:35:53+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

the agent edit is one numbered check; `fr validate artifacts` is clean and test_every_version_bump_registers_its_re_render_hop already asserts every hop 1..7

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-11-24T20:35:53+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

pages edited where the change made them incomplete, re-stamped where still true; the writing-standard check reports no FAIL and no warning on the added text
