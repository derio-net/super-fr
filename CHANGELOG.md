# Changelog

All notable user-observable changes to the `vk` toolchain. Conventions:
SemVer-ish (see [CLAUDE.md](./CLAUDE.md) for the patch / minor / major
heuristic this project uses), reverse-chronological, breaking changes
flagged with **BREAKING**.

Internal-only changes (test reorganisations, ruff/format passes, doc
typos) are not listed; consult the PR history for those.

## 2.0.0 — single state machine

**BREAKING — full rewrite per [the v2 design spec](docs/superpowers/specs/2026-05-06-vk-rebuild-state-machine-design.md).**

The plan format is now folder-based (`docs/superpowers/plans/<slug>/` with
`_meta.yaml`, `_prose.md`, and per-phase `NN.yaml` files). Use `vk migrate
v1-to-v2 --yes` to convert existing v1 `.md` plans; the migration tool
handles rework metadata, conflicting target_repo loud-fails, and updates
spec tables in lockstep.

The CLI surface collapses to:

- `vk apply` — render → observe → diff → mutate (idempotent reconciler).
- `vk plan {create,edit,rework,rework-add,rework-list,self-review}`.
- `vk pickup --phase N` — agent-facing phase scope.
- `vk spec status` — spec rollup, computed on demand.
- `vk migrate v1-to-v2` — the v1 off-ramp.

There are no separate `dispatch` / `progress` / `execute` / `admin` /
`issue` verbs in v2. Every state change is derived from observation of
the plan files plus GitHub state.

The bridge in willikins requires its own migration to call the v2 vk
library directly (Plan 2 of the v2 rebuild spec); until that lands, the
bridge continues to operate on consumer repos that haven't migrated.
Cross-repo plan resolution in `vk spec status` is also Plan-2 work and
currently surfaces cross-repo plans as `Unreachable`.

## 1.5.0 — v1 retirement

**BREAKING.** Every v1 CLI command is removed:

- `vk plan {new,convert,write,validate,rework,spec-index,format,...}`
- `vk dispatch {create,migrate,...}`
- `vk progress {sync,board,audit,transition,create}`
- `vk admin *`
- `vk execute {claim,scope,check-deps,check-step,pr-body,pr-opened}`
- `vk issue *`
- `vk init`

Replaced by the v2 surface (which has been available under `vk v2 ...`
since 1.4.x):

- `vk apply [<plan-dir>|--all] [--yes] [--format text|json]`
- `vk pickup <plan-dir> --phase N`
- `vk plan {create,edit,rework,rework-add,rework-list,self-review}`
- `vk spec status [<spec-path>|--all]`
- `vk migrate v1-to-v2 [--yes] [--include-in-progress]`
- `vk skills`

`vk migrate v1-to-v2` is the supported off-ramp from v1 `.md` plans to v2
plan-as-folder format. Migration is dry-run by default; pass `--yes` to
write. The migration tool itself remains available through 1.x; consumer
repos with v1 plans should run it once and commit the result.

Skill files (`skills/vk-{plan,dispatch,execute,progress}/SKILL.md`)
rewritten to reference only v2 commands.

## Earlier releases

Pre-1.5.0 releases were tracked through PR descriptions and commit
history rather than this file. See git log for details. Notable
milestones:

- **1.4.x** — v2 library + CLI shipped under `vk v2 ...` namespace
  (Phases 1–3 of the v2 rebuild plan).
- **1.0.x — 1.3.x** — v1 plan/dispatch/progress/execute toolchain.
