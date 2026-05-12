---
name: vk-execute
description: >
  Execute an agentic phase from a plan. Use when implementing
  assigned work from a plan file. Agent-facing skill.
---

# vk-execute

Implements a single phase from a plan.

**Announce at start:** "I'm using vk-execute to implement this phase."

## Mode selection

| Input | Mode |
|---|---|
| Issue URL/number (dispatch repo) | Dispatched: read assignment from Issue body |
| (plan_dir, phase number) | Local: direct arguments |

## PR format (unified)

When creating the PR for an agentic phase:

- **Title:** `[{owner}/{repo}] {slug} · Phase {n}/{total} · {phase_title}` —
  matches the Issue title shape so VK / GH / PR surfaces align.
- **Body:** first content block is the tracking block copied verbatim from
  the Issue body (the `📦 Repo:` / `📋 Plan:` / … lines plus the
  `**Goal (from plan):**` paragraph). Then proceed with your PR summary.

The `vk pickup` output below provides the canonical PR title template.

## Label lifecycle (no manual transition verbs in v2)

The Issue moves: `vk-ready → in-progress → pr-ready → closed`. v2 has no
manual transition verbs — every label flip is derived from what the
renderer can observe on the Issue plus its linked PRs:

- **`vk-ready`:** the phase has a `tracking_issue` but no assignee, no draft
  PR, and no open non-draft PR.
- **`in-progress`:** the Issue has an assignee OR a draft linked PR.
- **`pr-ready`:** an open non-draft, non-merged linked PR exists.
- **closed:** `state.completion.at` is set on the phase AND a merged PR is
  observed AND no open linked PR remains (per `_phase_complete` in
  `render.py`).

The `vk apply` step at the end of the phase pushes whichever transitions the
renderer projects from current GitHub state. To trigger `in-progress`,
assign yourself to the Issue (or open a draft PR); to trigger `pr-ready`,
take the PR out of draft.

## Procedure

1. **Get phase scope:**
   ```bash
   vk pickup <plan-dir> --phase N
   ```
   Output is markdown: phase title, dependency reminder, PR title template,
   tasks + steps, and a pointer to `_prose.md` for plan-level context.
   The `Depends on:` line surfaces blockers — if any blocker phase is not
   yet `Complete`, stop and report.

2. **Implement.** Delegate to `superpowers:executing-plans` (or
   `superpowers:subagent-driven-development` for parallel-friendly phases).

3. **Tick steps as you complete them:**
   ```bash
   vk plan edit <plan-dir> --tick P<n>.T<n>.S<n> --state x
   # or, to record a deliberate skip:
   vk plan edit <plan-dir> --tick P<n>.T<n>.S<n> --state - --note "<reason>"
   ```

4. **Mark the phase complete (after every step is ticked):**
   ```bash
   vk plan edit <plan-dir> --complete-phase N
   # manual phases require --note describing what was done
   vk plan edit <plan-dir> --complete-phase N --note "<runbook ref>"
   ```

5. **Open the PR.** Delegate to `superpowers:finishing-a-development-branch`.
   Use the PR title from `vk pickup` and the body shape above.

6. **Reconcile GitHub state:**
   ```bash
   vk apply <plan-dir>           # preview the projected mutations
   vk apply <plan-dir> --yes     # push label / state changes
   ```
   `vk apply` is idempotent and reads the current Issue + linked PR state
   from gh. Re-running after the PR merges closes the Issue automatically.

## Constraints

- One phase = one PR.
- Don't touch other phases.
- Stop if blocked — report what's missing.
- Step IDs: `P<n>.T<n>.S<n>`.
- Migration from v1 (.md) plans is a separate concern — see `vk migrate v1-to-v2`.

## Bridge integration

`vk.bridge.discover_plans` + `vk.bridge.tick` are the library surface
the live cron bridge (`agent-images/kali/scripts/vk-issue-bridge.py`)
imports — NOT operator CLI commands. Agents executing a phase never call
them. See spec §"Bridge integration — `vk.bridge.*`".

## v1 plan migration

If you encounter a `.md` plan file (not a folder), it's a v1 plan that needs
migration to the v2 plan-as-folder format before any execution:

```bash
vk migrate v1-to-v2           # preview (default)
vk migrate v1-to-v2 --yes     # apply: creates <slug>/ folders, moves .md to .md.v1-archive
```

Migration is repo-wide; it converts every v1 plan in
`docs/superpowers/{plans,archived-plans}/` and rewrites spec tables.
Commit as its own PR before resuming phase execution.
