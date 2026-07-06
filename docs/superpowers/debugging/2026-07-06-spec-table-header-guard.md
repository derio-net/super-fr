# Debugging log: mislabeled `## Implementation Plans` table headers

**Date:** 2026-07-06

## Symptom & reproduction

Operator reported the `## Implementation Plans` table values "seem off" in
two proxmox-cluster specs:

- `docs/superpowers/implemented/specs/2026-07-05-omni-on-gondor-design.md`
- `docs/superpowers/specs/2026-07-05-provisioning-bootstrap-design.md`

Both render:

```
| Plan | Phases | Status | Created |
|------|--------|--------|---------|
| 2026-07-05-omni-on-gondor | `derio-homelab/proxmox-cluster` | `2026-07-05-omni-on-gondor` | — |
```

The header claims columns `Phases | Status | Created`, but the row actually
holds a repo string, the plan slug again, and a dash — nonsensical under
those labels. A sweep of super-fr's own `implemented/specs/` turned up the
same drift in milder form: several specs use `Plan | Target repo | Slug |
Status` instead of the canonical `Plan | Repo | File | Depends on` — the
mismatch is just less visually jarring there because the cell values happen
to still read plausibly.

## Evidence

- `packages/fr/src/fr/spec.py::parse_spec` parses the table **purely
  positionally** — it never reads header text, only checks `cells[0].lower()
  == "plan"` to skip the header/separator rows. Confirmed automation
  (`fr status`, archive sweep, etc.) is unaffected — this is a
  human-readability defect, not a functional break.
- `packages/fr/src/fr/plan_ops.py::_append_spec_row` writes
  `` | {plan_name} | `{repo}` | `{file}` | {depends_on} | `` into columns 2-4
  **unconditionally**, regardless of what the header above it says those
  columns mean.
- `_validate_spec_section` (the preflight `fr plan create` runs before
  touching the filesystem, #133) only checked that *some* pipe-delimited line
  followed the `## Implementation Plans` heading — never the header's column
  names.
- No `fr spec create` scaffold exists; specs are hand-authored (by whatever
  brainstorming/design flow produced them), so header text has no canonical
  source and drifts per spec.
- `rework_create` calls `_append_spec_row` directly, bypassing
  `_validate_spec_section` entirely — a second path with the same gap.

## Root cause

`fr plan create` (and `fr plan rework`) assume the `## Implementation Plans`
table header is `Plan | Repo | File | Depends on` when appending a row, but
never validate that assumption. A spec authored with any other header text
still accepts the append silently, because neither `_validate_spec_section`
nor `_append_spec_row` checked header content — only that a table existed.

## Fix

Added `_check_table_header` in `plan_ops.py`, a shared check (used by both
`_validate_spec_section` and `_append_spec_row`, closing both call paths)
that parses the first pipe-delimited line after the heading and requires its
cells to match `Plan | Repo | File | Depends on` (case-insensitive). A
mismatch raises `PlanEditError` with the exact expected header, failing
**before** any folder is created (preserving the #133 no-stranded-state
property) or, for `rework_create`, before the row is written.

Regression test:
`tests/unit/test_v2_plan_ops.py::test_create_rejects_spec_with_mislabeled_table_header`
— a spec with a `Phases | Status | Created` header now fails preflight with
no plan folder created and no row silently appended.

## Rejected approaches

- **Auto-normalize the header instead of failing.** Rewriting the header
  text without operator awareness risks silently editing prose the operator
  authored by hand in a design doc; a loud, actionable error is safer and
  matches the repo's stated preference for code-enforced guards over silent
  correction.
- **Repairing existing malformed specs in this PR.** Out of scope for a
  debugging fix — the two proxmox-cluster specs (and super-fr's own
  `Target repo | Slug | Status` specs) are pre-existing data, not the bug
  itself. A follow-up `fr repair` pass (or manual `git mv`-style edit) can fix
  the on-disk files once this guard prevents new drift.
