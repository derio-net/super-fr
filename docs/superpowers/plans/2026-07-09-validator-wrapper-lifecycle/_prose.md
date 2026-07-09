# Validator wrapper lifecycle enforcement

Spec: `docs/superpowers/specs/2026-07-09-validator-wrapper-lifecycle-design.md`

## Why

Plan repos rely on the user-level PostToolUse hook calling a tracked per-repo
entry point at `scripts/validate-plans.sh`. Today that wrapper is installed by a
manual instruction printed at the end of `scripts/install.sh`, which is too easy
to miss in autonomous flows. A warning from `fr isolation up` is also too weak:
`fr-goal` can proceed without the operator seeing it.

## Shape of the change

Add one shared helper for validator-wrapper content, recognition, installation,
and isolation preflight checks. `fr init scaffold` uses it to install or refresh
the wrapper for repos that already have `docs/superpowers/plans/`. `fr isolation
up` uses it to fail closed before creating a worktree when a plan repo lacks an
executable wrapper.

The user-level installer stops printing the manual per-repo step. Repo lifecycle
commands own the wrapper now: scaffold installs it, isolation enforces it.

## Acceptance linkage

- `plan-validator-wrapper-lifecycle` -> Phase 1
