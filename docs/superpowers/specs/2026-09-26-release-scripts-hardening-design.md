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

Add `_set_project_version(text, new, path)` in `version_surfaces.py`. It finds
the `[project]` table header with `^\[project\][ \t]*(#.*)?$` (multiline; a
trailing comment is valid TOML), bounds the table at the next real table header
(`^\[\[?[A-Za-z0-9_"'.\- ]+\]\]?[ \t]*(#.*)?$` — a line that merely starts
with `[`, such as the continuation of a multi-line array, does not end the
table), applies the existing `_TOML_VERSION_RE` with `count=1` **inside that
slice only**, and splices the result back. If the table or its `version` line
is not found, or the regex does not match (`_TOML_VERSION_RE` accepts
double-quoted values only, so a single-quoted `version = '1.0'` that `tomllib`
accepts is a silent no-op today), it raises `ValueError` naming the file — never
falls back to first-match.

`version_surfaces()` already raises `ValueError` for a *missing* `[project].version`
(via `tomllib`, `_toml_version`), so the new guard's reachable cases are the
regex-mismatch and the bounding ones above. `write_version` computes every
pyproject rewrite in memory **before** writing any file, so a refusal leaves the
whole tree untouched (today it writes file by file, and a failure on a member
would leave earlier files rewritten).

`uv.lock` is unchanged: `_write_lock_versions` already scopes each
substitution to one `[[package]]` block, where `version` precedes every
subtable.

### 2.B `requires_bump`

Replace the two `plugins/super-fr/...` prefix checks with
`re.match(r"plugins/[^/]+/skills/", path)` for skills, and keep
`plugins/super-fr/rules/` for rules (AGENTS.md documents rules for super-fr
only). Plugin manifests under `plugins/*/.claude-plugin/` are not matched; they
stay `False` by fall-through (version surfaces are caught by the separate "no
PR edits a version" rule), and neither `plugins/x/.claude-plugin/skills/...`
nor `plugins/skills/...` matches.

### 2.C CI

The `change-fragment` job (`ci.yml:94-102`) has only `actions/checkout@v4`.
Add `- uses: astral-sh/setup-uv@v4` after it (as the neighbouring jobs do) and
change the run line to
`uv run --no-project python scripts/check-change-fragment.py "origin/${{ github.base_ref }}"`.
The stale "plain python" docstring line in `check-change-fragment.py` is
updated in passing.

## 3. Out of scope

Reworking `uv.lock` handling; changing which rules paths require a bump beyond
what AGENTS.md documents; touching the `release.yml` invocation (already uv).

## 4. Tests

Each is red before the change:

- `tests/unit/test_version_surfaces.py`: a member pyproject whose first table
  is `[tool.x]` with its own `version = "0.0.1"` — `write_version` moves
  `[project].version` and leaves the tool table byte-identical; `[project]`
  followed by `[project.urls]` and by a tool table; `[project]  # comment`
  header; a multi-line array with a nested `[` line inside `[project]`; a
  single-quoted `version` raises `ValueError` and `write_version` leaves every
  file (root included) unwritten.
- `tests/unit/test_version_bump_guard.py`:
  `plugins/super-fr-dispatch/skills/fr-dispatch/SKILL.md` requires a bump;
  `plugins/super-fr-dispatch/rules/x.md`, `plugins/super-fr/.claude-plugin/plugin.json`,
  `plugins/x/.claude-plugin/skills/y` and `plugins/skills/y` do not.
- `tests/unit/test_change_fragment_gate.py`: a tripwire that the `change-fragment`
  job in `ci.yml` has the `setup-uv` step and invokes
  `uv run --no-project python scripts/check-change-fragment.py`.

Acceptance: the existing change-fragment-gate row cites the bump-guard and
fragment-gate tests but not `test_version_surfaces.py`; the phase adds that ref
with `fr acceptance set-status ... --level unit=super-fr:tests/unit/test_version_surfaces.py`
(status unchanged, `--notes` saying why). No new row: this spec has no
dedicated test-plan section.

## 5. Delivery

One phase, one PR. No change fragment: the touched paths (`scripts/version_surfaces.py`,
`scripts/check-change-fragment.py`, `ci.yml`, `tests/**`, docs) are none of the
paths `requires_bump` lists, so the `change-fragment` job does not require one.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-26-release-scripts-hardening | `derio-net/super-fr` | `2026-09-26-release-scripts-hardening` | — |
