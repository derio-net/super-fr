---
name: vk-execute
description: >
  Execute an agentic phase or task from a plan. Use when implementing
  assigned work from a plan file. Agent-facing skill.
---

# vk-execute

Implements a single phase from a plan. Flat plans are deprecated — see
[Migrating flat plans](#migrating-flat-plans) below.

**Announce at start:** "I'm using vk-execute to implement this phase."

## Mode selection

| Input | Mode |
|---|---|
| Issue URL/number (dispatch repo) | Dispatched: read assignment from Issue body |
| (plan_path, phase number) | Local: direct arguments |

## PR format (unified)

When creating the PR for an agentic phase:

- **Title:** `[{owner}/{repo}] {slug} · Phase {n}/{total} · {phase_title}` — matches the Issue title shape so VK/GH/PR surfaces align.
- **Body:** first content block is the tracking block copied verbatim from the Issue body (the `📦 Repo:` / `📋 Plan:` / ... lines plus the `**Goal (from plan):**` paragraph). Then proceed with your PR summary.

## Label lifecycle

After `gh pr create` succeeds:

    gh issue edit <issue_number> --repo <owner/repo> \
       --add-label pr-ready --remove-label in-progress

Best-effort: failure does not block PR creation.

## Procedure

1. Check dependencies:
   ```bash
   vk execute check-deps <plan> <phase>
   ```
2. Get work scope:
   ```bash
   vk execute scope <plan> <phase>
   ```
3. Delegate to `superpowers:executing-plans` or `superpowers:subagent-driven-development`.
4. After each step completes:
   ```bash
   vk execute check-step <plan> <step-id> [--state x]
   ```
5. Generate PR body:
   ```bash
   vk execute pr-body <plan> <phase> [--issue N]
   ```
6. Delegate to `superpowers:finishing-a-development-branch`.
7. Transition VK Issue to "In Review" (dispatch mode only):
   - Extract the GitHub Issue number from the plan's tracking comment (`<!-- Tracking: ...issues/<N> -->`)
   - Call VK MCP `list_issues` with `search: "gh#<N>"` to resolve the VK Issue ID
   - Call VK MCP `update_issue(issue_id: "<id>", status: "In Review")`
   - If MCP is unavailable or calls fail, skip silently — the server fallback will handle it

## Constraints

- One phase = one PR.
- Don't touch other phases.
- Stop if blocked — report what's missing.
- Step IDs: `P<n>.T<n>.S<n>`.

## Migrating flat plans

Flat plans are deprecated. Plan shape should reflect review units (one phase =
one PR), not routing. Dispatch intent lives in `plan-config.yaml` — structure
and routing are independent concerns.

If this skill is handed a flat plan, migrate it before execution:

```bash
# Preview first
vk plan convert <plan> --to phased --single-phase --dry-run

# If tasks carry `[agentic]` / `[manual]` tags, cluster by them:
vk plan convert <plan> --to phased --group-by-tag --yes

# Otherwise, wrap everything in one phase (simplest, safest):
vk plan convert <plan> --to phased --single-phase --yes
```

Commit the migration as its own PR so the execution PRs that follow are clean
diffs. The converter renumbers tasks per-phase so step IDs resolve as
`P<n>.T<n>.S<n>`, and previously-ticked checkboxes are preserved.
