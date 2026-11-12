# Repo settings core (plan 1 of 3)

Plan 1 of `2026-11-04-repo-feature-settings-design.md` (R29): the settings
surface in the `repo` placement only. Quiet and stealth are refused by the
loader as "not yet available" until plan 3; the acceptance fragment model is
plan 2.

## Phases

1. **Settings core** (R2–R5): `fr/settings/` — a closed pydantic model, a
   loader that reads `.fr/settings.yaml` from the default ref (so a branch can
   never relax its own controls), coherence rules as data, and
   `fr settings init|show|check`, with `init`'s comments generated from the
   model's field descriptions. It is the skeleton: its first task is the
   smoke. CI here runs only on `pull_request`, and fr-goal opens the PR at
   deliver, so the smoke is the local suite.
2. **Policy off** (R6–R8, R15 for those features): acceptance, test_plan and
   gates can be off. Writers refuse, naming the setting. Every surface that
   said "None." splits into "absent" and "disabled by repo setting". The spec
   refusals sit at brainstorm and spec-review resolve and in the spec
   validator, not in plan self-review.
3. **Forge quiet** (R9–R10): one `forge_allows` predicate replaces every
   `tracking: none` check (18 modules; an inventory test keeps it that way),
   plus the scaffolded CI's own issue and comment steps. Under
   `pr_body: minimal` the live PR stays plain, and the full render becomes a
   durable `<run-id>.pr-body.md` that the operator reviews.
4. **Git policy** (R11–R14): an optional `issue` on the run cursor (run kind
   10 → 11, a stamp-only migration), commit templates applied through
   `commit_paths`' one seam (the defaults reproduce today's subjects byte for
   byte), `fr push` (ask gate, squash-unpushed split at merge and migration
   commits, subject check, never a force flag) and `fr pr create` (always a
   draft). The skills switch to both commands.

## Why these splits

Each phase is one independently reviewable ask, backed by one acceptance row:
`repo-settings-file`, `repo-settings-policy-off`, `repo-settings-forge-quiet`
and `repo-settings-git-policy`. Phases 2–4 depend only on phase 1, and run
serially in the shared workspace.

## Risks

- **Phase 3 changes `deliver`'s PR-body gate**, and phase 4 changes the
  `run` kind and adds the only command that rewrites commits (the squash).
  Both are `hard`.
- **The squash must never touch pushed history.** Its tests assert the git
  argv: no force flag, ever.
- **Default templates must not move a byte** of the `chore(fr):` subjects that
  the release cross-check and the usage parsers read.
