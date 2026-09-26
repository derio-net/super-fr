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
| d1 | A spec with **no** `## Implementation Plans` section gets one, with the canonical header, appended by `create` only. Pre-flight stays read-only: `_validate_spec_section` accepts a missing section and writes nothing. `create` writes the section immediately before its `_append_spec_row` call (`plan_ops.py:273`), so it lands with the row, after the plan folder. |
| d2 | `_append_spec_row` stays strict: `rework` (`plan_ops.py:765`) keeps raising on a missing section, and its message names the header. Rework's behaviour is deliberately unchanged. |
| d3 | Every table error names the canonical header through one builder: the mismatch error, and BOTH no-table sites (`_check_table_header` `plan_ops.py:414` and `_append_spec_row` `:477`), plus the missing-section error `_append_spec_row` still raises for `rework`. |
| d4 | One header definition. `_CANONICAL_HEADER_LINE` is the source; `_CANONICAL_HEADER_CELLS` (`plan_ops.py:398`) is derived from it, and the separator row and every error text are built from it. `migrate._ensure_spec_plan_row` uses the same text helper. |
| d5 | A section whose header is *mislabeled* is still refused, never rewritten (unchanged). |

## 3. Design

- `plan_ops.py`: add `_CANONICAL_HEADER_LINE = "| Plan | Repo | File | Depends on |"`; derive
  `_CANONICAL_HEADER_CELLS` and `_CANONICAL_HEADER_SEPARATOR` from it; add
  `_ensure_section_text(text) -> str` (returns the text with the section appended when absent,
  same blank-line handling as today's migrate helper) and `_header_hint()` producing
  "expected `<header>` followed by its separator row" for all errors.
- `_validate_spec_section`: a missing section returns quietly; a present section is still checked.
- `create`: when the spec exists, rewrite it through `_ensure_section_text` right before
  `_append_spec_row`, then append the row. The spec path is already in `written` for staging.
- `_append_spec_row` and `_check_table_header`: all three raises use `_header_hint()`.
- `migrate.py`: `_ensure_spec_plan_row` uses `_ensure_section_text`; output byte-identical.
- No artifact shape changes (spec text only) → no stamp bump or migration.

## 4. Test Plan

**In this PR:**

1. `create` on a spec with no section succeeds: the spec ends with header, separator and the
   plan's row, blank-line separated from prior prose (with and without a trailing newline).
2. Pre-flight is read-only: `_validate_spec_section` on a section-less spec returns and leaves
   the file byte-identical.
3. Re-run: the plan folder already exists (matching) and the spec has no section: `create`
   finishes the job and adds section and row once (idempotent on a third run).
4. Section present, no table: `create` raises `PlanEditError` containing
   `| Plan | Repo | File | Depends on |`, no plan folder created; the same for the second
   no-table site in `_append_spec_row`.
5. Mismatch error still names the header and leaves the spec untouched.
6. `rework` on a section-less spec still raises, and the message names the header.
7. `migrate`'s section-creating helper output is unchanged (existing tests).

Acceptance matrix: new rows for items 1, 4 and 6 are added in this PR via
`fr acceptance add` (`ci` status), citing this spec.

## 5. Non-goals

Rewriting a mislabeled header; creating the table when the heading exists with no
table (named, not created — the operator's prose under it is unknown).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-26-plan-table-header | `derio-net/super-fr` | `2026-09-26-plan-table-header` | — |
