# A `local` acceptance status for repos with no CI

Issue: derio-net/super-fr#1453.

## Background

In a repo with no CI (`fr services` reports `ci none`), a row verified by a passing
automated test can only be `unwired`, which is debt (`fr.acceptance.model.DEBT_STATUSES`).
`deliver`'s leftover gate (`fr.record.pr_body.unaccounted`, `pr_body.py:507-524`) then
refuses the row as "neither gated nor tracked" and offers only a post-merge tester gate
whose reason ("why it waits for a live walk") is false. Under quiet placement
(`forge.issues: off`) the issue route is closed too, and `ci` (refused by
`fr.acceptance.ci.ci_reason` in such a repo) or `manual` misstate how the row is
verified. A repo with no CI cannot deliver even a unit-tested feature honestly.

Found on the quiet walk of spec `2026-11-04-repo-feature-settings` (Test Plan step 1),
fr `7.0.0-rc.5`. That run is held at `deliver` until this ships.

## Requirements

R1. A row may carry the status `local`: verified by an automated test that anyone can run
on any checkout, which no CI runs. A fresh `local` row is not debt. `fr acceptance
status`, `fr debt`, `fr status`'s open count, the acceptance report, the debt digest and
the triage board list `local` rows beside `walked` and `manual`, with their stamp date.

R2. Setting `local` requires at least one level ref (`unit`, `api`, `int`, `ui`). Every
level ref on the row must name a path in this repo (a `<repo>:` prefix naming another repo
is refused) and resolve to an existing file, and, for a Python anchor, to an existing
test. A resolution that is only a warning (an archived twin) does not count. Every writer
refuses otherwise, changing nothing: `fr acceptance add`, `fr acceptance set-status`,
`fr acceptance amend --op set-status`, and a step record's `acceptance:` entry.

R3. Setting `local` is refused, by every writer of R2, while the repo has CI
(`fr.acceptance.ci.ci_active`); the refusal names `ci` (or `unwired`) as the status to
use. A row already `local` in a repo that has CI counts as debt, shown as
`local, promote to ci`.

R4. `deliver` stamps every row whose effective status is `local` and that this run's
feature added or set to `local` (its row, or its `set-status` amendment, in the
feature's fragment). The stamp is `local: {at: <ISO date>, tree: <code tree>, log:
<witness>, files: {<path>: <git blob sha>}}`, one `files` entry per path the row's level
refs name, read from HEAD of the product checkout. `deliver` stamps only when its own
`tests` evidence is either:
- a fresh local suite log with no uncommitted code path (`tree` is then HEAD's code tree
  at stamp time), or
- a `tests: reuse` of a phase log (`tree` is then the tree the witness names).

A log fr could not observe being written (`unobserved=tests`) stamps exactly as `deliver`
accepts it today. Any other `tests` evidence, or a dirty code tree, refuses with exit 2,
naming each such row. The stamps are built and checked with the other refusals, written
only after `deliver`'s last refusal, and land in the same commit as the `deliver`
resolve. A refused resolve writes no stamp.

R5. A `local` row is stale when its stamp's `files` keys differ from the paths its
current level refs name, or when a file the stamp names is missing at HEAD, or when that
file's HEAD blob differs from the stamped one. Blob shas are compared, not commits, so a
squash merge does not make a row stale. A stale row, and a `local` row with no stamp,
counts as debt whatever its status, shown as `local, stale: <path>` or
`local, unstamped`. `fr acceptance check` reports each one (debt, exit 0, like every
other debt row). A later run re-earns the stamp by setting the row `local` again, which
clears the old stamp, and delivering.

R6. Under `ci none`, `deliver`'s leftover refusal for an owed row (`not-implemented`,
`unwired`, `walk-owed`) offers a runnable `fr acceptance set-status --id <row> --status
local --level unit=<repo>:<path>#<test> --notes "<which test verifies it>"` (with the
same `--feature` flag as the issue route) first, then the tester gate. Where the repo has
CI, the refusal is unchanged.

R7. The `acceptance-fragment` kind moves from 1 to 2 with a registered stamp-only
migration. Every fragment writer writes the registry's current version. The fragment
validator (`fr.artifacts.structure`) checks a `local` stamp's shape and refuses a stamp on
a row whose status is not `local`. No other kind changes shape. Step records' acceptance
`status` is a `StrictStr`, and records never carry a stamp.

R8. The acceptance rule (`.claude/rules/acceptance-matrix.md`), the `fr-acceptance`
skill, the consumer rule scaffold (`fr.acceptance.scaffold.RULE_TEMPLATE`) and every docs
page whose `covers:` names a changed path describe `local`. The frozen matrix header
`MATRIX_TEMPLATE`, which a migration writes, is not changed. The generated mirrors are
regenerated.

R9. A scenario, `tests/scenarios/acceptance-local-status.sh`, installs the candidate and
builds a fixture repo with no CI. It shows the refusal for a row with no level ref, a
fresh `local` row listed as non-debt by `fr acceptance status` and `fr debt`, and the row
reported as debt by `fr acceptance check` once its test file changes (stale) and when it
has no stamp (unstamped). The scenario writes the stamp itself, as `deliver` would. It
also shows that `local` is refused once the fixture declares CI. It covers rows
`acceptance-local-status-listed`, `acceptance-local-earned` and `acceptance-local-stale`.

## Design

### A. The status, its stamp and the fold

`fr.acceptance.model.Status` gains `"local"`. `LISTED_STATUSES` gains it; `DEBT_STATUSES`
does not. `Row` and the fragment's `SetStatus` amendment gain an optional
`local: LocalStamp | None = None`. `LocalStamp` is closed (`extra="forbid"`): `at`,
`tree`, `log`, `files` (a non-empty `dict[str, str]`).

In the fold (`fr.acceptance.fold.apply_amendment`), a `set-status` amendment to `local`
replaces the row's stamp with its own (`None` when it carries none, so an earlier stamp
never survives a re-set). A `set-status` to any other status drops the stamp.
`add-level` and `drop-level` leave the stamp alone; R5's key comparison then reports the
row stale.

`local_debt(rows, product_root, *, ci_active) -> dict[str, str]` in a new
`fr.acceptance.local` module is the one definition of why `local` rows are debt: row id →
`promote to ci` (R3), `unstamped` or `stale: <path>` (R5). It reads HEAD blobs of the
product checkout with one batched `git ls-tree -r HEAD -- <paths>`. Under quiet or stealth
the fold comes from the artifact root, while the blobs still come from `product_root`.

### B. Debt surfaces

Local debt counts beside `contested`. `is_debt(status, *, contested=False, local=None)`
treats a local-debt reason as debt. `fr.debt.model.DebtRow` gains `local_at` (the stamp
date) and `local_debt` (the reason). `DebtAcceptance` gains a `local_debt` count that
`debt_count` adds, as it adds `contested`, and the figures carry it, so
`fr.debt.render`'s digest figures and the triage board (`triage/render.py:1047-1058`)
count it. The surfaces that read it are:
- `fr.acceptance.check.open_rows`: the nag set, and `fr acceptance status`;
- `fr.debt.engine.acceptance_from_matrix`: `fr debt` and the digest;
- `status_cmd`'s open count (`fr status`);
- `fr.acceptance.report`: the `local` entries in its status, legend and count maps, plus
  the stamp date or the debt reason;
- `fr.gatebackfill.close`: a `local` row with a debt reason is not delivery evidence.

### C. Writers (R2, R3, R6)

`local_error(row, root) -> str | None` in `fr.acceptance.local` returns why `row` cannot
be set `local`: no level ref, a level ref into another repo, a ref that does not resolve
(a returning wrapper over `fr.acceptance.check._resolve_ref` and `_check_python_anchor`,
which report through a `CheckResult`; a warning counts as unresolved), or a repo with CI
(`ci_active(root)`). `add`, `set-status`, `amend` and `fr.record.apply`'s acceptance path
call it where they call `walked_error` today.

`fr.acceptance.edit.render_row_block` and `render_amendment_block` render `local:`.
`render_fragment` writes the registry's current `acceptance-fragment` version (it
hard-codes 1 today). A new `stamp_local(fragment_text, row_id, stamp)` rewrites, in
place, the row block or the latest pending `set-status` amendment block of `row_id`.

`unaccounted`'s row fix (R6) prepends the `local` command, with `--level` and
`_feature_flag`, when `ci_active(repo_root)` is false.

### D. Deliver (R4)

`run_cmd`'s `deliver` block gains `_deliver_local_stamp_plan(repo_root, state)`, right
after `_deliver_leftovers_gate`. It finds this feature's `local` rows in the feature
fragment (read where the placement keeps it: the artifact root). It reads the deliver
unit's verified `tests` witness and refuses on anything other than a fresh log or a
`reused:` witness. For a fresh log it refuses when `dirty_code_paths` is non-empty. It
builds the stamps in memory from the product checkout's HEAD (`code_tree`, `git ls-tree`),
and writes nothing.

The plan is applied by `_deliver_local_stamp_write` beside `_flush_gate_decisions`, after
`_refuse_missing_emits` and every other refusal. That call writes the fragment with
`fr.artifacts.atomic.write_text_atomic` and goes through `_remember`, so a `--record`
restore covers it. It then records the path with `_note_record_write`, so the write is
committed with the resolve, in the artifact root's checkout under quiet or stealth. Under
repo placement the fragment lives under `docs/acceptance/`, outside the code tree
(`fr.run.code_tree`), so the stamp does not move the tree the log covered.

### E. Artifact version (R7)

`acceptance-fragment` 1 → 2 in `fr.artifacts.registry`, a stamp-only `SchemaMigration`
registered through a module imported by `fr/artifacts/__init__.py`. The change adds a
status value and an optional field. A released `fr` (7.0.0-rc.x) refuses both on its
closed `Row` and `SetStatus` models, so it is a shape change. A hop-by-hop chain test for
the kind is added. This repo's own fragments are migrated with `fr migrate artifacts
--yes` in the same PR.

## Verification

strategy: candidate
gate: acceptance-local-held-quiet-walk=tester

- acceptance-local-deliver-stamp: none — `deliver`'s stamp needs a full run; unit tests drive `fr run resolve --step deliver` in process over a fixture repo with no CI, including quiet placement, a dirty tree and a refused resolve.
- acceptance-local-artifact-migration: none — the migration is proven by the hop-by-hop chain test and `fr validate artifacts` in CI.
- acceptance-local-held-quiet-walk: live — only the operator's held quiet-placement run, on a released candidate, shows a real repo with no CI delivering with `local` rows.

## Test Plan

1. post-merge — operator-driven: on a release candidate carrying this change, resume the
   held quiet-placement walk of spec `2026-11-04-repo-feature-settings` (Test Plan step 1).
   Set its unit-tested rows `local` and resolve `deliver`. Expected: `deliver` passes with
   those rows stamped, no tester gate added and no issue filed; `fr acceptance status` and
   `fr debt` list the rows as `local` and do not count them as debt.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-14-acceptance-local-status | `derio-net/super-fr` | `2026-11-14-acceptance-local-status` | — |
