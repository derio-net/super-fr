# Repo-state lifecycle preflight in `fr-progress`

Closes #378.

## Why

An agent working via OpenCode hand-moved plan files into an incorrect
archive layout because nothing surfaced `fr archive`, `fr repair`, or
`fr migrate v1-to-v2` before it assessed the repo as "done." The fix is a
documentation gap, not a code gap: `fr-progress/SKILL.md` is the closest
existing home for progress/lifecycle discovery commands but had no
"run this before touching files by hand" preflight and no mention of
`fr repair` or `fr migrate v1-to-v2` at all.

## Scope (operator-approved)

Skill content only — no new hard-stop or PreToolUse hook. See
`docs/superpowers/specs/2026-07-14-lifecycle-preflight-skill-design.md`
for the full design and the exact CLI surface verified against source.

## Single phase

This is a small, single-phase, docs-only fix — one phase covers the whole
change. There is no manual phase: nothing here needs secrets, UI actions,
or human-only steps.

## Verification

No new automated test is added — there is no executable code path
introduced by a skill-content edit. The gates that do apply:
`tests/unit/test_skill_validation.py` (frontmatter, ≤120 lines, the
`fr-progress` acceptance-duty substring check), `scripts/sync-opencode.py
--check` (mirror drift), `scripts/bump-version.py --check` (version
lockstep), plus the standard `ruff check`/`ruff format --check`/`mypy`/
`pytest` gate.
