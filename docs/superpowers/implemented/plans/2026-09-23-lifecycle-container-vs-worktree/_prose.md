# Container vs worktree lifecycle — implementation plan

Spec: `docs/superpowers/specs/2026-09-23-lifecycle-container-vs-worktree-design.md`
(gh#577, gh#575, gh#471, gh#438).

## Shape

1. **Walking skeleton: `stop`.** This is the smallest verb that exercises the new
   Target protocol surface on all three targets, end to end through the CLI.
2. **Container verbs.** A shared `_devcontainer_up` helper, `rebuild`, the
   stopped-aware `exec`, and `up` keeping its bindings (#577, #471).
3. **Branch classification** (#438). Independent of phases 2 and 4 but touching
   `_git_worktree_add`, which phase 4 also edits, so phase 4 runs after it.
4. **Preserve the run record** (#575, core): run discovery, naming the run in
   refusals, two-phase stage and tombstone, and restore on `up`.
5. **An honest not-found** plus the end-to-end integration walk (#575 acceptance
   4).
6. **Skills, mirrors, the explainer, a minor bump, and the live walks** (#577
   acceptance 1–3, #471 acceptance 1–3), then flipping the matrix rows.

## Notes for executors

- Run everything with `uv run` from the worktree. Never use the bare `fr`
  (AGENTS.md).
- Keep the #354 invariant everywhere: a failed query is never evidence of
  absence.
- Do the live walks on **throwaway** workspaces, never the run's own. The
  executor's commands go through this workspace's container, and rebuilding it
  under a live executor would test the harness, not fr.
- A known gap to record in the plan journal: `<git-common-dir>/fr/preserved/`
  is never aged out.
