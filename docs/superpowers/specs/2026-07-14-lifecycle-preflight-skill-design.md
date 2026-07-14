# Repo-state lifecycle preflight in `fr-progress` (#378)

**Date:** 2026-07-14
**Status:** Draft — authored for `/fr-goal` on issue #378, one-shot to a PR.
**Target repo:** derio-net/super-fr (package: `plugins/super-fr`)

## Problem

An agent working via the OpenCode harness (issue #378) manually moved plan
files into an incorrect archive layout because it never discovered `fr
archive`, `fr repair`, or `fr migrate v1-to-v2` before assessing the repo as
"done." The repo it was working in had legacy v1 markdown plans, v2 plan
folders, specs linked through plan metadata, and an active acceptance
matrix — none of which triggered any kind of lifecycle preflight before the
agent started hand-editing `docs/superpowers/`.

Verified against current code (2026-07-14): grepping `.opencode/instructions/*.md`
and every shipped skill for `fr status`, `fr repair`, `fr migrate`, and
`fr archive` returns zero hits. No skill or generated instruction currently
walks an agent through "detect this repo is fr-managed, then run the
lifecycle-discovery commands before touching files by hand." The issue's
core claim holds against the codebase as it stands today, not just as a
historical complaint.

`plugins/super-fr/skills/fr-progress/SKILL.md` is the closest existing home:
it already documents `fr apply` (drift audit), `fr spec status [--all]`,
`fr status <plan-dir>` (deep per-plan report, explicitly "safe to
allowlist — it never mutates"), and `fr acceptance status`/`fr acceptance
check` as read-only discovery commands. It has no mention of `fr repair` or
`fr migrate v1-to-v2` at all, and does not frame any of this as a preflight
to run *before* manual file operations under `docs/superpowers/`.

Despite the issue's "OpenCode integration" framing, the actual gap is in
shared skill content that both Claude Code and OpenCode load from the same
source file (`plugins/super-fr/skills/fr-progress/SKILL.md`, mirrored into
`.opencode/skills/` by `scripts/sync-opencode.py`) — there is no
OpenCode-only code path here, so the fix touches skill content, not a new
mechanism.

## Resolved scope (operator-approved, no more than this)

**Skill content only. No new hard-stop / PreToolUse hook.** The operator
explicitly declined a hook that would block manual edits under
`docs/superpowers/plans/` when unmigrated v1 plans exist — that's more
enforcement surface than this fix warrants; a discoverable, well-triggered
skill section is the agreed remedy.

Concretely:

1. Add a "Repo-state preflight" section to `fr-progress/SKILL.md` instructing:
   when `docs/superpowers/` exists, before manually creating/moving/archiving
   anything under it, run in order: `fr --help` (first contact — confirm `fr`
   is installed and this repo is fr-managed), `fr status` (bare — repo-wide
   sweep of archivable/in-progress plans), `fr acceptance check` (matrix
   gate), `fr repair` (dry-run preview of stale-ref rewrites), a check for
   legacy v1 `.md` plans directly under `docs/superpowers/plans/` (as
   opposed to v2 plan folders) and `fr migrate v1-to-v2` (dry-run) if any are
   found, `fr spec status --all`, and only then `fr archive --all` for
   plans the sweep actually marked archivable. State explicitly that manual
   file moves under `docs/superpowers/` are prohibited when `fr` is
   installed.
2. Explain `.md.v1-archive` files: they are the pre-migration original,
   preserved for git history by `fr migrate v1-to-v2`, and they travel with
   their migrated plan folder through `fr archive` — not separate artifacts
   an agent should try to clean up by hand.
3. Extend the skill's frontmatter `description:` so it auto-triggers on "is
   this repo fr-managed," "legacy plans," and "before I archive/move files"
   — the phrases an agent would actually produce when it's about to touch
   `docs/superpowers/` in an unfamiliar repo, not just the existing
   progress-reporting phrases.
4. Version bump (`scripts/bump-version.py patch`) since this touches
   `plugins/*/skills/**`. Regenerate `.opencode/skills/` /
   `.opencode/instructions/` via `scripts/sync-opencode.py` and commit the
   mirror.

## CLI surface this section documents (verified against source, 2026-07-14)

- `fr status` (`packages/fr/src/fr/commands/status_cmd.py`): with no
  `plan_dir` argument, sweeps `docs/superpowers/plans/` and lists archivable
  ("merged-but-unarchived") and in-progress plans. Never mutates GitHub.
- `fr acceptance check` (`packages/fr/src/fr/commands/acceptance_cmd.py`):
  gates the acceptance matrix, exits 2 on any `failing` row.
- `fr repair` (`packages/fr/src/fr/commands/repair_cmd.py`): dry-run by
  default (no flag needed to preview); `--yes` applies and refuses (exit 2)
  on an uncommitted `docs/superpowers/` tree.
- `fr migrate v1-to-v2` (`packages/fr/src/fr/commands/migrate_cmd.py`):
  dry-run by default (`--yes` applies); legacy v1 plans are bare `*.md`
  files directly under `docs/superpowers/plans/` (glob `d.glob("*.md")` in
  `fr/migrate.py`), as opposed to v2 plan folders
  (`<slug>/_meta.yaml` + `NN.yaml`).
- `fr spec status --all` and `fr archive --all`: already documented
  elsewhere in the skill; the preflight section sequences them relative to
  the new commands rather than re-describing them.
- `.md.v1-archive`: per `fr/migrate.py`'s module docstring, the original
  `.md` is moved to `<slug>.md.v1-archive` to preserve git history when a
  plan is migrated to v2.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-07-14-lifecycle-preflight-skill | `derio-net/super-fr` | `2026-07-14-lifecycle-preflight-skill` | — |

## Non-goals

- No new hook, gate, or CI check (operator-declined scope).
- No behavior change to any `fr` command — this is documentation of
  existing, already-correct CLI behavior.
- No OpenCode-specific code path — `fr-opencode-plugin` is untouched.

## Verification

This is skill-content/docs, not application code: there is no runtime
behavior to unit-test, and the resolved scope explicitly excludes a new
hook or gate that could be tested. The verifiable surface is:

- `tests/unit/test_skill_validation.py` — structural checks on every
  `SKILL.md` (frontmatter present, `name`/`description` fields, ≤120 lines,
  the acceptance-duty substring check for `fr-progress`, which already
  requires `"fr acceptance status"` to appear and continues to pass).
- `scripts/sync-opencode.py --check` — verifies the `.opencode/` mirror
  matches the canonical skill after the edit (drift tripwire).
- `scripts/bump-version.py --check` — verifies version lockstep across
  manifests after the bump.

No new automated test is added because there is no executable code path
introduced by this change; the above existing gates are what gate this PR.
