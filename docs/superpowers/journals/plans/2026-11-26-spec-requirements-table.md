<!-- fr:journal-schema=4 -->
# Journal: 2026-11-26-spec-requirements-table

<!-- fr:journal kind=decision scope=plan id=plan-one-phase created=2026-11-28T09:31:29+00:00 -->
### plan-one-phase · decision · One agentic phase, by operator decision

Operator chose "One phase" over the recommended two-phase split. The phase is tier hard (decision tier-2026-11-26-spec-requirements-table-p1 in the spec journal).

<!-- fr:journal kind=discovery scope=plan id=p1-r9a-blocks-migration created=2026-11-28T13:08:35+00:00 phase=1 -->
### p1-r9a-blocks-migration · discovery · fr migrate artifacts refuses the live spec 2026-11-27-triage-leaves-split (R9a.), so this repo's specs were not migrated (phase 1)

A read-only dry build of the 1 -> 2 rewrite over every live spec (fr.artifacts.spec_requirements_table.build)
rewrites 7 specs (this one included), stamps 3 (no list), and refuses one:
`docs/superpowers/specs/2026-11-27-triage-leaves-split-design.md:57: malformed requirement id 'R9a'
(expected `R` + a positive integer) — fix the requirement id in the spec, then re-run fr migrate artifacts --yes`.
Per P1.T5.S1 that spec belongs to another feature, so its requirements were not edited and
`fr migrate artifacts --yes` was not run: P1.T5.S1 is left unticked. Until the operator decides
(renumber R9a in that feature's branch, or land it first and re-run here), the spec kind is at 2
while this repo's specs are unstamped, so `fr validate artifacts` and the own-artifacts test
(`test_this_repos_own_artifacts_are_structurally_valid`) stay red, and the CLI-entry gate in this
workspace would migrate the other ten specs and then refuse every gated fr command over the R9a
spec. The executor's own gated fr commands ran with FR_SKIP_MIGRATION=1. The same R9a line, read
under R3, also fails `tests/unit/test_dispatch_lint_corpus.py::test_the_dispatch_gate_scores_zero_on_this_repos_own_plans`
(phase sizing now raises `line 57: malformed requirement id 'R9a'` instead of dropping the line), and
`test_migration_runner.py::test_this_repos_own_artifacts_plan_only_safe_actions` sees the pending spec
actions. All four clear once that spec's id is fixed and `fr migrate artifacts --yes` runs here.

<!-- fr:journal kind=discovery scope=plan id=p1-preview-cannot-show-refusal created=2026-11-28T13:08:35+00:00 phase=1 -->
### p1-preview-cannot-show-refusal · discovery · fr migrate artifacts (preview) lists a spec the rewrite will refuse as 'would migrate' (phase 1)

The dry run never calls a SchemaMigration's fn, and SchemaMigration has no `check` hook (only Repair
does), so the preview cannot show the R5 refusal; only `--yes` prints it. Verified over a tmp repo with
prose between requirements: the preview printed `would migrate`, and `--yes` printed
`FAILED: ... SpecRewriteRefusedError: <file>:7: prose between requirements — move the prose out of the
requirements list, then re-run fr migrate artifacts --yes`, leaving the file byte-identical.
`fr.artifacts.spec_requirements_table.build(path, text)` is the side-effect-free check a preview
could call.

<!-- fr:journal kind=decision scope=plan id=p1-lettered-ids-implemented created=2026-11-28T13:08:35+00:00 phase=1 -->
### p1-lettered-ids-implemented · decision · Lettered requirement ids (R9a) accepted per operator decision lettered-requirement-ids; P1.T5.S1 then ran (phase 1)

`fr.requirements` reads an id as `R[1-9][0-9]*[a-z]?` in list and table form (one `_ID_PATTERN` behind
`_ID_RE` and `_LIST_ITEM_RE`), orders ids with the new `requirement_order` (R9 < R9a < R9b < R10), and
still raises on `R9ab.`, `R09.`, `R9A.` and `R9-a.`. Phase sizing's `_ASK_RE` takes the letter; proportionality
used `int(r[1:])` to sort served asks, which would have crashed on R9a, and now uses `requirement_order`.
The stamp-2 validator and the migration's round trip go through the same reader. Prose names the optional
letter (fr-brainstorming §2, fr-brainstorming-and-plan explainer; both mirrors re-synced).
The CLI-entry gate had already migrated and committed the other ten live specs (9eeb5c8ef) during the
earlier blocked run; `fr migrate artifacts --yes` then converted 2026-11-27-triage-leaves-split (its R9a is
now a `| R9a | ... |` row), committed as `chore(fr): migrate artifacts`, and `fr validate artifacts`
reports all 227 artifacts valid.

<!-- fr:journal kind=discovery scope=plan id=p1-fast-tier-final created=2026-11-28T13:08:35+00:00 phase=1 -->
### p1-fast-tier-final · discovery · final fast tier: the four R9a-held tests are green; 5 environment failures and 3 worker crashes remain, none in this diff (phase 1)

`uv run pytest --fr-scope origin/main -n 2 -q --no-cov`: 8 failed, 12258 passed, 137 skipped.
Green now: test_this_repos_own_artifacts_are_structurally_valid,
test_this_repos_own_artifacts_plan_only_safe_actions, test_dispatch_lint_corpus, and the closed-world
runner tests. Still failing in the devcontainer, in paths this diff does not touch:
test_run_idle_guard::test_the_gh518_stop_is_blocked and test_isolation_decision_core's four
relative-PATH cases (`bash` not found under a stripped PATH). Three xdist worker crashes under the
container's 2 GB memory (test_run_evidence_separate_context, test_tripwire_own_artifacts,
test_tripwire_artifact_paths) pass when run alone (43 passed). One earlier run aborted on an xdist
INTERNALERROR and was rerun.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-28T13:08:35+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

the table reader reuses the existing _split_row/_is_row helpers and mirrors _legacy_rows; Task 2's refactor step reshaped the readers onto one (lines, first_line_no) signature

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-28T13:08:35+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the validator delegates to one new fr.requirements.table_form_problems, which reuses the reader's own regexes and _table_body; nothing duplicated to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-28T13:08:35+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

prose, mirrors, a scenario and acceptance rows; no code structure to refactor

<!-- fr:journal kind=review scope=plan id=review-p1-1 created=2026-11-28T14:17:00+00:00 phase=1 -->
### review-p1-1 · review · phase 1 code review (requesting-code-review): 5 in-scope findings p1-r1..p1-r5, all fixed (phase 1)

Independent reviewer (hard tier) over the phase-1 diff against spec R1-R8 and the
artifact-versioning migration discipline. Migration safety, round trip on every live
spec, CRLF, code-span pipes and imports all checked clean. Findings: has_requirements
raising inside sizing's handler (r1), silent table truncation on a broken row (r2) or a
missing delimiter row (r3), an id-like prefix matching prose (r4, spec R3 amended), and
proportionality hiding the cause (r5). All fixed in 5ecc797fa with tests.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-28T14:17:00+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · sizing calls has_requirements inside its except RequirementsError, and has_requirements can now raise (phase 1)

`fr.plan_review.sizing` (lines 93-97) calls `has_requirements()` in its `except RequirementsError`
clause, and `has_requirements` can now raise through `_rows`, so `fr plan self-review` crashes on a
section like `R1. a` / `R9ab. b` or on a table holding `| R1 | a | b |`.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-28T14:17:00+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · a table row missing an outer pipe silently ends the table and drops every later row (phase 1)

In `_table_body`, `| R1 | a |` / `| R2 | b` / `| R3 | c |` reads as [R1] alone and
`table_form_problems` is silent. Amended R2: the table ends only at a blank line or a line holding no
`|`; any other non-blank line in it that is not a whole row raises naming the line, and the validator
reports it.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-28T14:17:00+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · the line after the table header is skipped unchecked, so a missing delimiter row loses R1 (phase 1)

`_table_body` skipped line idx+1 without checking it, so a header followed straight by `| R1 | a |`
lost R1. A GFM delimiter row (cells of `:?-+:?`) is now required there, else a RequirementsError
naming the line; the validator reports it too.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-28T14:17:00+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · the id-like prefix matches ordinary prose such as `Rationale. ...` (phase 1)

`_ID_LIKE_RE = ^(?:[-*]\s+)?R\S*\.\s` matched `Rationale. ...` and `Rather. than`, so a prose-only
spec refused to migrate and the validator called the prose list form. Amended R3: a digit must follow
`R`.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-28T14:17:00+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · proportionality drops the reader's error and names only the table form (phase 1)

`fr.proportionality` (lines 186-187) reported "spec has no Requirements table; asks cannot be
counted" for any RequirementsError, losing the named line and cause, and named one form only.

<!-- fr:journal kind=discovery scope=plan id=p1-legacy-table-reader-unchanged created=2026-11-28T14:17:00+00:00 phase=1 -->
### p1-legacy-table-reader-unchanged · discovery · the pre-5.0 three-column table reader still skips the line after its header unchecked and ends at the first non-row (phase 1)

`fr.requirements._legacy_rows` has the p1-r2/p1-r3 shape (no delimiter check, a broken row ends the
table silently). It was left alone on purpose: it reads old, archived specs only, no live spec uses
it, and R2 keeps its meaning unchanged.

<!-- fr:journal kind=discovery scope=plan id=p1-review-fast-tier created=2026-11-28T14:17:00+00:00 phase=1 -->
### p1-review-fast-tier · discovery · fast tier after the review fixes: 9 failed, 12275 passed; none in this diff (phase 1)

`uv run pytest --fr-scope origin/main -n 2 -q --no-cov`: 9 failed, 12275 passed, 137 skipped. Five are
the devcontainer failures seen before (run_idle_guard, four isolation_decision_core relative-PATH
cases). Four pass when run alone (44 passed): three xdist worker crashes (test_run_suite_reuse,
test_tripwire_own_artifacts, test_tripwire_artifact_paths) and test_install_channels'
channel-switch case. `fr migrate artifacts --yes` changed nothing; `fr validate artifacts`: all valid.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-28T14:17:00+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: sizing calls has_requirements inside its except RequirementsError, and has_requirements can now raise (phase 1)

`has_requirements` returns True when `_rows` raises: something requirement-shaped but invalid still
counts, so sizing reaches its "does not parse" warning. Test:
tests/unit/test_plan_phase_sizing.py::test_an_invalid_requirement_shape_warns_instead_of_crashing (bad
id and three-cell row), plus the has_requirements assertion in
test_a_line_inside_the_table_that_is_not_a_whole_row_raises.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-28T14:17:00+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: a table row missing an outer pipe silently ends the table and drops every later row (phase 1)

`_table_body` now returns rows and problems; the table ends at a blank or pipe-less line and any other
line that is not a whole row is a problem that `_table_rows` raises and `table_form_problems` reports.
Tests: test_spec_requirements_list.py::test_a_line_inside_the_table_that_is_not_a_whole_row_raises
(replaces test_a_row_without_outer_pipes_ends_the_table), ::test_the_table_ends_at_a_blank_line_or_a_line_with_no_pipe,
test_validate_artifacts.py::test_a_stamped_spec_with_a_broken_row_inside_the_table_is_refused.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-28T14:17:00+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: the line after the table header is skipped unchecked, so a missing delimiter row loses R1 (phase 1)

`_is_delimiter` (every cell `:?-+:?`) is required on the line after the header, else a problem naming
that line. Tests: test_spec_requirements_list.py::test_a_header_without_a_delimiter_row_raises_naming_the_line,
::test_any_gfm_delimiter_row_is_accepted,
test_validate_artifacts.py::test_a_stamped_spec_whose_header_has_no_delimiter_row_is_refused.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-28T14:17:00+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: the id-like prefix matches ordinary prose such as `Rationale. ...` (phase 1)

`_ID_LIKE_RE` is now `^(?:[-*]\s+)?(R[0-9]\S*)\.\s`. Tests:
test_spec_requirements_list.py::test_prose_starting_with_an_r_word_is_not_id_like,
test_spec_requirements_table_migration.py::test_a_table_legacy_or_prose_only_section_is_only_stamped[r-word-prose],
test_validate_artifacts.py::test_a_stamped_table_spec_with_r_word_prose_is_valid; R0., R09., R9A., R9-a.
and R9ab. still raise (test_an_id_like_line_with_a_malformed_id_names_the_line).

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-28T14:17:00+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: proportionality drops the reader's error and names only the table form (phase 1)

The line is now "spec's Requirements do not parse (<error>); write an `| ID | Requirement |` table or
an `R<n>.` list; asks cannot be counted." Tests:
test_plan_proportionality.py::test_an_invalid_requirements_section_names_the_line_and_cause and the two
updated no-section / no-spec tests.
