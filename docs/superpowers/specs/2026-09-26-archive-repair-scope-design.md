# Archive repair scope and canonical `spec:` form — design

**Date:** 2026-09-26
**Slug:** `2026-09-26-archive-repair-scope`
**Status:** design (fr-goal, autonomous)
**Repo:** `derio-net/super-fr` (single-repo change)
**Issue:** derio-net/super-fr#686

## 1. Goal

Fix two defects on one surface:

1. `fr archive <one plan>` calls `repair_repo(repo_root, write=True)`
   (`packages/fr/src/fr/commands/archive_cmd.py:63` via `_report_sweep`, and
   `:227`), which rewrites every other live plan's `_meta.yaml` `spec:` ref —
   unstaged changes one `git add -A` from shipping in an unrelated PR.
2. `fr repair` writes a bare `spec: <name>-design.md`
   (`packages/fr/src/fr/repair.py`, `_repair_meta`, `canonical = res.path.name`)
   while `fr plan create` stores the operator's argument verbatim
   (`plan_ops.py` `create`, `"spec": spec_str`), typically
   `docs/superpowers/specs/<name>-design.md`. Two writers, two forms: every
   freshly created plan is immediately "stale" to repair.

### Non-goals

- No change to `fr repair` itself: it stays repo-wide (`fr repair [--yes]`).
- No change to `fr archive --all` or `--sweep-only`, which are repo-wide by
  intent.
- No artifact shape change: both forms already parse (`spec` is a free string
  resolved through `refs.resolve_spec_ref`), so no stamp bump or migration.
- Do not touch `run/telemetry.py`, `commands/run_cmd.py`, `isolation/`.

## 2. Decisions (operator, 2026-09-26)

- **Canonical form: the bare filename** (`<name>-design.md`). It is
  lifecycle-independent — it still resolves after the spec moves to
  `implemented/specs/` — whereas the full path goes stale at archive. This
  keeps the 2026-06-06 spec-path-repair doctrine.
- **Scope: repair only the archived plan's own rows** on a single-plan
  archive; `fr repair` remains the repo-wide tool.
- No post-merge Test Plan (CI tests only).

## 3. Design

### 3.A Scoped repair

`repair_repo(repo_root, *, write, only_plans: frozenset[str] | None = None)`.
`None` keeps today's repo-wide behaviour byte-for-byte. When given, the walk
is restricted to the named plan slugs:

- plan `_meta.yaml`: only folders whose name is in `only_plans` (looked up in
  both `plans/` and `implemented/plans/`, since the archived plan has just
  moved);
- spec tables: only rows whose plan-name/File cell slug is in `only_plans`;
  the header normalization (per spec, not per plan) is skipped;
- `plan-config.yaml` dead-key stripping: skipped (repo-level, not a plan row).

### 3.B Archive call sites

Single-plan archive passes `only_plans` = the slugs of the plan(s) it moved.
`_report_sweep` gains an optional `only_plans` parameter, passed by the
single-plan path and left `None` by `--all` / `--sweep-only`. The
post-sweep call at `:227` uses the same scope.

### 3.C Canonical `spec:` form

`plan_ops.create` normalizes a same-repo `spec` ref to the bare filename when
it resolves via `refs.resolve_spec_ref` (cross-repo notation is left as-is,
matching `_repair_meta`; an unresolvable ref — a spec not yet written — is
stored verbatim, as today). The normalization function is shared with
`repair._repair_meta` so there is one definition of canonical. Readers
(`resolve_spec_ref`, the structure validator) keep accepting the full path for
back-compat, so plans already carrying it stay valid and `fr repair`
converges them.

## 4. Test plan (CI only)

Bug, debugging-first: each test is written red before the fix.

1. `fr archive <planA>` with a second live plan whose `spec:` is non-canonical
   leaves that plan's `_meta.yaml` byte-identical.
2. `repair_repo(only_plans=...)` rewrites only the named plan; `None`
   rewrites all (regression pin).
3. `fr archive --all` and `--sweep-only` still repair repo-wide.
4. `plan create --spec docs/superpowers/specs/x-design.md` writes
   `spec: x-design.md`; a following `repair_repo` reports zero rewrites.
5. A plan carrying the full-path `spec:` still validates and resolves.

## 5. Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
