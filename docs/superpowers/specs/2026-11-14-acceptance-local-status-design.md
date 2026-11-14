# A `local` acceptance status for repos with no CI

Issue: derio-net/super-fr#1453.

## Background

In a repo with no CI (`fr services` reports `ci none`), a row verified by a passing
automated test can only be `unwired`, which is debt (`fr.acceptance.model.DEBT_STATUSES`).
`deliver`'s leftover gate (`fr.record.pr_body.unaccounted`, `pr_body.py:508-524`) then
refuses the row as "neither gated nor tracked" and offers only a post-merge tester gate
whose reason ("why it waits for a live walk") is false. Under quiet placement
(`forge.issues: off`) the issue route is closed too, and `ci` (refused by
`fr.acceptance.ci.ci_reason` in such a repo) or `manual` misstate how the row is
verified. A repo with no CI cannot deliver even a unit-tested feature honestly.

Found on the quiet walk of spec `2026-11-04-repo-feature-settings` (Test Plan step 1),
fr `7.0.0-rc.5`. That run is held at `deliver` until this ships.

## Requirements

R1. A row may carry the status `local`: verified by an automated test that anyone can run
on any checkout, which no CI runs. `local` is not a debt status. `fr acceptance status`,
`fr debt`, the acceptance report, the debt digest and the triage board list `local` rows
beside `walked` and `manual`, with their stamp date.

R2. Setting `local` requires at least one level ref (`unit`, `api`, `int`, `ui`), and every
level ref on the row must resolve to an existing file and, for a Python anchor, an
existing test. Every writer refuses otherwise, changing nothing: `fr acceptance add`,
`fr acceptance set-status`, `fr acceptance amend --op set-status`, and a step record's
`acceptance:` entry.

R3. Setting `local` is refused, by every writer of R2, while the repo has CI
(`fr.acceptance.ci.ci_active`); the refusal names `ci` (or `unwired`) as the status to
use. A row already `local` in a repo that has CI counts as debt, shown as
`local, promote to ci`.

R4. `deliver` stamps every row whose effective status is `local` and that this run's
feature added or set to `local` (its row, or its `set-status` amendment, in the
feature's fragment). The stamp is `local: {at: <ISO date>, tree: <code tree>, log:
<witness>, files: {<path>: <git blob sha>}}`, one `files` entry per path the row's level
refs name, read at HEAD. `deliver` stamps only when its own `tests` evidence is a
verified local suite log or a `tests: reuse` of one. Otherwise it refuses, exit 2, naming
each such row, before any write. The stamp lands in the same commit as the `deliver`
resolve.

R5. A `local` row is stale when a file its stamp names is missing or its blob differs
from the stamped one. Blob shas are compared, not commits, so a squash merge does not
make a row stale. A stale row, and a `local` row with no stamp, counts as debt whatever
its status, shown as `local, stale: <path>` or `local, unstamped`. `fr acceptance check`
reports each one (debt, exit 0, like every other debt row). A later run re-earns the
stamp by setting the row `local` again and delivering.

R6. Under `ci none`, `deliver`'s leftover refusal for an owed row (`not-implemented`,
`unwired`, `walk-owed`) offers `fr acceptance set-status --id <row> --status local
--notes "<which test verifies it>"` first, then the tester gate. Where the repo has CI,
the refusal is unchanged.

R7. The `acceptance-fragment` kind moves from 1 to 2 and the `record` kind from 12 to 13,
each with a registered stamp-only migration. `fr.artifacts.structure`'s fragment
validator checks a `local` stamp's shape and refuses a stamp on a row whose status is not
`local`.

R8. The acceptance rule (`.claude/rules/acceptance-matrix.md`), the `fr-acceptance`
skill, the acceptance scaffold's status comment and every docs page whose `covers:`
names a changed path describe `local`. The generated mirrors are regenerated.

## Design

### A. The status and its stamp

`fr.acceptance.model.Status` gains `"local"`. `LISTED_STATUSES` gains it; `DEBT_STATUSES`
does not. `Row` and the fragment's `SetStatus` amendment gain an optional
`local: LocalStamp | None = None`. `LocalStamp` is closed (`extra="forbid"`): `at`,
`tree`, `log`, `files` (a non-empty `dict[str, str]`). The fold
(`fr.acceptance.fold`) carries a `set-status` amendment's stamp onto the row, and drops
the row's stamp when an amendment moves the status away from `local`.

`local_debt(row, root, *, ci_active) -> str | None` beside `walked_error` in
`fr.acceptance.model` is the one definition of why a `local` row is debt: `promote to ci`
(R3), `unstamped`, or `stale: <path>` (R5); `None` otherwise. It reads blob shas through
`git ls-files -s`/`git hash-object` on the working tree. `is_debt` takes the reason, the
way it takes `contested` today, so every surface that counts debt (`open_rows`, `fr debt`,
the digest, the report, the triage board) counts it from one place.

### B. Writers (R2, R3)

`local_error(row, root) -> str | None` returns why `row` cannot be set `local`: no level
ref, a ref that does not resolve (reusing `fr.acceptance.check`'s `_resolve_ref` and
`_check_python_anchor`), or a repo with CI (`ci_reason(root) is None`). `add`,
`set-status`, `amend` and `fr.record.apply`'s acceptance path call it where they call
`walked_error` today.

### C. Deliver (R4, R6)

A new `_deliver_local_stamp(repo_root, state)` runs in `run_cmd`'s `deliver` block after
`_deliver_leftovers_gate` and before `_deliver_pr_gate`. It finds this feature's `local`
rows in the feature fragment, reads the deliver unit's verified `tests` witness (a log
witness, or a `reused:` one), refuses on anything else, and builds the stamps in memory.
It writes them with `fr.artifacts.atomic.write_text_atomic` only after every refusal has
been checked, and adds the fragment to the resolve's pending commit paths. The fragment
lives under `docs/acceptance/`, outside the code tree, so the stamp does not move the
tree the log covered.

`unaccounted`'s row fix (R6) prepends the `local` command when `ci_active(repo_root)` is
false.

### D. Artifact versions (R7)

`acceptance-fragment` 1 → 2 and `record` 12 → 13 in `fr.artifacts.registry`, each a
stamp-only `SchemaMigration` registered through a module imported by
`fr/artifacts/__init__.py`. The change adds a status value and an optional field, and a
released `fr` (7.0.0-rc.x) refuses both on its closed models, so it is a shape change.
The hop-by-hop chain tests for both kinds are extended. This repo's own fragments and
records are migrated with `fr migrate artifacts --yes` in the same PR.

## Verification

strategy: candidate
gate: acceptance-local-held-quiet-walk=tester

- acceptance-local-deliver-stamp: none — `deliver`'s stamp needs a full run; unit tests drive `fr run resolve --step deliver` in process over a fixture repo with no CI.
- acceptance-local-artifact-migration: none — the migration chain is proven by the hop-by-hop chain tests and `fr validate artifacts` in CI.
- acceptance-local-held-quiet-walk: live — only the operator's held quiet-placement run, on a released candidate, shows a real repo with no CI delivering with `local` rows.

## Test Plan

1. post-merge — operator-driven: on a release candidate carrying this change, resume the
   held quiet-placement walk of spec `2026-11-04-repo-feature-settings` (Test Plan step 1).
   Set its unit-tested rows `local` and resolve `deliver`. Expected: `deliver` passes with
   those rows stamped, no tester gate added and no issue filed; `fr acceptance status` and
   `fr debt` list the rows as `local` and do not count them as debt.
