# fr repair quiet on pending-slice rows — implementation

Fixes #359 (follow-up to #351). `repair_repo`'s ref normalization warns on every
archive that a `pending`/`tbd` File-cell placeholder "does not resolve" —
noisy and misleading, because that placeholder is the intentional
decided-but-unbuilt-slice marker #351 introduced.

Design: `docs/superpowers/specs/2026-07-05-repair-skip-pending-359-design.md`.
Operator chose (batched Q&A): promote the recognizer to `fr.refs`.

## Phase map

- **Phase 1** — move `_is_pending_placeholder` (regex included) from
  `fr.migrate` to `fr.refs` as public `is_pending_placeholder`, beside
  `plan_slug`/`_PLACEHOLDERS`. `fr.migrate` keeps a thin alias so its callers
  and tests are unchanged. Behavior-preserving move.
- **Phase 2** — `_repair_spec_table` skips a pending cell before resolving it:
  no warning, no rewrite, cell left untouched (as archive/migrate already do).
  Flips acceptance `repair-quiet-on-pending` to `ci`.
- **Phase 3** — patch bump (3.8.2 → 3.8.3) + full gate.

## TDD notes

Phase 1's move is guarded on both ends: a new `test_refs.py` recognizer test
(same contract, incl. the `pending-cleanup`/`pendingish` word-boundary cases
from #351's review) plus the existing `test_v2_migrate.py` import/behaviour
tests, which must stay green through the alias. Phase 2's test asserts the
absence of a warning and a rewrite for a pending row — red on baseline (which
emits "does not resolve"), green after the guard.

## Why refs, not migrate

`fr.refs` is where "classify this File cell" already lives (`plan_slug`,
`resolve_plan_ref`, `_PLACEHOLDERS`) and it imports neither `migrate` nor
`repair` — so the recognizer becomes the single canonical classifier all three
surfaces share, with no cross-module coupling or cycle risk.
