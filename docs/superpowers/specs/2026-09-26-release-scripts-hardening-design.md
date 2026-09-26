# Release scripts: [project]-anchored TOML rewrite, fragment rule for every plugin's skills, uv-managed Python in CI

- **Date:** 2026-09-26
- **Status:** designed
- **Origin:** gh#669, gh#671, gh#670 (batch `release-scripts`)
- **Goal:** close three latent gaps in the release machinery that 4.24.0 (#666)
  made load-bearing, because the release bot now rewrites version surfaces on
  `main` unattended.

## 1. Problem

1. **gh#669 — table-unaware TOML rewrite.** `scripts/version_surfaces.py`
   rewrites a member `pyproject.toml` with `_TOML_VERSION_RE.sub(..., count=1)`
   over the whole file: the first `^version = "..."` in *any* table. It is
   correct only while `[project]` is the first table that carries a `version`.
   A `[tool.*]` table ahead of `[project]` would be rewritten instead, and the
   release bot would push that to `main`. `write_version` never re-reads to
   check.
2. **gh#671 — narrower code than docs.** `requires_bump` in
   `scripts/check-change-fragment.py` matches `plugins/super-fr/skills/` and
   `plugins/super-fr/rules/` only. AGENTS.md documents `plugins/*/skills/**`.
   A `plugins/super-fr-dispatch/skills/**` change therefore needs no fragment,
   ships without a release, and is stranded on old clients (the installer
   caches by version). Decision: widen the code, not the docs.
3. **gh#670 — bare `python` in CI.** `.github/workflows/ci.yml` runs
   `python scripts/check-change-fragment.py ...`. That works only while the
   runner image aliases `python` to 3.11+ (the script needs `tomllib`). Every
   other script step in CI and `release.yml` already uses
   `uv run --no-project python`.

## 2. Design

### 2.A `write_version` for TOML

Add `_set_project_version(text, new)` in `version_surfaces.py`. It locates the
`[project]` table header (`^\[project\]\s*$`, multiline), bounds the table at
the next line starting with `[` (or end of file), applies the existing
`_TOML_VERSION_RE` with `count=1` **inside that slice only**, and splices the
result back. If there is no `[project]` table, or it has no `version` key, it
raises `ValueError` naming the file — fail loudly before a byte is written,
never fall back to first-match. The `pyproject.toml` branch of `write_version`
uses it.

`uv.lock` is unchanged: `_write_lock_versions` already scopes each
substitution to one `[[package]]` block, where `version` precedes every
subtable.

### 2.B `requires_bump`

Replace the two `plugins/super-fr/...` prefix checks with a path-shape check:
`plugins/<any>/skills/**` requires a bump; `plugins/super-fr/rules/**` keeps
requiring one (AGENTS.md documents rules for super-fr only). Manifests under
`plugins/*/.claude-plugin/` stay exempt, as today (version surfaces are caught
by the separate "no PR edits a version" rule).

### 2.C CI

`ci.yml`'s change-fragment step becomes
`uv run --no-project python scripts/check-change-fragment.py "origin/${{ github.base_ref }}"`.
The job needs `uv`; add the same `astral-sh/setup-uv` step the neighbouring
jobs use if it lacks one.

## 3. Out of scope

Reworking `uv.lock` handling; changing which rules paths require a bump beyond
what AGENTS.md documents; touching the `release.yml` invocation (already uv).

## 4. Tests

Each is red before the change:

- `tests/unit/test_version_surfaces.py`: a member pyproject whose first table
  is `[tool.x]` with its own `version = "0.0.1"` — `write_version` moves
  `[project].version` and leaves the tool table byte-identical; a pyproject with
  no `[project]` version raises `ValueError` and is left unwritten.
- `tests/unit/test_version_bump_guard.py`:
  `plugins/super-fr-dispatch/skills/fr-dispatch/SKILL.md` requires a bump;
  `plugins/super-fr-dispatch/.claude-plugin/plugin.json` still does not.
- `tests/unit/test_change_fragment_gate.py`: a tripwire that the `ci.yml`
  change-fragment step invokes `uv run --no-project python`.

The existing acceptance row on the change-fragment gate already cites these
test files, so no new matrix row is created.

## 5. Delivery

One phase, one PR. No change fragment: the touched paths (`scripts/version_surfaces.py`,
`scripts/check-change-fragment.py`, `ci.yml`, `tests/**`, docs) are none of the
paths `requires_bump` lists, so the `change-fragment` job does not require one.
