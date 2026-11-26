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
  table, whose `source` column it ignores. Readers: phase sizing, `fr.proportionality`, `fr.plan_ops`,
  visual evidence and the PR body.
- The `spec` artifact kind is at `current_version=1` (`fr.artifacts.registry`), its stamp is
  `fr_schema:` in the front matter, and no live spec in this repo carries one (unstamped is version 1).
  `fr.artifacts.structure.validate_spec` checks headings only.
- `fr.artifacts.spec_test_plan_heading` is the precedent for a spec body rewrite (a `Repair`); this
  change moves the shape, so it is a `SchemaMigration`.
- `plugins/super-fr/skills/fr-brainstorming/SKILL.md` §2 tells authors to write the list;
  `fr-acceptance/SKILL.md` calls it a list; `docs/explainers/fr-brainstorming-and-plan.md` describes it.
- GFM splits a table cell at every unescaped `|`, inside a code span too. Requirements in this repo
  quote such text often (`rest | graphql`, `fixed | refuted | deferred`).

An `fr` at 9.0.0 or older, reading a two-column table, finds no requirement and fails phase sizing.
That is a shape change (`.claude/rules/artifact-versioning.md`): the kind moves to 2, so the old
reader refuses the file as newer than itself instead of misreading it.

The second half of the operator's brief (simplifying fr-isolation by leaning on the harnesses) is out
of scope here; it gets its own brainstorm on its own branch.

## Requirements

R1. A spec's `## Requirements` section may be a two-column GFM table whose header row is `| ID | Requirement |` (case-insensitive), followed by the delimiter row and one row per requirement: the id in the first cell, the text in the second. `\|` inside a cell is a literal `|`.
R2. `fr.requirements` reads that table to the same ids and text as the equivalent `R<n>.` list. It still reads the `R<n>.` list and the pre-5.0 three-column table, so archived specs and unmigrated files keep their meaning.
R3. The `spec` kind moves from version 1 to 2. Its 1 → 2 migration rewrites a live spec's `R<n>.` list into the R1 table, escaping each `|` in the text, and leaves every other byte of the spec as it was. A spec whose section is already a two-column table, is a pre-5.0 table, or has no `## Requirements` section is only stamped.
R4. The rewrite round-trips: the requirements parsed from the rewritten spec equal, id for id and text for text, those parsed from the original. A spec the rewrite cannot convert under that rule (prose lines between requirement lines, a parse error, or a failed round trip) is left byte-identical, unstamped, and reported by name as that one artifact's failure while the others migrate.
R5. Archived specs are never located, rewritten or stamped.
R6. `fr validate artifacts` refuses a spec stamped 2 or later whose `## Requirements` section holds an `R<n>.` list line, or whose table has a row with other than two cells (an unescaped `|` in the text), naming the line.
R7. The fr-brainstorming skill tells spec authors to write the R1 table, with front matter `fr_schema: 2`, and to escape `|` as `\|`. Its OpenCode and Hermes mirrors, the fr-acceptance skill's wording and the `fr-brainstorming-and-plan` explainer say the same.

## Design

- **Reader (R1, R2).** `fr.requirements` gains `_table_rows`: find a row whose cells, lowercased, are
  `["id", "requirement"]`, skip the delimiter row, read rows until the first non-row line, through the
  existing `_split_row`. `_rows` tries the legacy table, then the two-column table, then the list.
  `parse_requirements`'s id checks apply unchanged to every form.
- **Rewrite (R3, R4, R5).** New module `fr.artifacts.spec_requirements_table` registers a
  `SchemaMigration` spec 1 → 2. Its `fn` reads the file as text, locates the section with the parser's
  own `_locate_section`, and builds the new body in memory: the section's leading prose, a blank line,
  the table (`| R<n> | <text with | as \|> |`), a blank line, then the section's trailing lines. It
  refuses (raises, so the runner reports it) before writing when a prose line sits between two
  requirement lines, when `parse_requirements` fails on the original, or when parsing the built body
  does not give the original `Requirements`. Then one `write_text_atomic`. A body already in table form
  (or a legacy table, or no section) is left alone: the runner writes the stamp, which covers the crash
  window between body and stamp. The locator is the kind's own (`repo_glob("spec", "*.md")`), which
  never reaches `docs/superpowers/implemented/`.
- **Validator (R6).** `validate_spec` reads the stamp; at 2 or later it runs the section through the
  reader's line classifier and reports each `R<n>.` list line and each table row whose cell count is not
  two, by line number. A file at 1 is not checked for the form (it is stale, and the migration owns it).
- **Prose (R7).** Edit the canonical skills and the explainer; run `scripts/sync-opencode.py` and
  `scripts/sync-hermes.py`; bump the explainer's `reviewed` stamp.
- **This repo.** The PR runs `fr migrate artifacts --yes`, which rewrites the live specs here,
  including this one (written in the list form because the `fr` that resolves its brainstorm cannot read
  the table yet).

## Design shape

```text
packages/fr/src/fr/
  requirements.py                      ~ + _table_rows; _rows tries legacy → table → list   (R1, R2)
  artifacts/
    registry.py                        ~ spec current_version 1 → 2                           (R3)
    spec_requirements_table.py         + SchemaMigration spec 1→2: list → table, round-trip  (R3–R5)
    __init__.py                        ~ import the new module
    structure.py                       ~ validate_spec: v2 refuses list lines, bad cell counts (R6)
plugins/super-fr/skills/
  fr-brainstorming/SKILL.md            ~ §2: write the table, fr_schema: 2, escape |          (R7)
  fr-acceptance/SKILL.md               ~ "list" → "table"                                      (R7)
.opencode/skills/…, .hermes/skills/…   ~ regenerated mirrors                                   (R7)
docs/explainers/fr-brainstorming-and-plan.md  ~ describes the table; reviewed stamp           (R7)
docs/superpowers/specs/*.md            ~ migrated: stamped 2, lists rewritten to tables        (R3)

  before:  ## Requirements          after:  ## Requirements
           R1. text a                       | ID | Requirement |
           R2. b `x | y`                    |----|-------------|
                                            | R1 | text a |
                                            | R2 | b `x \| y` |
```

## Verification

strategy: candidate
- spec-requirements-table-read: none — unit tests in this PR's CI parse the table, the list and the legacy table to the same requirements and pin the skill wording
- spec-requirements-table-valid: none — unit tests in this PR's CI run `fr validate artifacts` over stamped specs with a list line and with a three-cell row

## Test Plan

- pre-merge — CI: `tests/unit/test_requirements.py` parses a two-column table, the equivalent list and the legacy three-column table to equal `Requirements`, with `\|` read as `|`, and the existing id errors raised for the table form (row `spec-requirements-table-read`).
- pre-merge — CI: a test of the migration rewrites a list spec to the table and stamps it; stamps without rewriting a table spec, a legacy-table spec and a spec with no section; leaves byte-identical and reports a spec with prose between requirement lines and one whose round trip fails; and never locates an archived spec (row `spec-requirements-table-migrate`).
- pre-merge — CI: `fr validate artifacts` refuses a spec stamped 2 with an `R<n>.` line and one with a three-cell row, naming the line, and accepts a valid one (row `spec-requirements-table-valid`).
- pre-merge — CI: the skill-text test pins the fr-brainstorming §2 wording and the mirrors stay in sync (row `spec-requirements-table-read`).
- pre-merge — candidate: the scenario installs the branch through `.fr/candidate-install`, migrates a fixture repo holding a list spec, and checks that the spec is now a stamped table, that the installed `fr`'s `fr.requirements` reads it to the same ids and text as before, and that `fr validate artifacts` passes on it (row `spec-requirements-table-migrate`).

## Implementation Plans
