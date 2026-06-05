# v1 command retirement — final decisions

**Status:** Approved
**Date:** 2026-05-14
**Repos affected:** `derio-net/superpowers-for-vk`

## Goal

Close out the post-v2.0.0 "v1 retirement gaps" thread by recording final
spec-or-skip decisions for the three CLI surfaces removed in commit
`12365db` (v2.0.0 cut): `vk issue create`, `vk issue convert`, and
`vk admin labels-sync`.

A short-lived restoration of `vk issue create` (PR #128, merged
2026-05-14, version 2.0.5 → 2.1.3 after rebase) is reverted as part of
this decision. The reasoning is recorded below so the call is durable.

## Decisions

| Command | Decision | Version after |
|---------|----------|---------------|
| `vk issue create` | **Skip permanently.** Revert PR #128 (this spec ships with that revert). | 2.1.3 → 2.1.4 |
| `vk issue convert` | **Skip permanently.** Phase 2 of the vk-issue-command plan will not be dispatched. | (no change) |
| `vk admin labels-sync` | **Skip permanently.** Not restored. | (no change) |

## Reasoning

### `vk issue create` — restored then reverted

PR #128 restored `vk issue create` as a 125-LOC wrapper around
`gh issue create` plus a 58-LOC body-template validator. Justification
in the original v1 spec (`2026-04-29-vk-cli-hygiene-and-issue-authoring-
design.md`) was that "agents completing a brainstorm, debug session, or
design review can file the follow-on Issue without manual body editing."

That justification doesn't survive v2's workflow shape:

1. **No callers.** A repo-wide grep across `skills/`, `rules/`, and `src/`
   for `vk issue create` finds zero invocations outside the command's own
   module and tests. No v2 skill instructs an agent to use it.
2. **v2 agents author plans, not standalone Issues.** The canonical
   follow-on path is brainstorm → spec → plan → `vk apply`. Issue bodies
   are emitted by `src/vk/render.py` from plan-as-folder yaml, with the
   bridge contract baked into the renderer. The standalone-Issue case is
   a v1 fossil.
3. **Trivial workaround.** A genuine one-off bridge Issue can be filed
   with a single `gh issue create --label vk-ready` invocation and an
   ~11-line body template stashed under `.github/ISSUE_TEMPLATE/` if
   discoverability matters.

The "validator" (`dispatch_body_validator.py`) duplicated parsing the
bridge itself already performs, with error surfacing.

**Net cost of keeping it:** ~470 LOC of code + tests, plus the `vk issue`
Typer group in `cli.py`, plus the un-archived plan, plus future
maintenance burden any time the bridge contract evolves.

**Net cost of skipping it:** none — `gh issue create` is always available.

### `vk issue convert` — never dispatch

Phase 2 of the vk-issue-command plan would take an existing GitHub Issue
and append the bridge contract sections via `gh issue edit`. Use case is
even narrower than `create` — when do you have an existing Issue that
you only *now* want the bridge to pick up? Hand-editing once is fine.

The plan stays archived; Phase 2 is marked as superseded by the
retirement addendum at
`docs/superpowers/archived-plans/2026-04-29-vk-issue-command/_RETIRED-2026-05-14.md`.

### `vk admin labels-sync` — never restore

`vk admin labels-sync` was 243 LOC + tests. It diffed repo labels against
a canonical registry with create/update/remove actions and a dry-run
table, across one or many repos.

v2 covers the 90% case via **lazy ensure-on-apply** in
`src/vk/apply.py:71`:

```python
gh.ensure_labels(m.repo, sorted(m.labels, key=lambda ld: ld.name))
```

`gh.ensure_label` is idempotent — creates if absent, updates color/desc
if present. Only the labels needed for the current plan get ensured.
The registry lives at `src/vk/labels.py`.

The two residual gaps:

| Gap | Frequency | v2 workaround |
|---|---|---|
| Proactive seeding in a fresh repo (before any plan exists) | Once per new repo lifetime | First `vk apply` ensures lazily; or `gh label create <name> --color <hex>` × N |
| Orphan cleanup (labels in repo but not in registry) | Once per major version migration | `gh label delete <name>` |

Retired in commit `12365db` on 2026-05-10. Four days passed before this
audit; no commit since references `labels-sync` or `admin_app`. The
"fight to persist" failed in real time.

## Out of scope

- Restoring `vk admin` as a top-level group for future operator-driven
  cross-repo administration. If a real need arises (e.g., a true label
  registry purge across N repos), revisit with a fresh spec — don't
  default to the v1 shape.
- Removing the `validate_issue_body` helper from any shared module —
  there isn't one. PR #128 reintroduced it as part of `issue_cmd`'s own
  surface; the revert takes it with it.

## Version

This decision spec ships in the same PR as the revert. Version
bumped 2.1.3 → 2.1.4 because `src/vk/cli.py` (removed `issue_app`
registration) and `src/vk/commands/` (three file deletions) change.

## Out-of-band: cross-repo dispatch

The duplicate-issue episode that prompted this audit (Issues #123–#127,
five byte-identical phase dispatches of a willikins plan into
superpowers-for-vk Issue workspace, with phantom `Blocked by #161, #162,
#163` refs that don't exist in this repo) revealed that cross-repo
dispatch is being attempted ad-hoc today without spec-level
orchestration. That gap was the subject of a separate RFC at
`docs/superpowers/archived-specs/2026-05-13-spec-dispatch-design.md`
(archived 2026-05-17, superseded by [#147](https://github.com/derio-net/superpowers-for-vk/issues/147))
and is out of scope for this decision.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| (no implementation plan) | — | — | — |

This is a one-PR decision spec with no follow-on implementation work.
The revert ships with the spec.
