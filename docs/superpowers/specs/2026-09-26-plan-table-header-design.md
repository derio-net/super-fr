# fr plan create: create the Implementation Plans table and name its header

- **Date:** 2026-09-26
- **Status:** designed
- **Origin:** gh#603 (batch `plan-table-header`, triage-batches phase 4 live walk)
- **Journal:** `docs/superpowers/journals/specs/2026-09-26-plan-table-header.md`
- **Goal:** the first `fr plan create` against a spec succeeds, or fails once with
  an error that already contains the fix.

## 1. Problem

`fr plan create --spec <spec>` refuses a spec that lacks `## Implementation Plans`
with "Add the section (with a 4-column table header) before scaffolding plans" —
without saying which four columns. The operator then hand-writes a header, gets
the *mismatch* error (the only one that names `| Plan | Repo | File | Depends on |`),
and fixes it a second time. Two wasted round trips on every first run.
The two missing-section messages are `plan_ops.py` `_validate_spec_section` and
`_append_spec_row`; the no-table message is `_check_table_header`.

`migrate._ensure_spec_plan_row` already knows how to create the canonical section
for `fr migrate v1-to-v2`; `create` does not reuse it.

## 2. Decisions

| # | Decision |
|---|---|
| d1 | A spec with **no** `## Implementation Plans` section gets one, with the canonical header, appended by `create`. Pre-flight stays read-only: it accepts the spec, and the section is written together with the row, after the plan folder. |
| d2 | Every table error names the canonical header, from one constant: the mismatch error, and the "section present but no table" error. The missing-section error no longer exists on `create`'s path. |
| d3 | The header text has one definition in `plan_ops` (`_CANONICAL_HEADER_LINE` and its separator), used by `create` and by `migrate._ensure_spec_plan_row`, so the two cannot drift. |
| d4 | A section whose header is *mislabeled* is still refused, never rewritten (unchanged: the existing guard). |

## 3. Design

- `plan_ops.py`: add `_CANONICAL_HEADER_LINE = "| Plan | Repo | File | Depends on |"`,
  `_CANONICAL_HEADER_SEPARATOR`, and `_ensure_section_text(text) -> str` returning
  the text with the section appended when absent (same blank-line handling as
  today's migrate helper). `_validate_spec_section` returns quietly on a missing
  section (nothing to validate, `create` will add it). `_append_spec_row` calls
  `_ensure_section_text` before locating the table. The no-table error reads
  "…has no table to append to; add `<header>` and its separator row."
  The mismatch message keeps its wording but is built from the constant.
- `migrate.py`: `_ensure_spec_plan_row` uses `_ensure_section_text` instead of its
  own literal; behaviour is byte-identical.
- No artifact shape changes (spec text only) → no stamp bump or migration.

## 4. Test Plan

**In this PR:**

1. `create` on a spec with no `## Implementation Plans` section succeeds; the spec
   ends with the canonical header, separator and the plan's row, and a blank line
   separates it from the prior prose (with and without a trailing newline).
2. `create` on a spec whose section has no table raises `PlanEditError` whose
   message contains `| Plan | Repo | File | Depends on |`, leaving no plan folder.
3. The mismatch error still names the header and still leaves the spec untouched.
4. `migrate`'s section-creating helper output is unchanged (existing tests).

## 5. Non-goals

Rewriting a mislabeled header; creating the table when the heading exists with no
table (named, not created — the operator's prose under it is unknown).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
