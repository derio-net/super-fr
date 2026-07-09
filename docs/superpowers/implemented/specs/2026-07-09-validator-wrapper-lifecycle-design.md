# Design: validator wrapper lifecycle enforcement

- **Status:** Draft
- **Date:** 2026-07-09
- **Slug:** validator-wrapper-lifecycle
- **Author:** fr-goal (operator: derio)

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-07-09-validator-wrapper-lifecycle | `derio-net/super-fr` | `2026-07-09-validator-wrapper-lifecycle` | — |

## Problem

The user-level PostToolUse plan validator calls
`$REPO_ROOT/scripts/validate-plans.sh` when a repo edits files under
`docs/superpowers/plans/`. Repos that keep plans therefore need a tiny tracked
wrapper at `scripts/validate-plans.sh` that delegates to the canonical validator
installed with the super-fr plugin.

Today the user-level installer only prints a manual per-repo command:

`bash ~/.claude/plugins/marketplaces/derio-net/scripts/install-validator-wrapper.sh`

That is easy to miss, especially when a repo is entered through `fr-goal` or
another autonomous flow. A warning from `fr isolation up` is also insufficient:
the operator might never see it before the workflow proceeds, leaving plan edits
without the validator entry point the hook expects.

## Goals

- `fr init scaffold` automatically installs the tracked validator wrapper for
  repos that already keep plans under `docs/superpowers/plans/`.
- `fr isolation up` fails before creating a worktree/devcontainer when a plan
  repo is missing an executable `scripts/validate-plans.sh` wrapper.
- The failure message includes the exact manual repair command.
- `scripts/install.sh` no longer presents the wrapper as a user-level install
  follow-up; the repo lifecycle owns it.

## Non-goals

- Installing wrappers into repos that do not keep plans under
  `docs/superpowers/plans/`.
- Replacing custom validators. If `scripts/validate-plans.sh` already exists,
  `fr init scaffold` should not overwrite it unless it is already recognized as
  a super-fr wrapper.
- Adding a bypass flag to `fr isolation up`. A real need can justify that later;
  the default should fail closed.

## Design

### Shared wrapper helper

Add a small Python helper in the `fr` package that owns the wrapper content and
recognition logic:

- `plans_dir_exists(repo_root)`: true when `docs/superpowers/plans/` is a
  directory.
- `validator_wrapper_path(repo_root)`: `repo_root/scripts/validate-plans.sh`.
- `is_super_fr_validator_wrapper(path)`: true when an existing file contains the
  historical `superpowers-for-vk` marker or current `super-fr` marker.
- `ensure_validator_wrapper(repo_root)`: write the thin wrapper when missing or
  already recognized; refuse to overwrite any other existing file.
- `validate_plan_repo_validator(repo_root)`: no-op for repos without a plans
  dir; otherwise raise an isolation error if the wrapper is absent or not
  executable.

The wrapper content remains:

`exec "$HOME/.claude/plugins/marketplaces/derio-net/scripts/validate-plans.sh" "$@"`

The shell installer script may keep its standalone behavior, but it should use
the same marker text and remain compatible with the Python recognition rule.

### `fr init scaffold`

After writing `.devcontainer/<profile>/` and `.devcontainer/fr-profiles.yaml`,
`fr init scaffold` checks whether `docs/superpowers/plans/` exists. If it does,
it installs or refreshes `scripts/validate-plans.sh` before the scoped scaffold
commit.

The scoped commit path list expands from:

- `.devcontainer/<profile>`
- `.devcontainer/fr-profiles.yaml`

to include:

- `scripts/validate-plans.sh`, only when this invocation wrote/refreshed it

If a non-super-fr file already exists at that path, scaffolding fails with a
clear error instead of overwriting operator code.

### `fr isolation up`

At the start of `LocalWorktreeDevcontainerTarget.up()`, after confirming the
repo is a git repo and before `git worktree add`, run the validator preflight.
For repos with `docs/superpowers/plans/`, missing or non-executable
`scripts/validate-plans.sh` raises `IsolationError` and exits 2 through the
existing CLI error path.

The message should name the reason and the fix:

`bash ~/.claude/plugins/marketplaces/derio-net/scripts/install-validator-wrapper.sh`

Putting this before `_git_worktree_add()` keeps failed starts clean: no partial
worktree, no devcontainer, no isolation state.

### `scripts/install.sh`

Remove the final manual per-repo step from the user-level installer. The
installer should no longer imply that user-level installation is responsible for
each repo's tracked wrapper. The lifecycle is:

- `fr init scaffold` installs it when a plan repo is being initialized.
- `fr isolation up` refuses to proceed if a plan repo somehow lacks it.

## Test Plan

- Unit: `fr init scaffold` writes and commits `scripts/validate-plans.sh` for a
  repo with `docs/superpowers/plans/`.
- Unit: `fr init scaffold` leaves repos without plans unchanged.
- Unit: `fr init scaffold` refuses to overwrite a custom validator.
- Unit: `fr isolation up` exits 2 before creating a worktree when a plan repo is
  missing the executable wrapper.
- Unit: `fr isolation up` continues for plan repos with an executable wrapper
  and for repos without plans.
- Unit/integration: `scripts/install.sh` output no longer contains the manual
  per-repo wrapper instruction.
