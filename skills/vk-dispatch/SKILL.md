---
name: vk-dispatch
description: >
  Dispatch a phase-structured plan to GitHub Issues with VK integration.
  Use when the user wants to create Issues from a plan, dispatch phases,
  or says "dispatch this plan", "send to VK", "create issues from plan",
  "dispatch phases", "break this plan into issues".
---

# VK Dispatch

## Overview

Reads a phase-structured plan file (created by `vk-plan`), creates one GitHub Issue per phase with sequential dependencies, adds each to the Derio Ops project board, and inserts tracking links back into the plan file.

**Announce at start:** "I'm using the vk-dispatch skill to dispatch this plan."

## Input

1. **Plan file path** — path to the plan markdown file (must have `## Phase N:` headers)
2. **Target repo** — which GitHub repo to create Issues in (e.g., `derio-net/content-factory`)
3. **VK project ID** — default: `90b1cb2f-f8fd-49a1-8b43-fc6a1eb2a0a1` (Derio Ops)

If the plan file path is not provided, ask for it. If the target repo is ambiguous, ask.

## Procedure

### Step 1: Parse the Plan File

Read the plan file and extract phases:

```bash
PLAN_FILE="<path>"

# Extract phase headers: lines matching "## Phase N: <name> [type]"
grep -n "^## Phase [0-9]" "$PLAN_FILE"
```

For each phase, extract:
- **Phase number** — from the header (e.g., `## Phase 2: Core Pipeline [agentic]` → 2)
- **Phase name** — text between `Phase N: ` and `[type]`
- **Phase type** — `manual` or `agentic` from the `[type]` tag
- **Phase body** — everything between this header and the next `## Phase` or end of file

Derive the **plan slug** from the filename:
- `2026-04-10-content-pipeline.md` → `content-pipeline`
- Strip the date prefix and `.md` extension

### Step 2: Check Idempotency

Before creating Issues, check for existing `<!-- Tracking: ... -->` comments in the plan file. If a phase already has a tracking comment:
1. Verify the linked Issue still exists on GitHub
2. If it exists, skip creation for that phase
3. If the Issue was deleted, remove the stale tracking comment and re-create

### Step 3: Create Issues

Maintain a `phase_num → issue_number` map for dependency resolution.

For each phase:

```bash
REPO="<target-repo>"
SLUG="<plan-slug>"
PHASE_NUM=<N>
PHASE_NAME="<name>"
PHASE_TYPE="<manual|agentic>"

# Issue title format: {slug}-{N}-{type}
TITLE="${SLUG}-${PHASE_NUM}-${PHASE_TYPE}"
```

#### Issue Body — Manual Phases

Manual phases get the full phase content verbatim as the Issue body. This is the operator runbook.

```markdown
# ${PHASE_NAME}

**Type:** Manual (operator runbook)
**Plan:** `${PLAN_FILE}`
**Phase:** ${PHASE_NUM}

---

${FULL_PHASE_BODY}
```

#### Issue Body — Agentic Phases

Agentic phases get a structured body that instructs the VK workspace agent:

```markdown
## Instruction

Use superpowers-for-vk:vk-execute to implement Phase ${PHASE_NUM} of this plan.

## Workspace

Repos: ${REPO}

## Dependencies

- Blocked by #${PREV_ISSUE_NUM}

---

**Plan file:** `${PLAN_FILE}`
**Phase:** ${PHASE_NUM} — ${PHASE_NAME}
```

The `## Dependencies` section references the Issue number of the previous phase. Phase 0 has no dependencies.

#### Labels

- Manual phases: label `manual` only (no `vk-ready` — operator must complete manually)
- Agentic phases: label `vk-ready` (signals VK to pick up the work)

**Important:** For agentic phases, create the Issue first WITHOUT the `vk-ready` label, then add the label after the body is set. This prevents VK from picking up an incomplete Issue.

```bash
# Create issue without vk-ready
ISSUE_URL=$(gh issue create \
  --repo "$REPO" \
  --title "$TITLE" \
  --body "$BODY" \
  2>&1 | tail -1)

# Extract issue number
ISSUE_NUM=$(echo "$ISSUE_URL" | grep -oP '\d+$')

# Record mapping
PHASE_TO_ISSUE[$PHASE_NUM]=$ISSUE_NUM

# Add vk-ready label for agentic phases (after body is set)
if [[ "$PHASE_TYPE" == "agentic" ]]; then
  gh issue edit "$ISSUE_NUM" --repo "$REPO" --add-label "vk-ready"
fi

# Add manual label for manual phases
if [[ "$PHASE_TYPE" == "manual" ]]; then
  gh issue edit "$ISSUE_NUM" --repo "$REPO" --add-label "manual"
fi
```

### Step 4: Add Issues to Project Board

```bash
PROJECT_NUM=$(gh project list --owner derio-net --format json | \
  jq -r '.projects[] | select(.title == "Derio Ops") | .number')

gh project item-add "$PROJECT_NUM" --owner derio-net --url "$ISSUE_URL"
```

### Step 5: Set Lifecycle State to `plan`

```bash
PROJECT_ID=$(gh project list --owner derio-net --format json | \
  jq -r ".projects[] | select(.number == $PROJECT_NUM) | .id")

ITEM_ID=$(gh project item-list "$PROJECT_NUM" --owner derio-net --format json | \
  jq -r ".items[] | select(.content.url == \"$ISSUE_URL\") | .id")

FIELD_ID=$(gh project field-list "$PROJECT_NUM" --owner derio-net --format json | \
  jq -r '.fields[] | select(.name == "Lifecycle") | .id')

PLAN_OPTION_ID=$(gh project field-list "$PROJECT_NUM" --owner derio-net --format json | \
  jq -r '.fields[] | select(.name == "Lifecycle") | .options[] | select(.name == "plan") | .id')

gh project item-edit \
  --project-id "$PROJECT_ID" \
  --id "$ITEM_ID" \
  --field-id "$FIELD_ID" \
  --single-select-option-id "$PLAN_OPTION_ID"
```

### Step 6: Insert Tracking Comments into Plan File

After each phase header, insert a tracking link:

Before:
```markdown
## Phase 2: Core Pipeline [agentic]
```

After:
```markdown
## Phase 2: Core Pipeline [agentic]
<!-- Tracking: https://github.com/derio-net/content-factory/issues/5 -->
```

Use the Edit tool for precise modifications.

### Step 7: Commit the Updated Plan

```bash
git add "$PLAN_FILE"
git commit -m "chore: link plan phases to GitHub Issues (vk-dispatch)"
```

### Step 8: Report Results

```
## Plan Dispatched

**Plan:** <plan title>
**Repo:** <repo>
**Phases dispatched:** N

| Phase | Type | Issue | State |
|-------|------|-------|-------|
| Phase 0: <name> | manual | <repo>#<num> | plan |
| Phase 1: <name> | agentic | <repo>#<num> | plan |
| Phase 2: <name> | manual | (skipped — tracking exists) | — |
```

## Error Handling

- **Plan file not found:** Report and stop.
- **No `## Phase` headers found:** Report "No phase headers found — was this plan created with vk-plan?" and stop.
- **`gh` auth failure:** Report and stop.
- **Issue creation fails for one phase:** Log the error, continue with remaining phases, report partial results.
- **Plan file not in a git repo:** Skip commit step, note in report.
- **Phase has no `[manual]` or `[agentic]` tag:** Report the untagged phase and stop. Don't guess.

## One Plan = One Dispatch

Each plan dispatches as a single unit. Never split a plan across multiple dispatches or repos. If a plan touches multiple repos, ask the user to split it first.

## Integration

- **Upstream:** `superpowers-for-vk:vk-plan` — creates the plan this skill dispatches
- **Downstream:** `superpowers-for-vk:vk-execute` — agents use this to implement agentic phases
- **Sync:** `superpowers-for-vk:vk-progress` — syncs Issue states back to plan checkboxes
