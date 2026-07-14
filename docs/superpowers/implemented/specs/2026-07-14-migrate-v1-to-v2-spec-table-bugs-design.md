# fr migrate v1-to-v2: spec-table creation, loud parse warnings, git staging, UX hint

**Status:** Approved (fr-goal batched Q&A, earlier conversation) — ready for `fr-plan`.
**Date:** 2026-07-14
**Issue:** derio-net/super-fr#379
**Repos affected:** `derio-net/super-fr` only (the `fr` CLI: `packages/fr/src/fr/migrate.py`,
`packages/fr/src/fr/spec.py`, and their shared write-helpers in `packages/fr/src/fr/plan_ops.py`).

## Problem

Four independent gaps in `fr migrate v1-to-v2` and its read/write neighbors,
verified against current code and bundled as one issue / one PR because they
all touch the same two files:

1. **Migration never creates the `## Implementation Plans` table.**
   `_rewrite_spec_table` (`migrate.py` ~665) only rewrites an *existing*
   table (drops the legacy `Status` column, rewrites `.md` File cells to
   `/`). Every v1 spec that predates the section entirely is a no-op — the
   migrated repo still has no table, and `fr spec status` has nothing to
   walk.
2. **`fr spec status` silently drops malformed table rows.** `parse_spec`
   (`spec.py` ~94) does `if len(cells) != 4: continue` — any row that isn't
   exactly 4 cells (most commonly a pre-migrate 5-column `Status` row)
   vanishes with zero trace, in output or in `SpecStatus.warnings`.
3. **Migration doesn't git-stage what it creates or removes.** `_meta.yaml`,
   `_prose.md`, `NN.yaml`, and the `.v1-archive` backup are all untracked
   after a run; the `.md` deletion isn't staged as part of a rename either
   (`shutil.move` — git sees a delete + an untracked file, not a rename).
   `git status` afterward is a mess the operator has to hand-fix.
4. **Skip message doesn't mention the escape hatch.** The in-progress skip
   reason gives no hint that `--include-in-progress` exists.

## Design

### 1. Create the spec table when absent (Bug 1)

Scope: **only** the "section entirely absent" case. When a spec already has
an `## Implementation Plans` section — 5-column legacy or 4-column — it
already has whatever rows its v1 author hand-wrote (that's the existing,
working case exercised by `test_migrate_rewrites_spec_table_drops_status_column`
et al.); `_rewrite_spec_table` continues to be the only thing that touches
it (column-drop + File-cell rewrite). Appending a second row for a plan that
already has one there is the failure mode to avoid, so this fix does not
attempt to reconcile "table exists but is missing a row for this plan" —
out of scope, noted below.

New helper in `migrate.py`, called once per successfully-migrated plan from
inside `_migrate_one` (not from the per-spec-file sweep in `migrate_repo`,
which has no plan context) — right before the function's final `return`,
using the same `v1plan.spec` value already written verbatim into
`meta["spec"]` at line 273:

```python
def _resolve_spec_file(spec_ref: str | None, repo_root: Path) -> Path | None:
    """Resolve a v1 plan's raw `**Spec:**` value to a spec file on disk.

    v1's value is whatever was written between backticks — usually a
    repo-relative path (`docs/superpowers/specs/<slug>.md`), occasionally a
    bare slug once a repo is already partway migrated. Cross-repo notation
    (`owner/repo:path`) can't be resolved locally — the file lives in
    another repo's checkout. Returns None when unresolvable so the caller
    can report *why* it couldn't ensure the row, not silently skip.
    """

def _ensure_spec_plan_row(spec_path: Path, *, slug: str, target_repo: str) -> str | None:
    """If spec_path has no `## Implementation Plans` section, create the
    canonical 4-column header and append a row for `slug`. No-op (returns
    None) when the section already exists. Returns a warning string on
    failure, else None.
    """
```

`_ensure_spec_plan_row` reuses the existing write machinery rather than
reinventing table-append logic:
- If `plan_ops._SPEC_TABLE_HEADER_RE` doesn't match, write
  `\n## Implementation Plans\n\n| Plan | Repo | File | Depends on |\n|------|------|------|------------|\n`
  at EOF (normalizing trailing-newline count first) — the exact header
  `_check_table_header` already treats as canonical.
- Then delegate to `plan_ops._append_spec_row(spec_path, plan_name=slug,
  repo=target_repo, file=slug, depends_on="—")` — the same call
  `plan_ops.create()` makes for `fr plan create`, so the row shape (bare
  canonical slug, backticked repo/file, idempotent re-run) is identical
  everywhere a row gets appended in this codebase.
- A `PlanEditError` from `_append_spec_row` here would only happen if the
  header we just wrote somehow doesn't match canonical — defensive, not
  expected to fire; caught and surfaced as a migration warning rather than
  raised, so one spec's header oddity doesn't abort the whole sweep.
- On success, stage the write via `plan_ops._stage(repo_root, [spec_path])`
  (best-effort `git add`, already used by `create()` for the same file) —
  this is new content, and Bug 3's git-status goal covers it naturally.

`_migrate_one` calls `_resolve_spec_file(v1plan.spec, repo_root)`; when it
resolves, calls `_ensure_spec_plan_row` and appends any returned warning to
the plan's `MigrationOutcome.warnings` (that field already exists for
exactly this class of non-fatal diagnostic — see the `_extract_prose_depends_on`
precedent). When `v1plan.spec` is set but doesn't resolve to a file on disk,
append a warning naming the unresolved value instead of silently doing
nothing — this is a real "couldn't do the thing" case, not a no-op.

**Out of scope, noted per operator instruction:** backfilling a row into an
*existing* table when this particular plan isn't in it yet. If that turns
out to be a real gap in practice, it's a follow-up issue — the risk of
mis-detecting "already has a row for this slug" across the mixed 4/5-column
legacy formats and duplicating rows outweighs the benefit of guessing here.

### 2. Loud (non-fatal) warning on malformed spec-table rows (Bug 2)

**Operator correction overriding the issue's own "Option A" suggestion:**
do not accept 3-column rows as `Plan | Repo | File` with a guessed
dependency default. Fail loud, don't guess.

`SpecMeta` gains a `warnings: tuple[str, ...] = ()` field (frozen dataclass,
default-safe — both call sites already use keyword construction). In
`parse_spec` (`spec.py` ~94), restructure the row loop so the header/separator
skip happens **before** the column-count check (a pre-migrate 5-column
header must not be flagged as a malformed *data* row — that's `fr migrate
v1-to-v2`'s job, not a warning-worthy row), then warn on anything left that
isn't exactly 4 columns:

```python
first = cells[0] if cells else ""
if first.lower() == "plan" or (first and set(first) <= {"-", " "}):
    continue  # header / separator, any column count
if len(cells) != 4:
    warnings.append(
        f"{spec_path.name}: row {stripped!r} has {len(cells)} columns, "
        f"expected 4 (Plan | Repo | File | Depends on) — skipped. If this "
        f"spec predates the v2 migration, run `fr migrate v1-to-v2`."
    )
    continue
```

The malformed row's data is never parsed or guessed at — just named and
skipped, mirroring the write-side's existing fail-loud posture in
`plan_ops._check_table_header` (raises on a differently-labeled 4-column
header). This is the read-side's non-fatal equivalent: `fr spec status`
must not abort a whole spec over one bad row, but it must not go silent
either.

A **same-column-count-but-differently-labeled** header (e.g. a hand-authored
`Phases | Status | Created`) is already handled by `fr repair`'s
`_repair_spec_table_header` — confirmed live and covered by
`tests/unit/test_repair.py` — so this fix does not duplicate that path; the
new warning only fires on wrong *column count*, matching the distinction
`repair.py`'s own docstring draws.

`compute_status` seeds its local `warnings` list from `spec.warnings` before
its own diagnostics are appended, so a bad row and (e.g.) a cross-repo
resolution failure both surface in `SpecStatus.warnings` — and therefore in
`render_status_md`'s output and the `fr spec status` CLI, which already
prints `status.warnings` (no CLI change needed).

### 3. Git-stage what migration creates/moves (Bug 3)

Reuses the `git mv` pattern from `migrate_dirs` (~888) but adds a fallback:
`migrate_dirs`'s tests `git init` their tmp_path fixtures and hard-fail via
`MigrationError` on a `git mv` failure — appropriate there because that verb
only ever runs against a real, already-tracked repo. `migrate v1-to-v2`'s
existing unit-test suite (34 call sites of `_make_repo` in
`test_v2_migrate.py`) does **not** `git init` its fixtures, and retrofitting
all of them just to make `git mv` succeed is disproportionate to a staging
fix. Instead:

```python
def _git_mv_best_effort(repo_root: Path, src: Path, dst: Path) -> None:
    """Move src -> dst via `git mv` (staged rename, history preserved) when
    src is a tracked file inside a real git working tree; falls back to a
    plain filesystem move otherwise (untracked fixture, no .git at all,
    git not on PATH). The fallback preserves pre-existing migrate_repo
    behavior for every caller that isn't a committed git checkout — which
    in practice is only this package's own test fixtures; real operators
    always run this inside a real repo, where git mv succeeds and the
    rename is staged for them.
    """
    try:
        subprocess.run(
            ["git", "-C", str(repo_root), "mv", str(src), str(dst)],
            check=True, capture_output=True, text=True,
        )
        return
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass
    shutil.move(str(src), str(dst))
```

Applied at both existing `shutil.move` call sites in `_migrate_one`:
- Line 340 (archive `.md` → `.md.v1-archive` after a successful migration).
- Line 181 (`--force` restore path, archive → `.md`, the reverse move) — the
  operator flagged this as having the same untracked-move problem "in
  reverse"; since the helper already handles both directions identically,
  fixing both costs nothing extra and keeps the two code paths symmetric.

New files get staged via the existing `plan_ops._stage(repo_root, paths)`
helper (imported into `migrate.py`, not reimplemented — it's already
best-effort `check=False` `git add`, exactly the semantics wanted here):
`_meta.yaml`, `_prose.md`, every `NN.yaml`, called once after all of a
plan's files are written and validated (right after the `_parse_v2`
re-validation succeeds, alongside the archive move).

**Explicitly out of scope:** staging `_rewrite_spec_table`'s edits to an
*already-tracked* spec `.md` (column-drop, File-cell rewrite). That's a
modification of a tracked file, not a new/deleted file — `git status`
already shows it as a normal unstaged modification, which is not the
specific "operator has to manually `git add`/`git rm` untracked mess"
complaint in the issue. (The one new write this PR *does* stage —
`_ensure_spec_plan_row`'s table-creation edit, via `plan_ops._stage` — is
staged because it's new content being introduced by this same PR, for
symmetry with `plan_ops.create()`'s own spec-row staging.)

### 4. Mention `--include-in-progress` in the skip message (UX Gap 1)

`migrate.py` line 209:

```python
reason=f"skipped (in-progress; status={v1plan.status!r})",
```

becomes

```python
reason=(
    f"skipped (in-progress; status={v1plan.status!r}; "
    f"use --include-in-progress to convert anyway)"
),
```

Flag spelling confirmed live against `packages/fr/src/fr/commands/migrate_cmd.py`
(`--include-in-progress`, `v1_to_v2_cmd`).

## Out of scope

- Backfilling spec-table rows for plans that predate this PR and whose spec
  already has a table missing their row (Bug 1's scope note above).
- Any change to `_repair_spec_table_header` / `_repair_spec_table` — both
  already handle their documented cases and are unit-tested; this PR adds a
  read-side warning (`parse_spec`) and a write-side table-creation path
  (`migrate.py`), neither of which touches `repair.py`.
- Staging modifications to already-tracked files made by `_rewrite_spec_table`
  (see Bug 3 scope note above).

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-07-14-migrate-v1-to-v2-spec-table-bugs | `derio-net/super-fr` | `2026-07-14-migrate-v1-to-v2-spec-table-bugs` | — |

## Test Plan

- Unit (`migrate.py` / Bug 1): a v1 plan whose spec file exists but has no
  `## Implementation Plans` section gets the section created with a
  canonical 4-column header and one row referencing the migrated plan's
  bare slug.
- Unit: a v1 plan whose spec file exists and already has an
  `## Implementation Plans` section (any column count) is left untouched by
  the new table-creation path — no duplicate row.
- Unit: a v1 plan whose `**Spec:**` value doesn't resolve to any file on
  disk produces a `MigrationOutcome.warnings` entry naming the unresolved
  value, and migration still succeeds (non-fatal).
- Unit (`spec.py` / Bug 2): `parse_spec` on a table with a 3-column row
  produces a `SpecMeta.warnings` entry naming the spec file and the
  offending row text, and drops the row from `meta.plans` (data never
  guessed at).
- Unit: `parse_spec` on a legacy 5-column table (pre-migrate `Status`
  column) does **not** warn on the header line itself, only on genuine data
  rows with the wrong count (if any) — the header/separator skip fires
  before the column-count check.
- Unit: `compute_status` includes `spec.warnings` in `SpecStatus.warnings`
  (and therefore in `render_status_md`'s output).
- Unit (`migrate.py` / Bug 3): inside a `git init`-ed + committed fixture
  repo, migrating a plan results in the `.md` deletion + `.v1-archive`
  addition showing as a staged rename (`git status --porcelain` reports
  `R  `), and `_meta.yaml`/`_prose.md`/`NN.yaml` show as staged adds (`A `).
- Unit: the same migration run outside a git repo (existing `tmp_path`
  fixtures, no `git init`) behaves exactly as before — plain filesystem
  move, no exception.
- Unit: `--force` re-migration's reverse move (archive → `.md`) is also
  staged when inside a tracked git repo.
- Unit (UX Gap 1): the skip reason string for an in-progress plan contains
  `--include-in-progress`.
- Full suite (`uv run pytest -q --no-cov`), `ruff check`/`format`, `mypy`
  over the four gated packages, and `fr acceptance status --brief` per this
  repo's standing conventions.
