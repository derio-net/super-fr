# Isolation guard `cd` transition allowance

Fixes #279: the strict-mode isolation guard denies the very
`cd <worktree> && gh …` transition its own deny message prescribes, leaving
no allowed path for host-side git/gh ops (the container is deliberately
tokenless). Spec:
`docs/superpowers/specs/2026-06-07-isolation-guard-cd-transition-design.md`.

## Shape

Two agentic phases (strictly ordered) plus one back-loaded manual phase:

1. **Guard allowance (TDD)** — extend `tests/unit/test_hooks_guard.py` with
   a failing `TestCdTransitionAllowance` class, then implement the
   leading-`cd` allowance in `plugins/super-fr/hooks/fr-isolation-guard.sh`:
   target resolved physically, allowed iff inside `FR_CD_ALLOW_PREFIXES`
   (default `$HOME/.cache/fr/worktrees:/tmp:${TMPDIR:-}`) AND outside the
   base repo root (repo-root precedence). Deny message gains the
   `cd <worktree> && …` hint.
2. **Docs + bump** — SKILL.md exec-bridge bullet documenting the
   compound shape, `bump-version.py patch` (3.1.1 → 3.1.2, hooks and skill
   copy are installer-shipped surfaces), full local CI surface.
3. **File the follow-up issue `[manual]`** — the deferred `fr isolation up`
   working-directory suggestion. Back-loaded for the operator: the harness
   permission classifier reserves this external GitHub write; the PR ships
   with this phase deliberately unimplemented.

## Decisions baked in (operator Q&A)

- Allowance breadth: **fr worktrees + temp dirs** — deliberately tighter
  than the field-tested "anywhere outside the repo" cache patch. `cd` to
  arbitrary dirs stays denied during a pipeline.
- Tests pin `FR_CD_ALLOW_PREFIXES` to `tmp_path`-controlled dirs; the real
  `/tmp`/`$TMPDIR` defaults are never relied on (pytest's tmp_path lives
  under them, which would make breadth tests vacuous).
- The post-merge Test Plan (live-session verification after the 3.1.2
  release) lives in the spec, not in a plan phase — it is operator-driven.
