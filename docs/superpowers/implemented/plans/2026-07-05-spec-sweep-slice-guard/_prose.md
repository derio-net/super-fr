# Spec-sweep slice guard — implementation

Fixes #351: a spec delivered in slices over-archives to `implemented/specs/`
every time any unrelated plan is archived, because all its `## Implementation
Plans` rows already resolve to archived locations and the sweep's only signal is
"all rows archived ⇒ spec done."

Design: `docs/superpowers/specs/2026-07-05-spec-sweep-slice-guard-design.md`.

## Approach

Two orthogonal changes in the `fr` package, plus docs + a version bump.

1. **Pending-slice rows (default fix).** A plan row whose File cell is a
   `pending`/`tbd` placeholder marks a decided-but-unbuilt slice. The shared
   `_spec_fully_implemented` (used by both `fr archive`'s `spec_archive_sweep`
   and `fr migrate dirs`) treats such a row as a hold — returning
   `(False, "row <name> pending — slice not yet built; …")` **before** any
   local/gh resolution, so the hold is deterministic, gh-independent, and
   carries a clear intentional note (today a `pending` cell blocks only
   accidentally via the misleading "unresolved locally (cross-repo?) — confirm
   and re-run" branch). Specs with no pending row sweep exactly as before.

2. **`--no-spec-sweep` flag (manual escape).** `fr archive … --no-spec-sweep`
   archives the plan(s) but skips the sweep for that one invocation.

## Phase map

- **Phase 1** — `--no-spec-sweep` flag (`archive_cmd.py`). Independent.
- **Phase 2** — pending-row hold (`migrate.py`): `_is_pending_placeholder`
  recognizer + the guard in `_spec_fully_implemented`, with unit + sweep +
  `migrate dirs` integration coverage. Independent of Phase 1.
- **Phase 3** — document the convention (docstrings) + patch version bump.
  Depends on Phases 1 and 2.

## TDD notes

Every behavior step is red-first against the current tree. The recognizer's
`\b` word boundary is pinned by a `pendingish → False` case. Determinism is
proven by asserting the gh client's `file_exists` is never reached on a
cross-repo pending row. The `no-pending-row → (True, None)` regression pins that
this is a pure superset — no existing archive behavior changes.

## Acceptance

- `archive-no-spec-sweep-flag` → flipped to `ci` in Phase 1 (test_archive_cmd).
- `spec-sweep-pending-slice-hold` → flipped to `ci` in Phase 2
  (test_v2_migrate). Both rows were born with the spec at brainstorm.
