# `spec:` writers agree on `canonical_spec_ref` — design

**Date:** 2026-09-27
**Slug:** `2026-09-27-spec-ref-writers`
**Status:** design (fr-goal, autonomous; triage batch `spec-ref-writers`)
**Repo:** `derio-net/super-fr` (single-repo change)
**Issues:** derio-net/super-fr#709, derio-net/super-fr#710, derio-net/super-fr#711

## 1. Goal

Close three leftovers from #697's Opus re-review (plan journal
`2026-09-26-archive-repair-scope`, findings `r2-f7`, `r2-f8`, `r2-f9`). All three
sit around `canonical_spec_ref` (`packages/fr/src/fr/refs.py`) and the code that
writes a plan's `spec:` value:

1. **#709.** `canonical_spec_ref` shortens a relative `spec:` ref whose path
   leaves the repo (`../sibling/docs/superpowers/specs/<slug>.md`) to a
   same-slug local spec when the target is not on this machine. Today the ref
   is kept verbatim only when `candidate.is_file()` holds and the file sits
   outside `SPEC_ROOTS`. An absent foreign target therefore falls through to
   slug resolution, and the only sign that the operator pointed at another repo
   is erased.
2. **#710.** When the spec sweep moves a spec, `fr archive` runs
   `repair_repo(write=True)` twice: once in `_report_sweep`
   (`packages/fr/src/fr/commands/archive_cmd.py`, `if moved:`) and again at the
   tail of `archive_command` (`if archived or specs_moved:`). Every
   `repair.warnings` entry is printed twice.
3. **#711.** The v1→v2 plan migration (`packages/fr/src/fr/migrate.py`,
   `_migrate_one`, `"spec": v1plan.spec`) writes the v1 value verbatim. That
   makes it a fourth `spec:` writer, one that bypasses `canonical_spec_ref`,
   whose docstring says every writer calls it.

### Non-goals

- No artifact shape change. `spec:` stays a free string that every reader
  resolves by slug, so there is no stamp bump and no migration.
- No change to `fr repair`'s scope, or to `--all` / `--sweep-only` semantics.
  Only the number of repair passes changes.
- Other running batches own `fr/isolation/`, `scripts/install.sh`,
  `commands/apply_cmd.py`, `run/telemetry.py`, `run/long_commands.py` and
  `fr/triage/`. This change does not edit them.

## 2. Decisions (operator, 2026-09-27, one question round)

- **The escape test is lexical.** A ref escapes when
  `os.path.normpath(repo_root / value)` is not under
  `os.path.normpath(repo_root)`. The test judges what the operator *wrote*. A
  symlinked `docs/` inside the repo therefore still canonicalizes; a
  `Path.resolve()` test would treat it as foreign.
- **Repair has one owner in `fr archive`.** `_report_sweep` stops repairing. A
  single helper, `_repair_in_passing(repo_root, only_plans)`, prints the
  rewrites and warnings. It runs once at the tail of the archive path, and once
  in `--sweep-only` when something moved. The move and its repair still land in
  the same operator commit.
- **Two acceptance rows** (§5), both ci-pinned by this change's unit tests.

## 3. Design

### 3.A `canonical_spec_ref`: a repo-escaping ref is foreign (#709)

After the cross-repo-notation check and before resolution:

```python
root = os.path.normpath(repo_root)
target = os.path.normpath(os.path.join(root, value))
if os.path.commonpath([root, target]) != root:
    return value
```

`os.path.join` with an absolute `value` yields `value`, so an absolute path
outside the repo is foreign as well, and an absolute path inside it is judged
like any other in-repo path. The rest of the function does not change. The
existing "exists outside `SPEC_ROOTS`" branch still covers an in-repo file
outside the lifecycle roots (`notes/x-design.md`). The docstring gains the new
verbatim case and lists the migration as a writer (§3.C).

`plan_ops.create`, `plan_ops.rework_create`, `plan_ops`'s equality helper, and
`repair._repair_meta` all call `canonical_spec_ref`, so each of them inherits
the fix with no edit. `fr repair` stops shortening such a ref, which is the
point of #709.

### 3.B `fr archive`: one repair pass (#710)

- `_report_sweep(repo_root, sweep)` prints moves and notes and returns
  `bool(sweep.moves)`. It no longer takes `only_plans` and no longer calls
  `repair_repo`.
- A new `_repair_in_passing(repo_root, only_plans)` calls
  `repair_repo(repo_root, write=True, only_plans=only_plans)` and prints
  `repaired:` lines and `warning:` lines, exactly as the two copies do today.
- `--sweep-only`: if `_report_sweep(...)` returns true, call
  `_repair_in_passing(repo_root, None)`, which stays repo-wide as it is today.
- Archive path: the tail's existing `if archived or specs_moved:` block becomes
  the helper's single call. The widening of `only_plans` by
  `plans_referencing_specs` stays where it is, before the tail, so the scoped
  repair still reaches plans that point at a moved spec.

Net effect: with a spec moved, the output carries one `repaired:` line per
rewrite and one `warning:` line per warning, and the files are unchanged from
today (the second pass rewrote nothing).

### 3.C v1→v2 migration writes the canonical form (#711)

In `_migrate_one`:

```python
"spec": refs.canonical_spec_ref(v1plan.spec, repo_root) if v1plan.spec else v1plan.spec,
```

A v1 `spec:` of `docs/superpowers/specs/<slug>-design.md` now migrates to
`<slug>-design.md`. An unresolved, cross-repo or foreign value stays verbatim,
because `canonical_spec_ref` already leaves those alone. A missing value stays
`None`. `_resolve_spec_file`, which finds the spec for the table-row update,
keeps reading the original v1 value; only the stored field changes.

## 4. Test Plan (CI only)

1. `tests/unit/test_repair.py`: `canonical_spec_ref` keeps
   `../sibling/docs/superpowers/specs/x-design.md` verbatim while a local
   `specs/x-design.md` exists (the #709 reproduction), and also keeps an
   absolute out-of-repo path. An in-repo `docs/superpowers/../superpowers/specs/x-design.md`
   still canonicalizes to `x-design.md`. `fr repair` leaves a plan carrying the
   escaping ref untouched.
2. `tests/unit/` archive tests: with a spec moved by the sweep and one repair
   warning present, `fr archive <plan>` prints that warning exactly once, and
   `--sweep-only` still repairs (it prints the `repaired:` line).
3. `tests/unit/test_v2_migrate.py`: a v1 plan whose `**Spec:**` is the full
   `docs/superpowers/specs/<slug>-design.md` path migrates to a `_meta.yaml`
   with `spec: <slug>-design.md`.

## 5. Acceptance rows

- `spec-writers-one-canonical-form`: every `spec:` writer (`fr plan create`,
  rework create, `fr repair`, v1→v2 migration) stores the same canonical form,
  and none of them shortens a ref that leaves the repo.
- `archive-repair-warns-once`: `fr archive` runs repair once per invocation,
  so each repair warning reaches the operator exactly once.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-27-spec-ref-writers | `derio-net/super-fr` | `2026-09-27-spec-ref-writers` | — |
