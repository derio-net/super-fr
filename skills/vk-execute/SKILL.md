---
name: vk-execute
description: >
  Execute an agentic phase or task from a plan. Use when implementing
  assigned work from a plan file. Agent-facing skill.
---

# vk-execute

Implements a single phase (phased) or task (flat) from a plan.

**Announce at start:** "I'm using vk-execute to implement this phase/task."

## Mode selection

| Input | Mode |
|---|---|
| Issue URL/number (dispatch repo) | Dispatched: read assignment from Issue body |
| (plan_path, phase/task number) | Local: direct arguments |

## PR format (unified)

When creating the PR for an agentic phase:

- **Title:** `[{owner}/{repo}] Phase {n}/{total} · {phase_title}` — matches the Issue title shape so VK/GH/PR surfaces align.
- **Body:** first content block is the tracking block copied verbatim from the Issue body (the `📦 Repo:` / `📋 Plan:` / ... lines plus the `**Goal (from plan):**` paragraph). Then proceed with your PR summary.

## Label lifecycle

After `gh pr create` succeeds:

    gh issue edit <issue_number> --repo <owner/repo> \
       --add-label pr-ready --remove-label in-progress

Best-effort: failure does not block PR creation.

## Procedure

1. Check dependencies:
   ```bash
   vk execute check-deps <plan> <phase-or-task>
   ```
2. Get work scope:
   ```bash
   vk execute scope <plan> <phase-or-task>
   ```
3. Delegate to `superpowers:executing-plans` or `superpowers:subagent-driven-development`.
4. After each step completes:
   ```bash
   vk execute check-step <plan> <step-id> [--state x]
   ```
5. Generate PR body:
   ```bash
   vk execute pr-body <plan> <phase-or-task> [--issue N]
   ```
6. Delegate to `superpowers:finishing-a-development-branch`.
7. Transition VK Issue to "In Review" (dispatch mode only):
   - Extract the GitHub Issue number from the plan's tracking comment (`<!-- Tracking: ...issues/<N> -->`)
   - Call VK MCP `list_issues` with `search: "gh#<N>"` to resolve the VK Issue ID
   - Call VK MCP `update_issue(issue_id: "<id>", status: "In Review")`
   - If MCP is unavailable or calls fail, skip silently — the server fallback will handle it

## Constraints

- One phase/task = one PR.
- Don't touch other phases/tasks.
- Stop if blocked — report what's missing.
- Step IDs: `P<n>.T<n>.S<n>` (phased) or `T<n>.S<n>` (flat).
