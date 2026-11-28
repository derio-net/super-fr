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

<!-- fr:journal kind=review scope=plan id=review-lens-1 created=2026-11-28T15:50:24+00:00 -->
### review-lens-1 · review · lens review (docs-accuracy, errors, tests): 7 in-scope findings fixed, 1 out of scope

One reviewer per lens over the whole feature diff (merge base c4e69ecd0). errors: the
migration's one-size "fix the requirement id" hint and a malformed stamp-1 table refusing
instead of being stamped. docs-accuracy: a stale R9a docstring example and an explainer
overstating the rewrite. tests: three surviving mutations (sort-key tie, first prose line,
stamp >= 2) and unpinned migration edge cases. All fixed in 96e189712 with tests.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-28T15:50:24+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · the spec rewrite catches every RequirementsError and always says 'fix the requirement id'

`build()` in fr/artifacts/spec_requirements_table.py turned every reader error into the one hint
"fix the requirement id", and a stamp-1 spec already in table form but with a malformed row or
delimiter was refused instead of only stamped (R4), leaving the stamp-2 validator (R7) to name it.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-28T15:50:24+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · the migration module docstring gives R9a. as an id-like error, which is now a valid id

The docstring of fr.artifacts.spec_requirements_table (around line 22) named `R9a.` as the
example of a malformed id-like line; lettered ids are valid since decision lettered-requirement-ids.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-28T15:50:24+00:00 state=open review_scope=in -->
### l-docs-accuracy-r2 · finding [open] (reviewer: in scope) · the brainstorming-and-plan explainer says the list is rewritten, with no exception

docs/explainers/fr-brainstorming-and-plan.md (lines 125-126) said an older spec's list "is
rewritten" by `fr migrate artifacts --yes`, without saying that a spec the rewrite cannot convert is
left unchanged and the error names the line to fix.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-28T15:50:24+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · the lettered-order proportionality test passes by set-hash luck

test_plan_proportionality.py's lettered-order test served R9, R9a and R10 only, so a sort key on
the integer part alone could still pass; no two served ids tied on the number.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-28T15:50:24+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · the unconvertible-spec fixture has a single prose line

With one prose line between requirements the test cannot tell the first offending line from any
other; it must hold two and assert the FIRST is named.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-28T15:50:24+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · no test pins the validator's stamp >= 2

The stamp-2 form check runs at `stamp >= 2`; nothing failed if it were written `== 2`.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-28T15:50:24+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · migration edge layouts are untested

No test covered: a file with no final newline, a literal `\|` already in list text, a continuation
line equal to a table header, a requirement line inside a code fence, the round trip's
`except RequirementsError` branch, or mixed line endings.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5 created=2026-11-28T15:50:24+00:00 state=open review_scope=out -->
### l-tests-r5 · finding [open] (reviewer: out of scope) · the R8 prose test checks only that wording is present

test_spec_requirements_prose.py asserts that phrases appear in the skills; it cannot check that
the prose is correct.

<!-- fr:journal kind=discovery scope=plan id=l-fenced-requirement-pinned created=2026-11-28T15:50:24+00:00 -->
### l-fenced-requirement-pinned · discovery · a code fence inside the Requirements list is not special to the reader

Pinned rather than changed: a fence opening line after a blank line is prose between requirements,
so a list with a fenced `R2.` below `R1.` refuses to migrate at the fence line. Neither the reader
nor the rewrite tracks fences; a fenced requirement-shaped line directly after a requirement would
read as a continuation. No live spec does either.

<!-- fr:journal kind=discovery scope=plan id=l-fast-tier created=2026-11-28T15:50:24+00:00 -->
### l-fast-tier · discovery · fast tier after the lens fixes: 8 failed, 12287 passed; none in this diff

`uv run pytest --fr-scope origin/main -n 2 -q --no-cov`: 8 failed, 12287 passed, 137 skipped. Five are
the known devcontainer failures (run_idle_guard, four isolation_decision_core relative-PATH cases);
three are xdist worker crashes (test_skills_cmd smoke, test_tripwire_artifact_paths,
test_tripwire_own_artifacts) that pass alone (43 passed). `fr migrate artifacts --yes` changed nothing,
`fr validate artifacts` reports all 227 valid, `fr docs check`, ruff and mypy are clean.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-28T15:50:24+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: the spec rewrite catches every RequirementsError and always says 'fix the requirement id'

(a) New `fr.requirements.requirements_form` judges the section by its first requirement-shaped line;
`build()` returns None (stamp only) for anything but the list form, so a malformed table is stamped
with its body unchanged and `fr validate artifacts` then names the bad line. Test:
test_spec_requirements_table_migration.py::test_a_malformed_table_is_only_stamped_and_the_validator_names_the_row
(three cells, no delimiter, broken row). (b) Each list refusal gets its own fix text: malformed id,
repeated or out-of-order id, a table header inside the list (`table_header_line`), prose between
requirements, and a failed round trip. Test: ::test_an_unconvertible_spec_is_left_byte_identical_and_named
(prose-between, R9ab, out-of-order, header-in-list, fenced) and
::test_the_round_trip_parse_error_branch_refuses_with_the_join_fix.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-28T15:50:24+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: the migration module docstring gives R9a. as an id-like error, which is now a valid id

The docstring now names `R09.` as the malformed id, lists the header-inside-the-list refusal and the
per-cause fixes, and states that a table-form section (even a malformed one) is only stamped.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-28T15:50:24+00:00 state=fixed resolves=l-docs-accuracy-r2 -->
### l-docs-accuracy-r2-resolved · finding [fixed] · resolves l-docs-accuracy-r2: the brainstorming-and-plan explainer says the list is rewritten, with no exception

The explainer now says that a spec the rewrite cannot convert, for example with prose between two
requirements or a malformed id, is left unchanged, and the error names the line to fix. `fr docs check`
passes.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-28T15:50:24+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: the lettered-order proportionality test passes by set-hash luck

test_plan_proportionality.py::test_a_lettered_requirement_is_served_and_ordered now serves R9b, R10,
R9a and R9 and expects (R9, R9a, R9b, R10): R9a and R9b tie on the integer part, so only the letter
orders them.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-28T15:50:24+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: the unconvertible-spec fixture has a single prose line

The PROSE_BETWEEN fixture holds two prose paragraphs; the test asserts line 7 (the first) is named
and that the error names exactly one line.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-28T15:50:24+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: no test pins the validator's stamp >= 2

test_validate_artifacts.py::test_a_spec_stamped_past_two_is_still_refused_for_a_list_line: an
`fr_schema: 3` spec with a list line. `validate_spec` refuses the line ("stamped fr_schema 3"), and
through `fr validate artifacts` the stamp check alone reports it (version 3 is newer than this fr
and validation stops there); both are asserted.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-28T15:50:24+00:00 state=fixed resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [fixed] · resolves l-tests-r4: migration edge layouts are untested

test_spec_requirements_table_migration.py::test_edge_layouts_convert_exactly: no final newline (the
result keeps none: the last row carries no ending), a literal `\|` (written `\\|`, reads back
unchanged), mixed endings (pinned: the table takes the first requirement line's ending). The
header-as-continuation and fenced cases are in ::test_an_unconvertible_spec_is_left_byte_identical_and_named
(the fenced one pinned as a prose refusal), and the round trip's except branch in
::test_the_round_trip_parse_error_branch_refuses_with_the_join_fix.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5-resolved created=2026-11-28T15:50:24+00:00 state=open resolves=l-tests-r5 out_of_scope=true -->
### l-tests-r5-resolved · finding [out-of-scope] · resolves l-tests-r5: the R8 prose test checks only that wording is present

true of the R8 prose test by design: a prose requirement can only be checked by presence

<!-- fr:journal kind=decision scope=plan id=fold-multi-paragraph-impl created=2026-11-28T16:53:31+00:00 -->
### fold-multi-paragraph-impl · decision · fold multi-paragraph requirements into the cell (operator decision fold-multi-paragraph)

Everything after a requirement line, up to the next requirement or heading, belongs to that requirement. Paragraphs and bullet items are joined with a literal <br> (bullets kept) in the list reader and the table cell alike, so parse(list) == parse(table). Prose between requirements no longer refuses; a heading inside the list does (the table would drop its text). Malformed-id, ordering, header-in-list and round-trip refusals stay. ops-gate-truth and batch-silent-failures migrated with parsed requirements unchanged; 241 artifacts valid. Code aac58c6c6, specs fc5830835.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-28T17:56:10+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · a hash line inside a fenced or indented code block was read as a heading, splitting the fence (fold delta review) (phase 1)
