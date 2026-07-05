# Spec-sweep slice guard — pending-slice rows hold a spec in place

**Status:** Approved (fr-goal batched Q&A, 2026-07-05) — ready for `fr-plan`.
**Date:** 2026-07-05
**Issue:** derio-net/super-fr#351
**Repos affected:** `derio-net/super-fr` only (the `fr` CLI). Downstream
fr-enabled repos benefit after they reinstall `fr`; no code changes there.

## Problem

A spec delivered in **slices**: slice A ships and its plan(s) archive; slice B
is decided and pending but has **no plan folder yet** (none is created until
that build starts). Because every row in the spec's `## Implementation Plans`
table now resolves to an archive location, `fr archive`'s spec sweep concludes
"spec done" and moves the spec to `implemented/specs/` — **every single time any
unrelated plan is archived**. The operator has to `git mv` it back after each
close-out. Observed downstream, reproduced 3× (#351).

Root cause: `fr.migrate._spec_fully_implemented` — shared by `spec_archive_sweep`
(`fr archive`) and `fr migrate dirs` — has one signal: "every plan row resolves
to an archive ⇒ spec complete." It cannot see an intra-spec slice that has no
row yet.

### Why the obvious fixes don't fit this repo

The issue floated a frontmatter `status:` allowlist ("only sweep shipped-like
statuses"). **super-fr specs have no YAML frontmatter** — they carry a free-form
`**Status:**` line whose real values include `Draft`, `Approved`, `design`,
`Seed spec …`. super-fr's own specs were archived while their status still read
`Draft`/`Approved`, so a *positive* "shipped-like status required to sweep"
allowlist would break the common case. The safe direction is a **negative
guard**: an explicit hold signal that leaves the spec in place. A false-positive
hold costs one manual `git mv`; a false-positive archive is today's recurring
bug — the asymmetry dictates biasing toward *hold*.

## Design

Two orthogonal changes, both in the `fr` package.

### 1. Pending-slice rows (the default fix)

Establish a convention: **when a slice is decided but unbuilt, add a row for it
to the spec's `## Implementation Plans` table with a recognized pending
placeholder in the File cell.** The sweep treats such a row as a hold.
Illustration (the `## Implementation Plans` table of a two-slice spec):

```text
Plan     | Repo        | File            | Depends on
-------- | ----------- | --------------- | ----------
Slice A  | derio-net/x | 2026-07-01-a/   | —           ← archived
Slice B  | derio-net/x | pending         | —           ← holds the spec
```

**Recognition** (`fr.migrate`, new helper `_is_pending_placeholder`): the File
cell is a pending placeholder when, after the existing cell normalization
(backticks/whitespace stripped by `parse_spec`), its first token is `pending` or
`tbd`, case-insensitively — so `pending`, `` `pending` ``, `TBD`, and
`pending — no plan yet` all qualify. A real plan cell (`—`, a date-slug, a
`docs/superpowers/plans/…` path) never does.

**Behavior in `_spec_fully_implemented`**: after the existing manual-row skip
(`file in ("—", "-")`) and **before** local/remote resolution, a pending
placeholder returns `(False, "row <name> pending — slice not yet built; leaving
spec in place")`.

Note the honest scope: a `pending` cell **already** blocks the sweep today —
but only *accidentally*, falling through to the "unresolved locally
(cross-repo?) — confirm and re-run" branch (verified empirically:
`(False, "…unresolved locally (cross-repo?)…")`). That note reads like an error
and tells the operator to "confirm and re-run" — the opposite of the truth
("this is intentional; leave it"). So the change is not "make it block"; it is
**(1)** make the pending-row convention first-class and documented so operators
actually add the row (the observed bug is caused by *omitting* it — with no row,
the sweep returns `(True, None)` and wrongly archives), **(2)** replace the
misleading note with a clear "pending slice" one, and **(3)** recognize it
deterministically, bypassing the gh probe. Concretely the hold becomes:

- **deterministic** — never reaches the gh contents probe, so it holds
  identically offline, during a gh outage, and for cross-repo `owner/repo`
  cells (today a `pending` cross-repo cell blocks only *accidentally*, via the
  gh-dependent "unresolved locally" branch);
- **intentional** — a clear "pending slice" note instead of the misleading
  "unresolved locally (cross-repo?) — confirm and re-run".

The note surfaces through both callers' existing note channels
(`spec_archive_sweep` prints `note: …`; `plan_dirs_migration` collects it), so
the hold is **never silent** — it matches the "never a silent pass" ethos the
sweep already follows. Because `_spec_fully_implemented` is shared, `fr migrate
dirs` inherits the guard for free.

Specs with **no** pending row are unaffected — all-rows-archived still sweeps
exactly as before. This is a pure superset; no existing archive behavior
changes.

### 2. `--no-spec-sweep` flag (the manual escape)

`fr archive [<plan> | --all] --no-spec-sweep` archives the plan(s) and skips the
spec sweep entirely for that invocation. Orthogonal to the per-spec hold — the
belt-and-suspenders escape for "archive this plan and touch nothing else."
Implemented in `archive_command` (`fr.commands.archive_cmd`): the flag gates the
`if archived or all_plans:` sweep block; when skipped, echo `(spec sweep
skipped)`. `--force`/`--all` interactions are unchanged; repair-in-passing still
runs on archived plans.

## Out of scope

- No YAML frontmatter for specs, no `**Status:**` word-scanning, no
  `archive: hold` marker. The pending-row convention is the single hold signal
  (operator decision, batched Q&A).
- No auto-insertion of pending rows. The operator adds the row when the slice is
  decided; the tool only recognizes it.
- No change to the per-plan archive gate (`archive_gate`) or to how plans move.

## Test Plan

Post-merge, operator-driven (proves the real-world acceptance the unit tests
simulate):

1. Reinstall `fr` from the new release (`scripts/install.sh` or
   `uv tool install --force`); confirm `fr --version` reports the bumped number.
2. In the affected downstream fr-enabled repo, add a `pending` row for the
   decided slice B to its sliced spec's `## Implementation Plans` table (one
   line), commit.
3. Run an **unrelated** `fr archive <some-other-plan>` close-out.
4. Assert the sliced spec **stays** in `docs/superpowers/specs/` (previously it
   moved to `implemented/specs/` on every archive, forcing a manual `git mv`
   back).
5. Sanity: `fr archive <plan> --no-spec-sweep` archives the plan and prints
   `(spec sweep skipped)`, leaving all specs untouched.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-07-05-spec-sweep-slice-guard | `derio-net/super-fr` | `2026-07-05-spec-sweep-slice-guard` | — |

_(Single slice, built in one plan; the row points at the active plan folder and
resolves to `implemented/plans/` when the plan archives at close-out.)_
