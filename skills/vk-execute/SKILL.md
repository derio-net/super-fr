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
| (plan_path, phase number) | Local: direct arguments |

## PR format (unified)

When creating the PR for an agentic phase:

- **Title:** `[{owner}/{repo}] {slug} · Phase {n}/{total} · {phase_title}` — matches the Issue title shape so VK/GH/PR surfaces align.
- **Body:** first content block is the tracking block copied verbatim from the Issue body (the `📦 Repo:` / `📋 Plan:` / ... lines plus the `**Goal (from plan):**` paragraph). Then proceed with your PR summary.

## Label lifecycle

The Issue moves: `vk-ready → in-progress → pr-ready → closed`. Dispatched mode only.

- `vk execute claim --issue <N> --repo <owner/repo>` — flips to `in-progress`.
- `vk execute pr-opened --issue <N> --repo <owner/repo> --pr-url <url>` — flips to `pr-ready`.

Both are idempotent, retry on transient errors, and hard-fail on persistent failure.

## Procedure

0. **Check plan shape, migrate if needed.** Before anything else:
   ```bash
   vk plan format <plan>
   ```
   If the output is `phased`, continue to step 1. If it is `flat`, run the
   [Migration](#migration) flow below and commit the result as its own PR
   **before** proceeding. There is no path that executes a flat plan directly.
1. Check dependencies (reads the target phase's declared `**Depends on:**`
   list — phases not declared as blockers do not gate pickup):
   ```bash
   vk execute check-deps <plan> <phase>
   ```
1.5. **Claim the Issue (dispatched mode only):**
   ```bash
   vk execute claim --issue $N --repo $REPO
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
6.5. **Mark Issue pr-ready (dispatched mode only):**
   ```bash
   vk execute pr-opened --issue $N --repo $REPO --pr-url $PR_URL
   ```
7. Transition VK Issue to "In Review" (dispatch mode only):
   - Extract the GitHub Issue number from the plan's tracking comment (`<!-- Tracking: ...issues/<N> -->`)
   - Call VK MCP `list_issues` with `search: "gh#<N>"` to resolve the VK Issue ID
   - Call VK MCP `update_issue(issue_id: "<id>", status: "In Review")`
   - If MCP is unavailable or calls fail, skip silently — the server fallback will handle it

## Constraints

- One phase = one PR.
- Migration (if needed) is a separate PR from any phase.
- Don't touch other phases.
- Stop if blocked — report what's missing.
- Step IDs: `P<n>.T<n>.S<n>`.

## Migration

Pick the flow that fits the plan. Either way, migrate as its own PR — separate
from the phase-execution PRs that follow — so diffs stay clean.

**Automatic + review** (default). Use this unless the operator asks for guided.

```bash
# Preview the rewrite
vk plan convert <plan> --to phased --single-phase --dry-run

# If tasks carry `[agentic]` / `[manual]` tags, cluster by them:
vk plan convert <plan> --to phased --group-by-tag --yes

# Otherwise, wrap everything in one phase:
vk plan convert <plan> --to phased --single-phase --yes

git add <plan> && git commit -m "plan: migrate to phased"
```

**Guided**. Use when the plan has natural subsystem boundaries worth capturing
as phases (multiple roles / services / modules):

1. Run `vk plan convert <plan> --to phased --single-phase --yes` to wrap
   everything into Phase 1.
2. Show the operator the task list and ask where phase boundaries should go.
3. Edit the plan: replace the single `## Phase 1:` with N phase headers at the
   chosen boundaries, and renumber tasks per phase (Task 1 of each phase
   starts at 1).
4. Run `vk plan self-review <plan>` to confirm shape.
5. Commit as its own PR.

The converter preserves previously-ticked checkboxes and renumbers step IDs to
`P<n>.T<n>.S<n>` per phase.
