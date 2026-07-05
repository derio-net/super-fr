# fr repair quiet on pending-slice rows — promote the recognizer to fr.refs

**Status:** Approved (fr-goal batched Q&A, 2026-07-05) — ready for `fr-plan`.
**Date:** 2026-07-05
**Issue:** derio-net/super-fr#359 (follow-up to #351, shipped in #358 / v3.8.2)
**Repos affected:** `derio-net/super-fr` only (the `fr` CLI).

## Problem

#351 taught `fr archive`'s spec sweep and `fr migrate dirs` to honor a
`pending`/`tbd` File-cell placeholder as a decided-but-unbuilt slice (they hold
the spec — correct). But the **repair-in-passing** step (`repair_repo` in
`packages/fr/src/fr/repair.py`), which runs after every archive to normalize
refs, does **not** recognize the convention. `refs.plan_slug("pending")` returns
`"pending"` (a non-empty token), so `_repair_spec_table` skips the empty-slug
guard, tries to resolve it as a plan, fails, and emits on every archive:

```
warning: <spec>.md: File cell (row 'Slice B') '`pending`' does not resolve — tried:
  …/plans/pending, …/implemented/plans/pending, …/archived-plans/pending.
  Left untouched; if this is a cross-repo row, run `fr repair` in its own repo.
```

Harmless (the cell is left untouched, the spec is still correctly held) but
**noisy and misleading** — it nags on a deliberate placeholder and points at a
cross-repo repair that doesn't apply. It undercuts the clean-note UX #351 aimed
for. Verified live in the #351 post-merge smoke test.

Root cause: three surfaces reason about "is this File cell a pending
placeholder?" but only two (archive sweep, migrate dirs) share the recognizer;
repair has no notion of it.

## Design

### 1. Promote the recognizer to `fr.refs` (single canonical classifier)

`#351` put `_is_pending_placeholder` (regex `^(pending|tbd)(\s|$)`,
case-insensitive) in `fr.migrate`. Move it — plus its regex — to `fr.refs` as a
**public** `is_pending_placeholder(cell: str) -> bool`, sitting beside
`plan_slug` and the existing `_PLACEHOLDERS = ("—", "-", "")` tuple (the natural
home: `refs` is where "classify this File cell" already lives, and it imports
neither `migrate` nor `repair`, so there is no coupling or cycle).

- `fr.migrate` keeps a thin alias `_is_pending_placeholder =
  refs.is_pending_placeholder` so its existing internal callers and
  `tests/unit/test_v2_migrate.py::test_is_pending_placeholder` (which imports
  `from fr.migrate import _is_pending_placeholder`) resolve unchanged. The
  duplicated regex constant is removed from `migrate.py`.
- Behavior is byte-for-byte identical to the shipped recognizer — this arm is a
  pure move, no logic change.

### 2. Skip pending cells in `_repair_spec_table`

In `packages/fr/src/fr/repair.py::_repair_spec_table`, after the header/separator
skip and **before** `refs.plan_slug(file_cell)` / `resolve_plan_ref`, insert:

```python
if refs.is_pending_placeholder(file_cell):
    continue  # intentional pending-slice placeholder (#351/#359) — not a ref
```

Effect: a `pending`/`tbd` row is left untouched **without** a warning or a
rewrite — exactly as archive/migrate already treat it. No other repair path
changes: `_repair_meta_refs` handles `_meta.yaml` `spec`/`plan` fields, which are
never placeholder tokens, so it needs no guard.

## Out of scope

- No change to the hold behavior itself (#351 shipped that).
- No change to what counts as a pending placeholder (same regex, now shared).
- No new frontmatter / status parsing.

## Acceptance

One new row (born here, presented at spec review):

- **`repair-quiet-on-pending`** — `fr repair` / repair-in-passing leaves a
  `pending`/`tbd` placeholder row untouched and emits **no** unresolved-ref
  warning. _Business claim: the pending-slice convention is quiet and
  consistent across all three surfaces (sweep, migrate, repair) — the operator
  never sees a spurious nag on an intentional placeholder. Verifiable at unit
  level over `repair_repo`; not an implementation detail (it's the UX the
  convention promises)._

## Verification

Pure internal `fr` code, no deployment — proven by unit tests
(`repair_repo` emits no warning + no rewrite for a pending row; the promoted
`refs.is_pending_placeholder` keeps the shipped recognizer's contract; the
`fr.migrate` alias still resolves). No post-merge Test Plan; a one-line local
smoke (re-run an archive over a sliced spec, confirm the warning is gone)
suffices at close-out.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-07-05-repair-skip-pending-359 | `derio-net/super-fr` | `2026-07-05-repair-skip-pending-359` | — |
