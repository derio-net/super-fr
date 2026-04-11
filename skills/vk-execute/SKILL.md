---
name: vk-execute
description: >
  Execute an agentic phase from a VK-dispatched plan. Understands Phase > Task > Step
  hierarchy. Agent-facing skill — not directly invoked by the operator. VK workspace
  agents use this to implement their assigned phase.
---

# VK Execute

## Overview

Implements a single agentic phase from a VK-dispatched plan. This skill is agent-facing — it is referenced in GitHub Issue bodies created by `vk-dispatch` and used by VK workspace agents to execute their assigned work.

**Announce at start:** "I'm using the vk-execute skill to implement this phase."

## How It Works

This skill wraps `superpowers:executing-plans` (or `superpowers:subagent-driven-development` if subagents are available) with phase-scoping constraints. The agent reads its assigned Phase, iterates through Tasks within the Phase, and executes Steps within each Task. Never touches other phases.

The plan file lives in the same repo as the workspace (single-repo plan rule). If the Issue references a plan file that doesn't exist in the workspace, stop and report — the Issue is likely misconfigured or the workspace is cloned from the wrong repo.

## Procedure

### Step 1: Read the Assignment

Read the GitHub Issue body to extract:
- **Plan file path** — from the `Plan file:` line
- **Phase number** — from the `Phase:` line
- **Target repo** — from the `Repos:` line in `## Workspace`
- **Dependencies** — from `## Dependencies` (e.g., `Blocked by #N`)

If any of these are missing, stop and report: "Issue body is missing required fields. Was this dispatched with vk-dispatch?"

### Step 2: Check Dependencies

For each `Blocked by #N` dependency:
1. Query the referenced Issue state
2. If the blocking Issue is still open, **stop immediately**: "Phase blocked by #N (still open). Cannot proceed."
3. If the blocking Issue is closed, continue

Do not attempt to work around unresolved dependencies. Stop cleanly.

### Step 3: Read and Scope the Plan

1. Read the plan file at the path from the Issue body (path is repo-relative)
2. Locate the assigned phase: `## Phase <N>:`
3. Extract only the Tasks within this Phase:
   - Tasks are `### Task N:` headers
   - Steps are `- [ ] **Step N:**` checkboxes within each Task
   - A Phase typically has 1-8 Tasks, each with 3-8 Steps
4. Ignore all other phases — they belong to other agents or the operator

### Step 4: Execute the Phase

Invoke the upstream execution skill with the scoped phase content:

- **If subagents are available:** Use `superpowers:subagent-driven-development`
- **If no subagents:** Use `superpowers:executing-plans`

Additionally, use `superpowers:test-driven-development` for all implementation work within the phase.

Follow all upstream rules: bite-sized steps, run verifications, stop when blocked.

### Step 5: Update Plan Checkboxes

As each Step within each Task completes, update the plan file:
- Change `- [ ]` to `- [x]` for completed Steps
- Only update checkboxes within the assigned Phase
- Never touch checkboxes in other Phases
- After completing all Steps in a Task, verify the Task is fully checked before moving to the next Task. Tasks that have explicitly ignored/skipped, after confirmation from the operator, need to be marked with `- [-]` and a comment explaining the decision must be added

### Step 6: Open PR

When all tasks in the phase are complete and verified:

1. Invoke `superpowers:finishing-a-development-branch`
2. The PR title should reference the phase: `feat: <phase-name> (Phase N)`
3. The PR body should link to the GitHub Issue: `Closes #<issue-number>`

## Constraints

- **One phase = one PR.** Do not combine phases or split a phase across PRs.
- **Don't touch other phases.** If you see work that should be done in another phase, note it in the PR description — don't do it.
- **Stop if blocked.** If a dependency is missing (file, API, env var from a manual phase), stop and report what's missing. Don't guess or stub.
- **Respect phase boundaries.** The plan file may have many phases. You own exactly one.

## Error Handling

- **Plan file not found:** Report and stop.
- **Phase not found in plan:** Report the phase number and available phases, then stop.
- **Dependency Issue still open:** Report the blocking Issue number and stop.
- **Test failure:** Follow `superpowers:systematic-debugging`. If unresolvable, stop and report.
- **Missing infrastructure from manual phase:** Stop and report what's missing. The operator needs to complete the manual phase first.

## Integration

- **Upstream dispatch:** `superpowers-for-vk:vk-dispatch` — created the Issue this skill reads
- **Upstream plan:** `superpowers-for-vk:vk-plan` — created the plan file
- **Execution engine:** `superpowers:executing-plans` or `superpowers:subagent-driven-development`
- **Testing:** `superpowers:test-driven-development`
- **Completion:** `superpowers:finishing-a-development-branch`
- **Progress:** `superpowers-for-vk:vk-progress` — syncs completion state back to plan
