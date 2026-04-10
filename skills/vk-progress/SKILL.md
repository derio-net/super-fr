---
name: vk-progress
description: >
  Sync GitHub Issue and VK card states back to plan file checkboxes.
  Use when the user wants to update plan progress, check completion,
  or says "sync progress", "update the plan", "refresh plan status",
  "how far along is the plan".
---

# VK Progress

## Overview

Reads GitHub Issue states and VK card statuses for tracked phases, then updates the plan file checkboxes to reflect reality. This is the reverse of `vk-dispatch` — it syncs external state back to the plan document.

**Announce at start:** "I'm using the vk-progress skill to sync plan progress."

## Input

1. **Plan file path** — the plan file to sync (must have `<!-- Tracking: ... -->` comments from `vk-dispatch`)

If the path is not provided, search for plan files with tracking comments and ask which one to sync.

## Procedure

### Step 1: Extract Tracking Links

```bash
PLAN_FILE="<path>"

# Find all tracking comments and extract Issue URLs
grep -n "<!-- Tracking:" "$PLAN_FILE" | \
  sed 's/.*<!-- Tracking: \(.*\) -->/\1/'
```

If no tracking comments found, report "No tracking links found — dispatch this plan with vk-dispatch first" and stop.

### Step 2: Query Issue and VK States

For each tracked Issue URL:

```bash
# Extract repo and issue number from URL
# URL format: https://github.com/derio-net/<repo>/issues/<number>
REPO=$(echo "$ISSUE_URL" | sed 's|.*/derio-net/\([^/]*\)/.*|\1|')
NUMBER=$(echo "$ISSUE_URL" | sed 's|.*/issues/\([0-9]*\)|\1|')

# Get Issue state (open/closed)
IS_CLOSED=$(gh issue view "$NUMBER" --repo "derio-net/$REPO" --json closed --jq '.closed')

# Get lifecycle state from project board
PROJECT_NUM=$(gh project list --owner derio-net --format json | \
  jq -r '.projects[] | select(.title == "Derio Ops") | .number')

STATE=$(gh project item-list "$PROJECT_NUM" --owner derio-net --format json | \
  jq -r ".items[] | select(.content.url == \"$ISSUE_URL\") | .fieldValues.nodes[] | select(.field.name == \"Lifecycle\") | .name")
```

Optionally, also check the VK card status via MCP `list_issues` with a search matching the Issue title, if VK MCP is available. This provides additional signal (e.g., VK may show "Done" before the GitHub Issue is closed).

### Step 3: Map States to Checkbox Status

| State | Checkbox | Meaning |
|-------|----------|---------|
| Issue closed | `- [x]` | Complete (terminal) |
| Lifecycle: deployed | `- [x]` | Complete |
| Lifecycle: healthy | `- [x]` | Complete |
| Lifecycle: retired | `- [x]` | Intentionally done |
| Lifecycle: in-progress | `- [ ]` | In progress (don't check yet) |
| Lifecycle: plan | `- [ ]` | Not started |
| Lifecycle: blocked | `- [ ]` | Blocked |
| Lifecycle: degraded | `- [x]` | Complete but degraded (add note) |
| Lifecycle: dead | `- [-]` | Dead (add note) |
| VK card: Done | `- [x]` | Complete (if Issue not yet closed) |

### Step 4: Update Plan File Checkboxes

For each phase with a tracking comment:

1. Find the `<!-- Tracking: ... -->` comment line number
2. Find the phase header immediately above it (`## Phase N:`)
3. Between this header and the next `## Phase` (or end of file), update checkboxes:
   - **Complete states** (deployed/healthy/retired/closed/Done): change all `- [ ]` to `- [x]`
   - **In progress:** leave checkboxes as-is (individual step tracking is done by the executing agent)
   - **Dead:** change all unchecked to `- [-]`
   - **Not started / blocked:** leave as-is
4. **Never uncheck a manually checked box.** Progress only moves forward.

Use the Edit tool for precise modifications.

### Step 5: Update Plan Status Header

If all phases are complete (all checkboxes checked), update the plan's `**Status:**` line:
- `Not Started` or `In Progress` → `Complete`

If any phase has started but not all are complete:
- `Not Started` → `In Progress`

### Step 6: Add Sync Timestamp

At the bottom of the plan file, add or update a sync timestamp:

```markdown
---
*Last progress sync: 2026-04-10T15:30:00Z*
```

If a previous sync timestamp exists, replace it.

### Step 7: Commit if Changes Were Made

```bash
git add "$PLAN_FILE"
git diff --cached --quiet || git commit -m "chore: sync plan progress from GitHub Issues (vk-progress)"
```

### Step 8: Report Results

```
## Progress Sync

**Plan:** <plan title>
**Synced:** 2026-04-10T15:30:00Z

| Phase | Type | Issue | Lifecycle | Checkbox |
|-------|------|-------|-----------|----------|
| Phase 0: <name> | manual | <repo>#<num> | deployed | [x] |
| Phase 1: <name> | agentic | <repo>#<num> | in-progress | [ ] |
| Phase 2: <name> | manual | <repo>#<num> | plan | [ ] |

**Overall:** 1/3 phases complete, 1 in progress, 1 planned
```

## Error Handling

- **No tracking links:** Report and suggest running `vk-dispatch` first.
- **Issue not found:** Note it in the report, leave checkbox unchanged.
- **Issue not on project board:** Use Issue closed/open state as fallback.
- **Plan file not writable:** Report changes that would be made without writing.
- **Git not available:** Skip commit step, note in report.

## Safety

- Never mark a checkbox as complete unless the Issue is in a terminal state (deployed, healthy, retired, closed, Done).
- Never uncheck a checkbox that was manually checked.
- If in doubt about a state mapping, leave the checkbox unchanged and note it in the report.

## Integration

- **Upstream:** `superpowers-for-vk:vk-dispatch` — created the tracking links this skill reads
- **Execution:** `superpowers-for-vk:vk-execute` — the agents whose progress this skill tracks
- **Plan:** `superpowers-for-vk:vk-plan` — created the plan file with phase structure
