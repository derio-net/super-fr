# fr-goal closeout defects (gh#610)

Spec: `docs/superpowers/specs/2026-09-25-fr-goal-closeout-defects-design.md`.

Four of gh#610's five defects are fixed here. Defect 2 (container port
publishing) was dropped by the operator.

1. **verify-merge** resolves the default branch and never tracebacks. It is the
   walking skeleton: the smallest end-to-end change, plus the minor version bump.
2. **The validator wrapper** ships with the first `fr plan create`, and the guard's
   remedy is the harness-neutral `fr init validator-wrapper`.
3. **fr commits its own record writes** (run cursor, plan edits, journal entries)
   with one path-scoped committer extracted from `commit_migration`. The commit is
   made at the CLI layer, never on the default branch, and never fails the write.
4. **`fr pickup --run <id>`** prints a closeout brief from the run file. Resolving
   `deliver` and a finished `advance` hand off that exact command for a new
   session.
5. **Skill prose, mirrors, and an end-to-end closeout proof** on a `master`
   fixture repo.

Order: phase 3 depends on phase 2, because `plan create`'s commit includes the
wrapper. Phase 4 depends on phase 3, because the handoff prints the cursor
commit's sha. Phase 5 proves the whole combination.

Risk: phase 3 is the wide one. Tests that assume fr leaves a dirty tree will need
their assertions changed, not the behaviour. Each such change is journaled.
