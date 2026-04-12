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

## Constraints

- One phase/task = one PR.
- Don't touch other phases/tasks.
- Stop if blocked — report what's missing.
- Step IDs: `P<n>.T<n>.S<n>` (phased) or `T<n>.S<n>` (flat).
