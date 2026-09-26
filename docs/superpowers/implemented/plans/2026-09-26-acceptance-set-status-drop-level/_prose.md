# acceptance set-status --drop-level (gh#624)

Three phases, bottom-up along the one write path:

1. **`drop_levels`** in `fr/acceptance/edit.py`: the removal twin of `merge_levels`. It is the single
   definition of "on the row" that both the CLI pre-flight and the engine use. This is the walking skeleton.
2. **Engine**: `RecordTarget.acceptance_drops`, a verb-only channel, reaches `_acceptance_writes`. Drops apply
   before the merge in the move branch. Misaligned drops are refused, never silently ignored. `AcceptanceItem`
   and the record kind stay at version 1 (spec d-carrier).
3. **CLI** `set-status --drop-level`, plus the rule doc, its OpenCode mirror, the matrix row moved to `ci` by
   the verb itself, and a patch bump.
