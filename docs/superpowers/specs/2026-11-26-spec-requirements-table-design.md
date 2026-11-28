---
fr_schema: 2
---
# Spec requirements as a table

## Background

A spec's `## Requirements` section is a plain list, one requirement per line (`R1. <text>`), with no
blank line between the lines (spec `2026-09-29-spec-is-the-contract-design.md` §B). CommonMark joins
consecutive lines into one paragraph, so every Markdown previewer (GitHub, IDE previews, the site
renderer) shows the whole section as one run-on block. The operator asked for the requirements to be
wrapped in a table.

What exists today:

- `fr.requirements` (`packages/fr/src/fr/requirements.py`) is the one parser. It reads the `R<n>.`
  list, optionally behind a `-`/`*` bullet, and a pre-5.0 three-column `| id | requirement | source |`
  table, whose `source` column it ignores. Its callers are `fr.plan_review.sizing` (phase sizing in
  self-review) and `fr.proportionality`; the PR body and visual evidence use its matrix helpers only.
- The list reader keeps only the `R<n>.` line itself; every other line is prose. Live specs wrap long
  requirements onto continuation lines (`2026-11-27-ci-hygiene-design.md` R1,
  `2026-11-27-isolation-gc-sweeper-design.md` R1–R3), so today every reader silently sees only the
  first line of such a requirement. A line with an id-like but malformed prefix
  (`2026-11-27-triage-leaves-split-design.md`'s `R9a.`) is silently dropped as prose. A pre-contract
  spec (`2026-06-11-bridge-dispatch-hardening-design.md`) holds prose and no requirement line at all.
- The `spec` artifact kind is at `current_version=1` (`fr.artifacts.registry`), its stamp is
  `fr_schema:` in the front matter (a file with no front matter gains a block holding only that key),
  no live spec carries one, and the kind has no pydantic model, so no model must accept the key.
  `fr.artifacts.structure.validate_spec` checks headings only.
- A `SchemaMigration` whose `fn` raises is that artifact's `FailedAction` and stays unstamped
  (`fr.artifacts.runner`); the CLI-entry gate then refuses every gated `fr` command over the
  half-migrated tree (`fr.artifacts.trigger`), and `validate-artifacts` stays red, since a refusing
  migration is not "migratable". `fr.artifacts.spec_test_plan_heading` is the precedent for a spec body
  rewrite that keeps line endings (`read_utf8`, `splitlines(keepends=True)`).
- `plugins/super-fr/skills/fr-brainstorming/SKILL.md` §2 tells authors to write the list. The
  fr-acceptance and fr-plan skills, `docs/explainers/fr-brainstorming-and-plan.md`,
  `docs/explainers/fr-acceptance.md`, `docs/explainers/01-fr-goal.md`, and the parser's docstring and
  error texts call it a list.
- GFM splits a table cell at every unescaped `|`, inside a code span too; a `\|` renders as `|` there
  (the GFM spec processes pipe escapes before inline parsing; other previewers not verified).
  Requirements here quote such text often (`rest | graphql`, `fixed | refuted | deferred`).

Any `fr` before this change, given a two-column table spec, finds no requirement: self-review silently
skips phase sizing and `fr plan proportionality` reports no Requirements list. Only
`fr validate artifacts` reads the stamp and refuses a file newer than itself. That is a shape change
(`.claude/rules/artifact-versioning.md`), so the kind moves to 2. The silent-skip window on a node
whose `fr` is older than its repo's specs is accepted: sizing is advisory, and the node's next update
closes it.

The second half of the operator's brief (simplifying fr-isolation by leaning on the harnesses) is out
of scope here; it gets its own brainstorm on its own branch.

## Requirements

| ID | Requirement |
|----|-------------|
| R1 | A spec's `## Requirements` section may be a two-column GFM table whose header row is `\| ID \| Requirement \|` (case-insensitive), followed by the delimiter row and one row per requirement: the id in the first cell, the text in the second. An id is `R<n>` (`n` from 1, no leading zero), optionally followed by one lowercase letter (`R9a`), which inserts a requirement without renumbering. Every row starts and ends with `\|`, and `\\|` inside a cell is a literal `\|`. |
| R2 | `fr.requirements` reads that table to the same ids and text as the equivalent `R<n>.` list, and raises `RequirementsError` naming the line for a table row that does not hold exactly two cells, a header not followed by a delimiter row, or a non-blank line inside the table that is not a whole row (the table ends at a blank line or a line holding no `\|`). It still reads the pre-5.0 three-column table and the `R<n>.` list, so archived and unmigrated specs keep their meaning. |
| R3 | In the `R<n>.` list, everything after a requirement line up to the next requirement line, the next heading or the end of the section is part of that requirement. Lines directly after it are continuation lines, joined to its text with single spaces; a blank line starts a new paragraph of the same requirement. Paragraphs are joined with `<br>`, and a paragraph's bullet items (`- ` or `* `) each start on a new `<br>` with the bullet kept. Blank lines before the first requirement and after the last one's text belong to no requirement; text before the first requirement line is prose. A line that starts like a requirement id (an optional `-`/`*` bullet, then `R` and a digit, then any non-space characters, then `. `) but whose id is not an R1 id raises `RequirementsError` naming the line. |
| R4 | The `spec` kind moves from version 1 to 2. Its 1 → 2 migration rewrites a live spec's `R<n>.` list into the R1 table, one row per requirement with continuation lines joined and each `\|` escaped as `\\|`. It keeps every line outside the requirement and continuation lines as it was, adds one blank line before and after the table where none is, keeps the file's line endings, and the runner adds the front-matter stamp. A spec whose section is already a two-column table, is a pre-5.0 table, holds no requirement line, or has no `## Requirements` section is only stamped. |
| R5 | The rewrite round-trips: the requirements parsed from the rewritten spec equal, id for id and text for text, those parsed from the original. A spec the rewrite cannot convert under that rule (a `RequirementsError` or a failed round trip) is left byte-identical and unstamped, and its failure names the file, the line and the cause, and gives the hand fix: fix the id, or join the lines. Every other spec still migrates. |
| R6 | Archived specs are never located, rewritten or stamped. |
| R7 | `fr validate artifacts` refuses a spec stamped 2 or later whose `## Requirements` section holds an `R<n>.` list line, or whose `\| ID \| Requirement \|` table has a row with other than two cells, naming the line. A pre-5.0 three-column table is not refused. |
| R8 | The fr-brainstorming skill tells spec authors to write the R1 table, with front matter `fr_schema: 2`, and to escape `\|` as `\\|`. The fr-acceptance and fr-plan skills, their OpenCode and Hermes mirrors, the `fr-brainstorming-and-plan`, `fr-acceptance` and `01-fr-goal` explainers, and `fr.requirements`' docstring and error texts describe the table (the errors name both forms). |

## Design

- **Reader (R1–R3).** `fr.requirements` gains `_table_rows`: find a row whose cells, lowercased, are
  `["id", "requirement"]`, skip the delimiter row, read rows until the first line `_is_row` rejects,
  through the existing `_split_row`; a row of other than two cells raises with its line number (the
  legacy reader keeps its own loop). `_list_rows` gains continuation joining and the id-like-prefix
  check (`^(?:[-*]\s+)?R\S*\.\s`). `_rows` tries the legacy table, then the two-column table, then the
  list. `parse_requirements`' id checks apply unchanged to every form. A new
  `list_layout(spec_text)` returns, for the list form, each requirement's line span and any prose line
  between requirements, for the rewrite to use; the parser and the rewrite share it, so they cannot
  disagree on which lines belong to a requirement.
- **Rewrite (R4–R6).** New module `fr.artifacts.spec_requirements_table` registers a
  `SchemaMigration` spec 1 → 2, imported by `fr/artifacts/__init__.py`. Its `fn` reads with
  `read_utf8` and `splitlines(keepends=True)`, takes the layout, and builds the new text in memory: the
  lines before the first requirement, a blank line where needed, the header, the delimiter and one row
  per requirement (each ending in the section's own line ending), a blank line where needed, then the
  lines after the last requirement. Before writing it raises, with the R5 message, on a
  `RequirementsError`, or when `parse_requirements` of the built text differs from
  that of the original. Then one `write_text_atomic`. A body already in table form (or a legacy table,
  or no requirement line, or no section) is left alone, so the runner only writes the stamp; this also
  covers the crash window between body and stamp. The locator is the kind's own
  (`repo_glob("spec", "*.md")`), which never reaches `docs/superpowers/implemented/`.
- **Consequences of a refusal (R5).** One unconvertible spec makes the CLI-entry gate refuse every
  gated `fr` command in that repo until it is fixed by hand, and keeps `validate-artifacts` red; this
  is the gate's standing behaviour over a half-migrated tree, and the R5 message is what makes it
  recoverable. In every workspace that runs `fr` after the release, the gate also rewrites the live
  specs of in-flight runs on that branch, so two branches holding the same live spec can conflict on its
  `## Requirements` section; merging the base and re-running `fr migrate artifacts --yes` resolves it,
  because a table body is only stamped.
- **Validator (R7).** `validate_spec` reads the stamp through a function-local import of the
  registry's `_read_spec_stamp` (as it already imports `fr.spec` locally), since the registry imports
  `structure` at module load. At 2 or later it runs the section through the reader's line classifier
  and reports each `R<n>.` list line and each two-column-table row of other than two cells. A file at 1
  is not checked for the form: it is stale, and the migration owns it.
- **Prose (R8).** Edit the canonical skills and the three explainers (or bump the `reviewed` stamp
  where a page stays true); run `scripts/sync-opencode.py` and `scripts/sync-hermes.py`.
- **This repo.** The PR runs `fr migrate artifacts --yes`, which rewrites the live specs here,
  including this one (written in the list form because the `fr` that resolves its brainstorm cannot read
  the table yet). `2026-11-27-triage-leaves-split-design.md`'s `R9a.` refuses under R3 if that spec is
  still live when this PR migrates; its owner decides the renumbering, and this PR does not edit
  another feature's requirements.

## Design shape

```text
packages/fr/src/fr/
  requirements.py                      ~ _table_rows, continuation joining, id-prefix check,
                                         list_layout, docstring + errors name both forms      (R1–R3, R8)
  artifacts/
    registry.py                        ~ spec current_version 1 → 2                           (R4)
    spec_requirements_table.py         + SchemaMigration spec 1→2: list → table, round-trip   (R4–R6)
    __init__.py                        ~ import the new module
    structure.py                       ~ validate_spec: v2 refuses list lines, bad cell counts (R7)
plugins/super-fr/skills/
  fr-brainstorming/SKILL.md            ~ §2: write the table, fr_schema: 2, escape |          (R8)
  fr-acceptance/SKILL.md, fr-plan/SKILL.md  ~ "list" → "table"                                (R8)
.opencode/skills/…, .hermes/skills/…   ~ regenerated mirrors                                   (R8)
docs/explainers/
  fr-brainstorming-and-plan.md, fr-acceptance.md, 01-fr-goal.md  ~ table wording; reviewed     (R8)
docs/superpowers/specs/*.md            ~ migrated: stamped 2, lists rewritten to tables        (R4)
tests/unit/
  test_spec_requirements_list.py       ~ table form, continuation lines, id-prefix refusal    (R1–R3)
  test_spec_requirements_table_migration.py  + rewrite, stamp-only cases, refusals, CRLF      (R4–R6)
  test_validate_artifacts.py           ~ v2 refusals; legacy table accepted                    (R7)
  test_spec_requirements_prose.py      + pins the skills' table wording                        (R8)
tests/scenarios/spec-requirements-table.sh  + candidate walk                                   (R4, R5)
tests/integration/test_scenarios.py   ~ the scenario's test
.changes/feat-spec-requirements-table.yaml  + bump: minor

  before:  ## Requirements          after:  ## Requirements
           R1. text a                       
           that wraps                       | ID | Requirement |
           R2. b `x | y`                    |----|-------------|
                                            | R1 | text a that wraps |
                                            | R2 | b `x \| y` |
```

## Verification

strategy: candidate
- spec-requirements-table-read: none — unit tests in this PR's CI parse the table, the list (with continuation lines) and the legacy table to the same requirements and pin the skill wording
- spec-requirements-table-valid: none — unit tests in this PR's CI run `fr validate artifacts` over stamped specs with a list line, with a three-cell row and with a legacy table

## Test Plan

- pre-merge — CI: `tests/unit/test_spec_requirements_list.py` parses a two-column table, the equivalent list and the legacy three-column table to equal `Requirements`, with `\|` read as `|`; raises naming the line for a three-cell row, a row without outer pipes and an `R9a.` line; joins continuation lines; and raises the existing id errors for the table form (row `spec-requirements-table-read`).
- pre-merge — CI: `tests/unit/test_spec_requirements_table_migration.py` rewrites a list spec (including wrapped requirements and a CRLF file) to the table, keeps every other line and the line endings, and stamps it; only stamps a table spec, a legacy-table spec, a prose-only section and a spec with no section; folds a multi-paragraph requirement (paragraphs and bullets) into its cell with `<br>`; leaves byte-identical, and reports with file, line, cause and hand fix, a spec with a malformed id such as `R09.` and one whose round trip fails; never locates an archived spec; and reaches 2 from 1 hop by hop (row `spec-requirements-table-migrate`).
- pre-merge — CI: `fr validate artifacts` refuses a spec stamped 2 with an `R<n>.` line and one with a three-cell row, naming the line, and accepts a valid table spec and a stamped legacy-table spec (row `spec-requirements-table-valid`).
- pre-merge — CI: `tests/unit/test_spec_requirements_prose.py` pins the fr-brainstorming §2 table wording, and the mirror tripwires stay green (row `spec-requirements-table-read`).
- pre-merge — candidate: `tests/scenarios/spec-requirements-table.sh` installs the branch through `.fr/candidate-install`, migrates a fixture repo holding a list spec with a wrapped requirement, and checks that the spec is now a stamped table, that the installed `fr`'s `fr.requirements` reads it to the same ids and joined text as before, and that `fr validate artifacts` passes on it (row `spec-requirements-table-migrate`).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-26-spec-requirements-table | `derio-net/super-fr` | `2026-11-26-spec-requirements-table` | — |
