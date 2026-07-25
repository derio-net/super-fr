# Spec-scope journals must follow their spec into `implemented/`

**Issue:** derio-net/super-fr#417
**Status:** design
**Scope:** `fr archive` spec-journal sweep + `fr journal` read resolver.

## Problem

`fr archive` moves a completed plan folder, its spec, and the **plan-scope**
journal into `docs/superpowers/implemented/`, but leaves the **spec-scope**
journal (`journals/specs/<slug>.md`) behind in the live tree. AGENTS.md
documents the intended layout as "archived to `implemented/journals/<scope>/`"
— one subdir per scope — so plan journals honor it and spec journals don't.
`journals/specs/` accumulates residue for shipped work and stops being
glanceable.

Three archived features' spec journals sit in the live tree today:

- `journals/specs/2026-07-23-hermes-agent-compat.md`
- `journals/specs/2026-07-24-isolation-host-modes.md` (archived in #398)
- `journals/specs/2026-07-24-vk-mcp-timeout-permit-leak.md` (archived in #406)

## Root cause

`spec_archive_sweep` (`packages/fr/src/fr/archive.py`) *does* call
`_archive_journal(repo_root, "spec", spec_path.stem)` — added in #390 — but with
the **wrong slug**. Specs are written as `<YYYY-MM-DD-slug>-design.md`, so
`spec_path.stem` is `<YYYY-MM-DD-slug>-design`; the spec-scope journal is keyed
by the bare feature slug (`journals/specs/<slug>.md`,
2026-07-22-fr-goal-subagent-execution spec §A). The `-design` suffix mismatch
means `journal_path(...)` resolves a non-existent file, so `_archive_journal`
returns early — a silent no-op. Every real spec ends in `-design.md`, so the
move never fires in practice.

The existing test `test_spec_journal_moves_when_spec_archived` passed only
because its fixture spec is named `2026-05-10-solo.md` — *without* the `-design`
suffix real specs carry — so the slug happened to match. The test never
exercised the real naming convention.

## Design

Three changes, mirroring the plan-journal move's idempotence/repair posture.

### 1. Derive the spec-journal slug correctly

Add `spec_journal_slug(spec_stem: str) -> str` to `fr/journal/model.py`: strip a
trailing `-design` suffix so the archive sweep resolves the same file
`fr journal add --scope spec` wrote. A stem without the suffix (an older or
hand-named spec) maps to itself, so the helper is safe for every spec. Own the
`-design` convention in one place so the sweep and any future caller agree.

`spec_archive_sweep` calls `_archive_journal(repo_root, "spec",
spec_journal_slug(spec_path.stem))`.

### 2. Teach the read resolver about the archived location

`fr journal render`/`check` currently resolve only the **active** path
(`journals/<scope>/<slug>.md`), so a journal can't be read once its spec/plan is
archived. Add `resolve_journal_read_path(repo_root, scope, slug)` returning the
active path if it exists, else the archived path
(`implemented/journals/<scope>/<slug>.md`), else the active path (treated as
empty). Wire `render` and `check` to it. `add` keeps writing the active path — a
sealed, archived journal is not appended to.

This closes the same gap for **plan** reads (identical today), making the
issue's "mirroring how plan-journal reads work post-archive" true for both
scopes rather than only aspirational.

### 3. Backfill the three stragglers

The three journals above are orphaned: their specs already moved out of
`specs/`, so `spec_archive_sweep` (which only iterates specs still in `specs/`)
will never revisit them even after fix #1. `git mv` them to
`implemented/journals/specs/` in this PR — the issue sanctions the fix's PR
sweeping them.

## Non-goals

- No standalone orphan-repair scanner. The plan-journal move has none either;
  the move stays tied to the spec/plan move + idempotent (`dst` exists → skip).
  The three pre-existing orphans are handled by the one-time backfill.
- No change to the on-disk journal format or the `add` write path.

## Verification

Pure-code change, no deploy surface — covered by unit tests, no acceptance
matrix rows:

- `spec_journal_slug` strips `-design` and passes non-design stems through.
- `spec_archive_sweep` moves a journal for a realistically named
  `<slug>-design.md` spec whose journal is keyed by the bare slug.
- `resolve_journal_read_path` prefers active, falls back to archived, and
  returns the active path when neither exists.
- `fr journal render`/`check` find a journal at the archived location.
- The three straggler files no longer exist under `journals/specs/` and do
  exist under `implemented/journals/specs/`.
