# `fr acceptance set-status --drop-level`: removing stale evidence refs

- **Date:** 2026-09-26
- **Status:** designed
- **Origin:** gh#624 (found in the lean cost-aware pipeline's phase-2 review, p2-r25)
- **Goal:** the documented status transition covers evidence *removal* as well
  as addition, so re-pointing a row whose tests were deleted never needs a
  hand edit of `docs/acceptance/matrix.yaml`.

## 1. Problem

`fr acceptance set-status` (spec `2026-09-18-harness-parity-matrix-design.md`
§3.G.2) moves a row's status in place, records `--notes`, and can **add**
evidence with `--level <level>=<ref>`. It cannot remove a ref. The additive
behavior is deliberate (`fr.acceptance.edit.merge_levels`: "removing a ref stays
a deliberate edit, not something a status flip does silently"), but no verb
performs that deliberate edit. The only route is a hand edit of `matrix.yaml`,
which `.claude/rules/acceptance-matrix.md` forbids.

## 2. Design

### 2.A The flag

`--drop-level <level>=<ref>`, repeatable, on `set-status` only. Same grammar as
`--level`, parsed by `acceptance_cmd._parse_levels` (`acceptance_cmd.py:303`),
which gains a `flag` parameter so a malformed value names the flag the operator
actually typed (`--drop-level must be '<level>=<ref>'`), and exits 2. A ref
repeated in `--drop-level` within one call is deduplicated (dropped once), which
matches how `merge_levels` treats a repeated `--level` (`edit.py:137-140`).
`--notes` stays required: a drop is a status transition with a reason, like any
other.

### 2.B Refusals — all exit 2, all before any byte moves

1. **Absent ref.** A `--drop-level` ref that is not on the row under that level
   is refused and names the level and the ref. Dropping nothing is a typo, and
   a typo'd drop that "succeeded" would be a silent no-op. The matrix file and
   the three committed reports stay byte-identical.
2. **Unknown level key.** Refused, as `merge_levels` refuses one for additions.
3. **Contradiction.** The same `<level>=<ref>` in both `--level` and
   `--drop-level` in one call is refused (operator decision). It has no single
   reading.

Emptying a row's evidence while its status is `ci`/`scheduled` is **allowed**
(operator decision). The status is the operator's explicit call in the same
command, `--notes` records why, `set-status` has never judged status against
evidence, and `fr acceptance check` stays the gate.

### 2.C One rewrite, through the existing engine

`set-status` already routes through `fr.record.apply.apply_record` with a
one-entry `StepRecord`: one matrix rewrite (`fr.acceptance.edit.replace_row`),
all three committed reports regenerated (`render_committed_set`), one commit. The
drop joins that same pass. The row's new `levels` is the existing refs with the
drops removed, then the additions merged, so drop + add re-points a row in one
call.

**Carrier: CLI-only** (operator decision). The drops reach the engine through
`RecordTarget` (`apply.py:74-87`), the verb-only channel that already carries
`message`, `journal_scope` and the other verb targets. The new field is
`acceptance_drops: Mapping[str, Mapping[str, tuple[str, ...]]]` (row id → level →
refs), with an empty default (`field(default_factory=dict)`, since the dataclass is
frozen). Today `_acceptance_writes(record, overlay, repo_root)` (`apply.py:550`)
never sees the target. It gains a `drops` parameter, which `apply_record` passes
from `target.acceptance_drops`. In the move branch the row's levels become
`merge_levels(drop_levels(existing.levels, drops[id]), additions)`, so the drop
happens before the merge.

The engine refuses (`RecordRefusedError`, nothing written) three misalignments,
each of which would otherwise make a drop a silent no-op:
- a drop keyed by a row id that has no `AcceptanceItem` in the record;
- a drop keyed by an item that takes the create branch (a new row has nothing to
  drop);
- non-empty `acceptance_drops` passed together with a `run_id`, since a run path
  never reads verb targets. `AcceptanceItem`, the `record` artifact kind's shape, is **not**
changed: no record-kind stamp bump, no migration, and the release stays a patch.
The consequence, stated: a step record's `acceptance:` section still cannot drop
refs. It could not before either, and a step that needs a removal runs the verb.

The removal logic lives beside `merge_levels` in `fr/acceptance/edit.py` as
`drop_levels(existing, drops)`, raising `AcceptanceError` on an absent ref or an
unknown key. Both the engine and the CLI's pre-flight validation call it, so
they cannot disagree about what "on the row" means.

### 2.D Docs

`.claude/rules/acceptance-matrix.md` "How": the `set-status` bullet names
`--drop-level` and its refusal. That rule is mirrored to
`.opencode/instructions/acceptance-matrix.md` (`sync-opencode.py:63-64`
`REPO_LOCAL_ONLY_RULES`), so run `scripts/sync-opencode.py` and commit the
regenerated mirror, or `test_tripwire_opencode_instructions_sync.py` goes red.
Hermes excludes this rule (`sync-hermes.py:41-45`), so there is nothing to
regenerate there. Patch version bump (`scripts/bump-version.py patch`).

### 2.E Matrix row, same PR

The PR ships the surface that `lifecycle-acceptance-drop-level` waits on, so it
moves the row in the same PR, dogfooding the verb:
`fr acceptance set-status --id lifecycle-acceptance-drop-level --status ci
--level unit=super-fr:tests/unit/test_acceptance_set_status.py --notes "…"`.
That command regenerates all three reports.

## 3. Non-goals

- A `drop_levels` field in step records (see 2.C).
- Deleting or editing whole rows, or rewriting `origin`.
- Any status/evidence consistency judgement in `set-status`.

## Test Plan

Unit tests, in `tests/unit/test_acceptance_set_status.py`:

1. `--drop-level` removes the named ref, keeps the row's other refs, moves the
   status and notes, and regenerates the reports (a successful drop).
2. `--drop-level` of a ref not on the row exits 2, and `matrix.yaml` and every
   committed report are byte-identical afterwards.
3. `--drop-level` and `--level` in one call re-point the row: the old ref is
   gone, the new one present, one rewrite.
4. The same ref in both `--level` and `--drop-level` exits 2 with nothing changed.
5. An unknown level key in `--drop-level` exits 2 with nothing changed.
6. A malformed `--drop-level` value (no `=`) exits 2 and names `--drop-level`.
7. A drop that empties a `ci` row's evidence succeeds (d-empty-evidence).

Unit tests of the edit helper (no module tests `fr.acceptance.edit` directly
today), in `tests/unit/test_acceptance_set_status.py`:

8. `drop_levels` removes a ref and keeps the remaining refs in order, dedupes a
   repeated drop, and refuses an absent ref and an unknown key with
   `AcceptanceError`.

Unit tests of the engine, in `tests/unit/test_record_apply.py`:

9. `apply_record` given a `RecordTarget` whose `acceptance_drops` holds an absent
   ref raises `RecordRefusedError`, and `matrix.yaml` and the reports stay
   byte-identical.
10. `apply_record` refuses drops keyed by an id with no item, by a create-branch
    item, and drops passed together with a `run_id`.
