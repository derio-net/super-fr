# VK Workspace Lifecycle Automation Design Spec

## Summary

Automate two lifecycle transitions that are currently manual:

1. **Agent completion → "In Review":** When a VK workspace agent finishes its assignment and creates a PR, the linked VK Issue moves to "In Review" automatically.
2. **PR merged → archive workspace:** When a PR is merged and the operator moves the Issue to "Done", the workspace's git worktree is cleaned up automatically.

The design uses a hybrid approach: the agent skill handles the happy path (instant), and server-side periodic jobs handle crash recovery and archival.

## Problem Statement

Today, after a VK workspace agent finishes its work and creates a PR:

- The VK Issue stays in "In progress" until the operator manually transitions it.
- The git worktree stays on disk indefinitely until the operator manually archives it.
- If an agent crashes without creating a PR, nothing flags the issue as stale.

With multiple agents running concurrently on the secure pod, this manual overhead scales linearly with agent count.

## Success Criteria

1. When an agent creates a PR, the linked Issue moves to "In Review" within seconds (happy path) or within 5 minutes (crash fallback).
2. When a PR is merged and the Issue reaches "Done", the workspace worktree is deleted within 10 minutes.
3. No manual operator intervention required for either transition in the normal flow.
4. Failed agent runs (no PR created, session dead) are surfaced rather than silently stuck.

## Scope

**In scope:**
- Skill change to `vk-execute` (agent calls `update_issue` after PR creation)
- VK backend periodic job: crash fallback ("In progress" → "In Review")
- VK backend periodic job: workspace archival ("Done" → archive + cleanup)

**Non-goals:**
- Changes to the VK MCP API surface (all needed tools already exist)
- Changes to issue status definitions (all four statuses exist in Derio Ops project)
- Changes to `vk-dispatch` (dispatch continues to create issues as before)
- PR auto-merge or operator review automation (the "In Review" → "Done" transition stays manual)

## Design Decisions

| # | Decision | Alternatives considered |
|---|----------|------------------------|
| D1 | **Hybrid: skill hook + server fallback.** Agent transitions on the happy path; server catches crashes. | Polling-only (adds latency to happy path), hook-only (no crash recovery) |
| D2 | **Issue lookup by GitHub Issue number.** Agent resolves its VK Issue ID by searching `list_issues` with the `gh#N` pattern from the plan tracking comment. | Pass Issue ID through env var (requires `start_workspace` changes), hardcode in prompt (fragile) |
| D3 | **Archival triggered by "Done" status, not PR merge alone.** The operator manually marks "Done" after review, then the cron archives. | Auto-archive on PR merge (skips operator review gate), webhook-based (requires webhook receiver infrastructure) |
| D4 | **Remote branch deletion on archive.** When a merged workspace is archived, the remote branch is also deleted. | Leave remote branches (accumulates noise), separate cleanup job (more moving parts) |
| D5 | **Failed runs stay "In progress" with a log warning.** Dead sessions with no PR don't auto-transition — they're flagged for operator attention. | Auto-transition to a "Failed" status (requires new status), auto-retry (risky without understanding failure) |

## Components

### Component 1: Skill hook (happy path)

**Location:** `superpowers-for-vk` — `vk-execute` skill (SKILL.md)

**Change:** After the agent creates a PR via `superpowers:finishing-a-development-branch`, add a final step:

1. Extract the GitHub Issue number from the plan's tracking comment (`<!-- Tracking: https://github.com/<owner>/<repo>/issues/<N> -->`)
2. Call VK MCP `list_issues` with `search: "gh#<N>"` to resolve the VK Issue ID
3. Call VK MCP `update_issue(issue_id: "<id>", status: "In Review")`
4. If MCP is unavailable (local mode, no VK server), skip silently — this is dispatch-mode only

**Error handling:**
- If `list_issues` returns no match: log warning, skip transition (don't fail the agent run)
- If `update_issue` fails: log warning, skip (the crash fallback will catch it)
- The agent's primary job (code + PR) is already done at this point — the status transition is best-effort

### Component 2: Crash fallback (server-side periodic job)

**Location:** `vibe-kanban` backend (Rust)

**Schedule:** Every 5 minutes (configurable)

**Logic:**

```
for each issue where status == "In progress":
    workspace = find linked workspace
    if workspace is None:
        skip (issue not managed by VK workspaces)
    
    session = get workspace session
    if session is still alive:
        skip (agent still working)
    
    # Session is dead — agent finished or crashed
    pr = check for PR on workspace branch (gh pr list --head <branch>)
    if pr exists:
        update_issue(status: "In Review")
        log "Fallback transition: {issue.simple_id} → In Review (session dead, PR found)"
    else:
        log warning "Stale agent: {issue.simple_id} — session dead, no PR found"
```

**Session liveness detection:** The VK server already manages sessions via `create_session` / `list_sessions`. The server should track session exit status (process exited, exit code) as part of the existing session lifecycle. The crash fallback queries this: if the session's executor process has exited, the session is dead. The specific mechanism (tmux session check, PID polling, or process exit callback) is an implementation detail for the `vibe-kanban` backend plan.

**Safety:**
- Only transitions issues in "In progress" (never touches "To do", "In Review", or "Done")
- Idempotent: if issue is already past "In progress", skip
- Does not retry or restart failed agents

### Component 3: Workspace archival (server-side periodic job)

**Location:** `vibe-kanban` backend (Rust)

**Schedule:** Every 10 minutes (configurable)

**Logic:**

```
for each workspace where archived == false and worktree_deleted == false:
    issue = find linked issue
    if issue is None or issue.status != "Done":
        skip
    
    pr = get PR for workspace branch (gh pr view --head <branch> --json state,mergedAt)
    
    if pr.state == "MERGED":
        # Verify worktree is clean
        if worktree has uncommitted changes:
            log warning "Cannot archive {workspace.name}: uncommitted changes"
            skip
        
        git worktree remove <container_ref>
        git push origin --delete <branch>
        update_workspace(archived: true)
        # worktree_deleted is set by delete_workspace or the remove operation
        log "Archived: {workspace.name} (PR merged)"
    
    elif pr.state == "CLOSED":
        # PR closed without merge — archive but warn
        git worktree remove <container_ref>
        update_workspace(archived: true)
        log warning "Archived: {workspace.name} (PR closed, NOT merged)"
    
    elif pr is None or pr.state == "OPEN":
        # Anomaly: issue is Done but PR isn't merged
        log warning "Anomaly: {workspace.name} — issue Done but PR not merged/missing"
        skip
```

**Safety:**
- Never deletes a worktree for an issue that isn't "Done"
- Never deletes a worktree with uncommitted changes
- Workspace record stays in the database (soft delete) — only the disk worktree is removed
- Remote branch is only deleted when PR is confirmed merged

## Status Flow

```
start_workspace          agent creates PR          operator reviews         operator merges PR
     |                        |                         |                         |
  To do  ──→  In progress  ──→  In Review  ──→  (manual review)  ──→  Done  ──→  [archived]
                          skill hook ^        ^ crash fallback           ^ archival job
```

| Transition | Trigger | Actor |
|------------|---------|-------|
| To do → In progress | `start_workspace` called | VK server |
| In progress → In Review | PR created | Agent (skill hook) or server (crash fallback) |
| In Review → Done | Operator satisfied | Operator (manual) |
| Done → archived | PR merged, worktree cleaned | Server (archival job) |

## Testing Strategy

### Skill hook
- Unit test: mock MCP calls, verify `update_issue` is called with correct status after PR creation
- Integration test: run `vk-execute` in a test workspace, verify issue transitions

### Crash fallback
- Test with a workspace where the session process has been killed but PR exists → verify transition
- Test with a dead session and no PR → verify warning logged, no transition
- Test with a live session → verify no action taken

### Workspace archival
- Test with a "Done" issue and merged PR → verify worktree removed, workspace archived, remote branch deleted
- Test with a "Done" issue and unmerged PR → verify warning, no deletion
- Test with uncommitted changes → verify skip with warning
- Test idempotency: run twice on the same workspace → second run is a no-op

## Implementation Plans

| Plan | Repo | File | Status | Depends on |
|------|------|------|--------|------------|
| Skill: agent completion hook | `derio-net/superpowers-for-vk` | `docs/superpowers/plans/2026-04-13-workspace-lifecycle-skill-hook.md` | Not Started | — |
| Backend: lifecycle jobs | `derio-net/vibe-kanban` | `docs/superpowers/plans/2026-04-13-workspace-lifecycle-backend-jobs.md` | Not Started | Skill hook (for full feature) |
| Workspace Lifecycle Skill Hook Implementation Plan |  | `docs/superpowers/plans/2026-04-13-workspace-lifecycle-skill-hook.md` | Complete | — |
