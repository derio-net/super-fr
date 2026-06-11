# Scaffold commits the devcontainer profile (#299 part 2)

## Why

On a fresh repo, `fr init scaffold` writes `.devcontainer/<profile>/` but never
commits it, while `fr isolation up` cuts the worktree from the branch's
*committed* tree — so the profile never reaches the worktree and `devcontainer
up` fails. The agent can't fix it by hand (base-repo `git commit` is
gate-denied even after #305), so the fr-goal bootstrap of a fresh repo
deadlocks.

Full design + operator-approved decisions:
`docs/superpowers/specs/2026-06-11-scaffold-devcontainer-propagation-design.md`.

## Approach

Operator chose **A — scaffold commits the profile** (over having `up` carry it
into the worktree). A devcontainer profile is permanent repo infrastructure, so
it belongs committed on the base branch; `up` stays unchanged. Committing is
**intrinsic** (on by default; `--no-commit` is a write-only escape hatch), since
a scaffold whose files aren't committed isn't a usable profile.

TDD throughout (the test fixture already uses a real git repo, so commits are
exercised for real):
- **Phase 1** — `scaffold_profile` makes a scoped commit by default, with the
  edge cases (re-scaffold no-op, zero-commit initial commit, git-ignored warn).
- **Phase 2** — `--no-commit` CLI escape hatch.
- **Phase 3** — `up` raises an actionable "profile written but not committed"
  error instead of the cryptic `devcontainer up failed`.
- **Phase 4** — skills drop the gate-blocked manual-commit step; version bump.

## Key decisions

- **Scoped commit** — only the two files scaffold wrote
  (`.devcontainer/<profile>/` + `.devcontainer/fr-profiles.yaml`) are staged;
  the operator's other dirty changes are never swept in.
- **Commit on HEAD** — no branch creation/switching; during bootstrap that's
  `main`, so the profile lands as permanent infra and the later feature PR
  carries only the feature.
- **Net effect** — with #305 (part 1) allowing `fr init` through the gate and
  this part committing, the fr-goal fresh-repo bootstrap is fully
  agent-completable end-to-end.

## Out of scope

#299 parts 1 (gate allowlist) and 3 (exec workspace resolution), both shipped
in #305.
