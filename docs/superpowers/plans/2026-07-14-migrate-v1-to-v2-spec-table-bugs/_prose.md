# fr migrate v1-to-v2: spec-table bugs, staging, UX — implementation

Fixes #379: four independent gaps in `fr migrate v1-to-v2` and its read/write
neighbors, bundled as one issue / one PR because they all touch
`packages/fr/src/fr/migrate.py` and `packages/fr/src/fr/spec.py`.

Design: `docs/superpowers/specs/2026-07-14-migrate-v1-to-v2-spec-table-bugs-design.md`.
Every design decision (including an explicit operator correction on Bug 2's
fix approach, and deliberate scope cuts on Bugs 1 and 3) is final and recorded
there — this plan does not reopen any of it.

## Phase map

- **Phase 1** — trivial: the in-progress skip message names
  `--include-in-progress` (UX Gap 1).
- **Phase 2** — `fr spec status` (`spec.py`) stops silently dropping
  malformed `## Implementation Plans` rows. `SpecMeta` gains a `warnings`
  field; `parse_spec` fires a warning (never guesses the row's data) on any
  non-4-column data row, while still correctly ignoring header/separator
  lines of any width (a not-yet-migrated 5-column table's header line is not
  itself a "malformed row"). `compute_status` threads `spec.warnings` into
  `SpecStatus.warnings`, which `render_status_md` already prints.
- **Phase 3** — `fr migrate v1-to-v2` (`migrate.py`) creates the spec's
  `## Implementation Plans` table when it's entirely absent (true of every
  v1 spec), scoped deliberately: it never touches a spec that already has a
  table (even one missing this particular plan's row) — that's a follow-up
  if it turns out to matter, not this fix. Reuses `plan_ops._append_spec_row`
  / `plan_ops._SPEC_TABLE_HEADER_RE` — the exact machinery `fr plan create`
  already uses to keep spec-row shape consistent everywhere.
- **Phase 4** — `fr migrate v1-to-v2` git-stages what it creates/moves: the
  archive `.md` → `.md.v1-archive` move (and the `--force` reverse move)
  become `git mv` with a fallback to a plain move when the source isn't a
  tracked file inside a real git repo (keeps ~30 existing non-git-init test
  fixtures behaving exactly as before); newly created `_meta.yaml`,
  `_prose.md`, `NN.yaml` get `git add`-staged via the same best-effort
  `plan_ops._stage` helper `fr plan create` already uses. Depends on Phase 3
  because both touch the tail of `_migrate_one`.
- **Phase 5** — patch bump + full gate (lint, typecheck, full pytest incl.
  the coverage gate, acceptance nag).

## TDD notes

Every phase is red → green (→ optional refactor). Phase 2's ordering fix
(header/separator skip before the column-count check) gets its own
dedicated red/green pair (Task 2) rather than being folded into Task 1,
because it's a distinct, independently-checkable claim: a legacy 5-column
table's *header* line must never itself read as a malformed data row.

Phase 3 is careful about scope: `_ensure_spec_plan_row` is a no-op the
moment any `## Implementation Plans` section already exists, regardless of
its column count or whether it happens to be missing a row for the plan
being migrated right now. This is tested explicitly (byte-identical text
after a no-op call) so a future change can't accidentally widen the scope
without a test catching it.

Phase 4's biggest risk is regressing the ~30 existing `test_v2_migrate.py`
fixtures that never `git init` their `tmp_path`. `_git_mv_best_effort`'s
fallback path is exercised by every one of those unchanged; the new
git-backed assertions live in dedicated fixtures that explicitly `git init`
+ commit first, so the two code paths (tracked vs. untracked) both have
direct test coverage rather than one being incidentally covered by the
other's tests.

## Out of scope (see spec for full reasoning)

- Backfilling a row into an existing-but-incomplete spec table.
- Staging `_rewrite_spec_table`'s edits to an already-tracked spec file
  (modification, not new/deleted content — not the specific mess #379
  complains about).
- Any change to `fr repair`'s `_repair_spec_table_header` /
  `_repair_spec_table` — both already correct and tested; Bug 2's fix is
  read-side (`parse_spec`), not a repair-path change.
