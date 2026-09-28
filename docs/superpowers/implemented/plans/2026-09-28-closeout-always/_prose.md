# Close-out is an always condition — keyed on the branch

Implements `docs/superpowers/specs/2026-09-28-closeout-always-design.md` (derio-net/super-fr#733).

## Shape

1. **Skeleton**: `branch_changed_paths` is lifted out of `branch_changes_present` so the two share
   one diff path. `fr.closeout.branch_artifacts` classifies what a branch touched, and the change
   fragment lands.
2. **`fr archive --branch <b>`**: resolves refs like verify-merge, refuses an unmerged or
   unresolvable branch, archives per kind, and prints `held:` lines instead of failing.
3. **`owed_artifacts`**: the one "live but its PR merged" predicate. `fr status` reports through
   it and `fr archive --all` moves through it; `archive_twin` learns the journal scopes so
   matrix refs survive the move.
4. **`fr pickup --branch`**: a single brief builder, with `fr pickup --run` as a caller that
   adds only its run extras (spec §D table).
5. **Skills**: fr-debugging, fr-execute (standalone), fr-isolation and fr-goal relay or name
   the branch close-out; both mirror generators run; a tripwire pins it.
6. **Sweep**: `fr archive --all` on this branch moves the owed set (the live debug journals
   and anything else `fr status` lists), checked against what `fr status` reported beforehand.

Phases 3 and 4 both depend only on 2. They run serially, 3 then 4, and never touch the same
files.

No phase names #733 as a `tracking_issue`, because the batch PR closes it.
