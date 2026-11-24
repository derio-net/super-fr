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
