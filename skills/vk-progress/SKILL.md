````markdown
---
name: vk-progress
description: >
  Work lifecycle tracking — sync plan progress, query status boards, create/transition
  work items, health summaries, and audit. Absorbs work-lifecycle + progress-sync.
  Also syncs plan status back to spec index tables.
  Use when: "sync progress", "status board", "what's in progress", "what's broken",
  "update the plan", "health summary", "create work item", "transition state",
  "audit", "refresh plan status", "how far along is the plan".
---

# VK Progress — Work Lifecycle Tracking

## Overview

Unified work lifecycle skill. Five capabilities:

1. **Plan sync** — sync GitHub Issue/card states back to plan file checkboxes + spec index
2. **Status board** — query the project board, group by lifecycle state
3. **Create work item** — create new GitHub Issues with type labels and lifecycle state
4. **Transition state** — move items between lifecycle states with validation
5. **Health & audit** — stale items, blocked items, plan-vs-board drift

**Announce at start:** "I'm using vk-progress for [capability]."

## Profile Reading

Read the repo's profile config for lifecycle settings:

1. Look for `docs/superpowers/plan-config.yaml` in the repo root
2. Extract:
   - `header.status_values` — valid plan statuses (default: `[Not Started, In Progress, Complete]`)
   - `dispatch.owner` — GitHub owner/org (default: `derio-net`)
   - `dispatch.project_board` — project name (default: `"Derio Ops"`)
3. Export as shell variables for use throughout:

```bash
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PROFILE="$REPO_ROOT/docs/superpowers/plan-config.yaml"
if [ -f "$PROFILE" ]; then
  OWNER=$(sed -n '/^dispatch:/,/^[^ ]/{s/^  owner: *//p}' "$PROFILE" | head -1)
  PROJECT_BOARD=$(sed -n '/^dispatch:/,/^[^ ]/{s/^  project_board: *"\(.*\)"/\1/p}' "$PROFILE" | head -1)
fi
OWNER="${OWNER:-derio-net}"
PROJECT_BOARD="${PROJECT_BOARD:-Derio Ops}"
```

## Capability 1: Plan Sync

### Input

**Plan file path** — must have `<!-- Tracking: ... -->` comments from vk-dispatch.

If not provided, search for plan files with tracking comments and ask which one.

### Procedure

#### Step 1: Extract Tracking Links

```bash
PLAN_FILE="<path>"
grep -n "<!-- Tracking:" "$PLAN_FILE" | sed 's/.*<!-- Tracking: \(.*\) -->/\1/'
```

If no tracking comments: "No tracking links found — dispatch this plan with vk-dispatch first." Stop.

#### Step 2: Query Issue and VK States

For each tracked Issue URL, parse the owner and repo from the URL itself (don't assume a fixed org):

```bash
# URL format: https://github.com/<owner>/<repo>/issues/<number>
URL_OWNER=$(echo "$ISSUE_URL" | sed 's|https://github.com/\([^/]*\)/.*|\1|')
URL_REPO=$(echo "$ISSUE_URL" | sed 's|https://github.com/[^/]*/\([^/]*\)/.*|\1|')
NUMBER=$(echo "$ISSUE_URL" | sed 's|.*/issues/\([0-9]*\)|\1|')

IS_CLOSED=$(gh issue view "$NUMBER" --repo "$URL_OWNER/$URL_REPO" --json closed --jq '.closed')

PROJECT_NUM=$(gh project list --owner "$OWNER" --format json | \
  jq -r ".projects[] | select(.title == \"$PROJECT_BOARD\") | .number")

STATE=$(gh project item-list "$PROJECT_NUM" --owner "$OWNER" --format json | \
  jq -r ".items[] | select(.content.url == \"$ISSUE_URL\") | .fieldValues.nodes[] | select(.field.name == \"Lifecycle\") | .name")
```

#### Step 3: Map States to Checkboxes

| State | Checkbox |
|-------|----------|
| Issue closed | `- [x]` |
| deployed / healthy / retired | `- [x]` |
| in-progress / plan / blocked | `- [ ]` |
| degraded | `- [x]` (add note) |
| dead | `- [-]` (add note) |

#### Step 4: Update Plan File Checkboxes

For each phase with a tracking comment:
1. Find the `<!-- Tracking: ... -->` line and the phase header above it
2. Between this header and the next `## Phase` (or EOF), update checkboxes per state
3. **Never uncheck a manually checked box.** Progress only moves forward

#### Step 5: Update Plan Status Header

Read `header.status_values` from profile. Apply:
- All phases complete → last terminal status in profile (e.g., `Complete`, `Deployed`)
- Any phase started → `In Progress`
- None started → leave as-is

#### Step 6: Update Spec Index (if plan has a Spec header)

1. Extract `**Spec:**` path from the plan header
2. Resolve spec file (may be cross-repo — skip if not accessible)
3. Read the spec's `## Implementation Plans` section
4. Update the Status column for this plan's row
5. Commit the spec update separately:
   ```bash
   git -C "$SPEC_REPO_ROOT" add "$SPEC_FILE"
   git -C "$SPEC_REPO_ROOT" commit -m "docs: sync $PLAN_TITLE status to $NEW_STATUS (vk-progress)"
   ```

If the spec is cross-repo and not locally accessible, print a warning with the update the operator should apply manually.

#### Step 7: Add Sync Timestamp and Commit

```markdown
---
*Last progress sync: 2026-04-11T15:30:00Z*
```

```bash
git add "$PLAN_FILE"
git diff --cached --quiet || git commit -m "chore: sync plan progress from GitHub Issues (vk-progress)"
```

#### Step 8: Report

```
## Progress Sync

**Plan:** <title>
**Synced:** <timestamp>

| Phase | Type | Issue | Lifecycle | Checkbox |
|-------|------|-------|-----------|----------|

**Overall:** N/M phases complete
**Spec index:** updated at <spec-path>
```

## Capability 2: Status Board

Query the project board and display grouped by lifecycle state.

```bash
PROJECT_NUM=$(gh project list --owner "$OWNER" --format json | \
  jq -r ".projects[] | select(.title == \"$PROJECT_BOARD\") | .number")

gh project item-list "$PROJECT_NUM" --owner "$OWNER" --format json | \
  jq -r '.items[] | [.content.title, .content.url, (.fieldValues.nodes[] | select(.field.name == "Lifecycle") | .name) // "unset"] | @tsv'
```

Group by lifecycle state. Highlight items needing attention: dead, blocked, degraded, items with no lifecycle state.

### Output Format

```
## Status Board — <$PROJECT_BOARD>

### 🔴 Needs Attention
| Item | Repo | State | Issue |

### In Progress (N)
### Planned (N)
### Deployed / Healthy (N)
```

## Capability 3: Create Work Item

### Input
- Title, Repo (default from profile's `dispatch.default_repo`), Type (feature/bug/infra/skill/pipeline), Lifecycle (default: `idea`), Body

### Procedure

```bash
# $REPO is the short name (e.g., "willikins"); combine with $OWNER for the full slug
ISSUE_URL=$(gh issue create --repo "$OWNER/$REPO" --title "$TITLE" --body "$BODY" --label "$TYPE" 2>&1 | tail -1)
ISSUE_NUM=$(echo "$ISSUE_URL" | grep -oP '\d+$')

PROJECT_NUM=$(gh project list --owner "$OWNER" --format json | \
  jq -r ".projects[] | select(.title == \"$PROJECT_BOARD\") | .number")
gh project item-add "$PROJECT_NUM" --owner "$OWNER" --url "$ISSUE_URL"

# Set lifecycle state (field-edit pattern, same as vk-dispatch Step 5)
```

## Capability 4: Transition State

Move an Issue between lifecycle states with validation.

### Validation Rules

| From | Allowed To |
|------|------------|
| idea | spec, dead |
| spec | plan, dead |
| plan | in-progress, blocked, dead |
| blocked | in-progress, dead |
| in-progress | deployed, blocked, dead |
| deployed | healthy, degraded, dead |
| healthy | degraded, retired |
| degraded | healthy, dead, retired |
| dead | (terminal) |
| retired | (terminal) |

Constraints:
- `spec → plan` requires a plan file to exist
- `plan → in-progress` should have tracking comments present (i.e. was dispatched)

### Procedure

```bash
CURRENT_STATE=<query from project board>
# Validate transition; if invalid, report allowed targets
# Apply via field-edit (same pattern as vk-dispatch Step 5)
```

## Capability 5: Health & Audit

### Health Summary

Cross-reference board with Grafana alerts:

```bash
curl -s -H "Authorization: Bearer $GRAFANA_API_KEY" \
  "https://grafana.frank.derio.net/api/alertmanager/grafana/api/v2/alerts?active=true" | \
  jq -r '.[] | [.labels.alertname, .status.state] | @tsv'
```

Flag: deployed items with firing alerts; dead/degraded items without alerts.

### Audit

Drift checks:
- Plans with `**Status:** Complete` but Issues still open
- Issues closed but plan checkboxes unchecked
- In-progress items idle >7 days
- Dispatched plans where Issues were deleted
- **Spec index drift:** plan status differs from spec index Status column

### Output

```
## Health Summary

### Alerts Firing (N)
### Board Anomalies
- N items in-progress >7 days
- N plans with status/board drift
- N items missing lifecycle state
- N spec index entries out of sync
```

## Error Handling

- **No tracking links (sync):** Suggest running vk-dispatch first
- **Issue not found:** Note in report, leave checkbox unchanged
- **gh auth failure:** Report and stop
- **Spec not accessible (cross-repo):** Skip spec index update, warn with manual patch
- **Grafana unavailable:** Skip alert cross-reference

## Safety

- Never mark complete unless terminal state
- Never uncheck a manually checked box
- Progress only moves forward
- Spec index updates are additive — never remove rows

## Integration

- **Upstream:** vk-dispatch created the tracking links
- **Execution:** vk-execute agents whose progress this tracks
- **Plan:** vk-plan created the plan file and seeded the spec index
````
