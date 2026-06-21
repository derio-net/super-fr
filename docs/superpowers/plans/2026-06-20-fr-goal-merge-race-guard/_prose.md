# fr-goal merge-race guard — plan

Implements [#320](https://github.com/derio-net/super-fr/issues/320) per
`docs/superpowers/specs/2026-06-20-fr-goal-merge-race-guard-design.md`.

**Goal (from plan):** Close the merge-race where fr-goal fix commits land on
an already-merged PR branch and orphan from `main`. Operator decisions:
**Hybrid** enforcement (code-enforce the pre-push guard #2 as a hook; the rest
as skill prose) and **Draft-from-start** PR visibility.

## Phases

1. **Pre-push guard hook** — a new `PreToolUse(Bash)` hook
   `fr-merged-pr-push-guard.sh` that DENIES `git push` while an fr pipeline is
   active and the current branch's PR is `MERGED`/`CLOSED`. Fail-open on every
   ambiguity (no sentinel, no push, no PR, gh/jq absent, network/auth error).
   TDD via a fake-`gh`-on-PATH harness mirroring `test_hooks_guard.py`.
2. **Skill prose** — fr-goal (build pushes branch only; orchestrator opens a
   DRAFT PR; `gh pr ready` only post-review; squash-aware close-out
   verification; hand-off wording), fr-isolation (document the enforced
   pre-push guard), fr-execute (step-5 caveat: no per-phase PR under fr-goal
   local mode).
3. **Version bump + full gate** — `bump-version.py patch` (3.4.0 → 3.4.1) and
   the full CI gate green.

## Notes

- All phases are pure agentic; there is **no manual phase** (no secrets, UI,
  or deploy). The PR ships complete.
- The hook is sentinel-scoped (active fr pipelines only) — matching the
  isolation guard's blast radius and covering the exact failure path (the
  orchestrator session that pushed the orphaned fix carries a sentinel).
- Close-out verification is **content-based, not SHA-ancestry**, because
  super-fr squash-merges (`git merge-base --is-ancestor` would false-negative).
