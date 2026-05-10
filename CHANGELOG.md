# Changelog

All notable user-observable changes to the `vk` toolchain. Conventions:
SemVer-ish (see [CLAUDE.md](./CLAUDE.md) for the patch / minor / major
heuristic this project uses), reverse-chronological, breaking changes
flagged with **BREAKING**.

Internal-only changes (test reorganisations, ruff/format passes, doc
typos) are not listed; consult the PR history for those.

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
