# Plugin Canonical Skills Implementation Plan

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** `willikins/docs/superpowers/specs/2026-04-10-vk-skills-harmonization-design.md`
**Status:** Not Started

**Goal:** Rewrite the four superpowers-for-vk skills (vk-plan, vk-dispatch, vk-execute, vk-progress) to be profile-aware and standalone, add the canonical validator, install script, and bootstrap the plugin's own plans infrastructure. Ship as v0.2.0.

**Architecture:** vk-plan absorbs writing-plans quality standards and becomes the canonical plan skill. vk-progress absorbs work-lifecycle board queries. All four skills read `docs/superpowers/plan-config.yaml` from the repo they're invoked in. Ships a canonical validator that per-repo wrappers delegate to, an install.sh for user-level installation, and a minimal plans directory for this repo's own meta-work.

**Tech Stack:** Claude Code skills (Markdown), Bash (validator, install), YAML (profile), `gh` CLI, `jq`

**Cross-plan note:** This plan is Plan A of the VK Skills Harmonization feature. See the spec's "Implementation Plans" section for sibling plans in frank and willikins. Plans B and C depend on this plan being merged and installed at user level.

---

## Phase 0: Canonical Skills Rewrite [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/1 -->

Rewrite all four skills. This is the core of the harmonization work.

### Task 1: Rewrite vk-plan as standalone canonical skill

**Files:**
- Modify: `skills/vk-plan/SKILL.md`

vk-plan becomes standalone (no longer wraps writing-plans), absorbs all quality standards, adds profile reading, adds spec index maintenance, and offers three execution paths.

- [ ] **Step 1: Replace skills/vk-plan/SKILL.md with the new standalone version**

Write the full file content. **Outer fence uses 5 backticks** so that the inner 4-backtick Task Structure example (and its 3-backtick code blocks) nest without collision:

`````markdown
---
name: vk-plan
description: >
  Canonical plan skill for derio-net repos. Write phase-structured plans with
  manual/agentic phase tagging. Profile-driven per-repo behavior via plan-config.yaml.
  Maintains spec-to-plans forward index. Use when: "write a plan", "vk plan",
  "create a plan", "phase-structured plan", "plan for vk", "create a dispatchable plan".
---

# VK Plan — Canonical Plan Skill

## Overview

Write comprehensive, phase-structured implementation plans assuming the engineer has zero context for the codebase. Document everything: which files to touch, complete code, testing, verification. Give them the whole plan as bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

**This skill replaces `superpowers:writing-plans`.** It produces the same quality output with added phase structure, profile-driven per-repo behavior, and spec index maintenance.

**Announce at start:** "I'm using vk-plan to create the implementation plan."

**Context:** Prefer running in an isolated worktree when the work could conflict with other changes on `main`. The brainstorming skill may create one; if not, it's worth creating one manually via `git worktree add`. Not a hard requirement — most plans can be written on `main` without issue.

## Profile Reading

Before writing any plan, read the repo's profile config:

1. Look for `docs/superpowers/plan-config.yaml` in the repo root
2. If found, use it to drive: filename pattern, required headers, status values, post-deploy phase, dispatch config
3. If not found, use defaults: simple filename (`YYYY-MM-DD-{name}.md`), Status-only header, dispatch enabled

```bash
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PROFILE="$REPO_ROOT/docs/superpowers/plan-config.yaml"
if [ -f "$PROFILE" ]; then
  echo "Profile found: $PROFILE"
else
  echo "No profile — using defaults"
fi
```

### Filename Generation

Use the profile's `plan.filename` pattern:
- `YYYY-MM-DD-{name}.md` — resolve `{name}` from the feature name (kebab-case)
- `YYYY-MM-DD--{layer}--{details}.md` — resolve `{layer}` from `docs/layers.yaml` registry, `{details}` from the feature name

### Header Generation

Include fields listed in `header.required`. Common fields:
- `**Spec:**` — backtick-enclosed path to the design spec (may be cross-repo, e.g. `willikins/docs/superpowers/specs/…`)
- `**Status:**` — one of `header.status_values` (default: Not Started)

### Post-Deploy Phase

If the profile defines `post_deploy` and the plan is NOT in `post_deploy.skip_when` categories, append a final manual phase with the configured steps. Phase name from `post_deploy.name`, type always `[manual]`.

## Spec Index Maintenance

**This is a required post-write step for any plan that has a `**Spec:**` header.**

A spec that spans multiple repos generates multiple plans (one per target repo). Without forward references, reconstructing "what was built for this spec" requires scanning every repo for backlinks. The spec owns the index.

### Procedure

After writing the plan:

1. Resolve the spec file path from the `**Spec:**` header
   - If the path is repo-relative (starts without `/`), interpret against the plan's repo root
   - If the path is prefixed with another repo name (e.g., `willikins/docs/...`), resolve against `~/repos/<repo>/` or the configured cross-repo workspace root
2. If the spec file is not accessible (cross-repo, no local clone): skip the index update, warn the user, and print the entry they need to add manually
3. Read the spec file. Look for an `## Implementation Plans` section (h2 header, exact text)
4. **If the section exists:**
   - Look for an existing row matching this plan's file path
   - If found: update its Status column to match the plan's current Status
   - If not found: append a new row to the table
5. **If the section does not exist:**
   - Create it immediately before the `## What Stays Unchanged` section (fallback: before the first trailing section; final fallback: end of file)
   - Initialize with a markdown table:
     ```markdown
     ## Implementation Plans

     | Plan | Repo | File | Status | Depends on |
     |------|------|------|--------|------------|
     | <plan-title> | `<owner>/<repo>` | `<repo-relative-path>` | Not Started | — |
     ```
6. Commit the spec update separately from the plan file:
   ```bash
   git -C "$SPEC_REPO_ROOT" add "$SPEC_FILE"
   git -C "$SPEC_REPO_ROOT" commit -m "docs: index $PLAN_TITLE in implementation plans (vk-plan)"
   ```

If the spec lives in a different repo than the plan, the commit happens in the spec's repo. Warn the user if they need to push that repo separately.

### Entry Format

| Column | Value | Example |
|--------|-------|---------|
| Plan | Short title (drop "Implementation Plan" suffix) | `Plugin canonical skills` |
| Repo | `owner/repo` | `derio-net/superpowers-for-vk` |
| File | Repo-relative plan file path in backticks | `` `docs/superpowers/plans/2026-04-11-plugin-canonical-skills.md` `` |
| Status | Plan's `**Status:**` value | `Not Started` |
| Depends on | Cross-plan dependencies (free text) | `A merged` or `—` |

## Scope Check

If the spec covers multiple independent subsystems, it should have been broken into sub-project specs during brainstorming. Each plan should produce working, testable software on its own.

**Cross-repo features:** If the feature spans multiple repos, write multiple plans — one per target repo — not a single plan with cross-repo phases. Each plan lives in its target repo. The spec's Implementation Plans section is the coordination layer.

## File Structure

Before defining tasks, map out which files will be created or modified and what each one is responsible for. Prefer smaller, focused files. Files that change together should live together — split by responsibility, not layer. In existing codebases, follow established patterns.

## Phase Structure

Plans are organized into sequential phases. Each phase header:

```markdown
## Phase N: <name> [manual|agentic]
```

### Rules

1. **Phases are sequential** — Phase N+1 depends on Phase N being complete
2. **Each phase is tagged** `[manual]` or `[agentic]`:
   - **`[manual]`** — Operator runbook. Requires human hands: UIs, accounts, interactive auth
   - **`[agentic]`** — Automatable. Writing code, running tests, creating files, committing
3. **Each agentic phase = one PR.** Scope so the PR is reviewable and self-contained
4. **Manual phase Issues are dispatched but not `vk-ready`.** VK agents will not pick them up for autonomous work. The Issue body is the operator runbook; a human executes the steps. Closing a manual phase Issue is itself a manual step today — there is no automation that closes it based on runbook completion
5. **Backend-agnostic:** `[manual]`/`[agentic]` describe work type, not execution target
6. **Single-repo scope:** all phases of a plan target the same repo (the plan's home repo). Cross-repo features use multiple plans

### Manual Phase Content

Manual phases must be complete operator runbooks:
- Exact URLs to visit
- Exact commands to run (with expected output)
- Exact file paths and environment variable names
- Verification steps
- Why each step connects to the next phase

### Agentic Phase Content

Agentic phases use the Phase > Task > Step hierarchy:

```markdown
## Phase N: <name> [agentic]

### Task 1: <component>

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

- [ ] **Step 1: Write the failing test**
...
- [ ] **Step 5: Commit**

### Task 2: <component>
...
```

## Bite-Sized Task Granularity

Each step is one action (2-5 minutes):
- "Write the failing test" — step
- "Run it to make sure it fails" — step
- "Implement the minimal code" — step
- "Run tests and verify they pass" — step
- "Commit" — step

## Task Structure

````markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

- [ ] **Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## Test-Driven Development

**TDD is the default, not the exception.** In practice, AI agents executing plans often either test last or skip tests altogether. Counter this explicitly when writing plans:

- **Test first, always.** The first step of any implementation task is "Write the failing test." Not "Write the implementation and then a test for it." Not "Skip the test, it's trivial."
- **Run the test and see it fail** before writing the implementation. This catches two classes of bug: tests that pass without the feature (false positives), and tests that run against stale state.
- **Minimal implementation to make the test pass.** No speculative generality. No extra methods "while we're in there."
- **Refactor only after green.** With the test as a safety net, cleanup is safe.
- **Commit often.** One task = one logical change = one commit. Don't batch unrelated changes.

### Walking Skeleton Pattern

When the architecture is new or the integration points are uncertain, use the walking-skeleton pattern: build the smallest possible end-to-end implementation that exercises every layer of the system, then grow it feature by feature.

Prefer a walking skeleton when:
- You're bootstrapping a new service, plugin, or tool (Phase 0 of a new repo)
- Integration across layers is the risky part — more so than any individual layer's internals
- The plan starts with "create project scaffolding" or "wire up CI/CD"

A walking skeleton task looks like: "Write the smallest test that exercises the full pipeline end-to-end (input → each layer → output). Make it pass with stub implementations everywhere. Subsequent tasks replace stubs with real implementations, one at a time, each with its own failing test first."

When NOT to use walking skeleton: well-understood domains where each component has clear contracts, or changes to existing code where the architecture is already proven.

## No Placeholders

Every step must contain the actual content. These are **plan failures** — never write them:
- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases"
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the code)
- Steps that describe what to do without showing how
- References to types, functions, or methods not defined in any task

## Plan Document Header

```markdown
# [Feature Name] Implementation Plan

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** `path/to/spec.md`  <!-- if profile requires Spec -->
**Status:** Not Started

**Goal:** [One sentence]
**Architecture:** [2-3 sentences]
**Tech Stack:** [Key technologies]

---
```

- Include `**Spec:**` only if profile lists it in `header.required`
- Status values come from `header.status_values` in profile

## Self-Review

After writing the complete plan:

1. **Spec coverage:** point to a task for each spec requirement. List gaps.
2. **Placeholder scan:** find and fix any "No Placeholders" patterns above
3. **Type consistency:** types/signatures/names match across tasks
4. **Phase tagging:** every phase has `[manual]` or `[agentic]`
5. **Phase sequencing:** each phase genuinely depends on the previous
6. **Manual completeness:** operator can follow without asking questions
7. **Agentic scoping:** ≤ ~5 files, ≤ ~8 tasks per phase; split if bigger
8. **Single-repo:** all agentic phases target the same repo

Fix issues inline.

## Execution Handoff

After saving the plan AND updating the spec index, offer three execution paths:

**"Plan complete and saved to `<path>`. Spec index updated at `<spec-path>`. Three execution options:**

**1. Dispatch to VK** — Create GitHub Issues per phase, VK agents pick up agentic phases

**2. Subagent-Driven (in-session)** — Fresh subagent per task, review between tasks

**3. Inline Execution** — Execute tasks in this session with checkpoints

**Which approach?"**

- **Dispatch:** Invoke `vk-dispatch` with the plan file path
- **Subagent-Driven:** Invoke `superpowers:subagent-driven-development`
- **Inline:** Invoke `superpowers:executing-plans`

## Save Location

Use profile's `plan.save_to` directory. Default: `docs/superpowers/plans/`

Filename: generated from profile's `plan.filename` pattern with today's date and feature name.

## Integration

- **Upstream:** brainstorming feeds into vk-plan (via user-level rule redirect)
- **Downstream:** vk-dispatch dispatches phases to GitHub Issues
- **Execution:** vk-execute (agentic phases), subagent-driven-development, executing-plans
- **Tracking:** vk-progress syncs Issue states back to plan checkboxes AND updates spec index status
`````

- [ ] **Step 2: Verify the new skill**

```bash
wc -l skills/vk-plan/SKILL.md
# Expected: ~330-380 lines (absorbs writing-plans + spec index + TDD emphasis)
grep -q "Spec Index Maintenance" skills/vk-plan/SKILL.md && echo "OK: spec index"
grep -q "Profile Reading" skills/vk-plan/SKILL.md && echo "OK: profile"
grep -q "No Placeholders" skills/vk-plan/SKILL.md && echo "OK: quality"
grep -q "Single-repo scope" skills/vk-plan/SKILL.md && echo "OK: repo-scope rule"
grep -q "Three execution" skills/vk-plan/SKILL.md && echo "OK: 3 paths"
grep -q "Walking Skeleton" skills/vk-plan/SKILL.md && echo "OK: walking skeleton"
grep -q "Test-Driven Development" skills/vk-plan/SKILL.md && echo "OK: TDD section"
```

- [ ] **Step 3: Commit**

```bash
git add skills/vk-plan/SKILL.md
git commit -m "feat: rewrite vk-plan as standalone canonical skill

Absorbs superpowers:writing-plans quality standards, adds profile-driven
behavior via plan-config.yaml, enforces single-repo plan scope, and
maintains the spec-to-plans forward index after writing any plan that
references a spec. Replaces writing-plans as the canonical plan skill."
```

### Task 2: Add profile reading to vk-dispatch

**Files:**
- Modify: `skills/vk-dispatch/SKILL.md`

The current vk-dispatch hardcodes "Derio Ops" project and label names. Update it to read these from the profile.

- [ ] **Step 1: Add Profile Reading section**

Insert a new `## Profile Reading` section immediately after `## Overview`:

````markdown
## Profile Reading

Before dispatching, read the target repo's dispatch config:

1. Look for `docs/superpowers/plan-config.yaml` in the repo root
2. Extract dispatch settings:
   - `dispatch.owner` — GitHub owner/org (default: `derio-net`)
   - `dispatch.project_board` — project name (default: `"Derio Ops"`)
   - `dispatch.default_repo` — fallback repo slug `<owner>/<repo>` (default: plan's home repo)
   - `dispatch.labels.agentic` — label for agentic phases (default: `"vk-ready"`)
   - `dispatch.labels.manual` — label for manual phases (default: `"manual"`)
3. If `dispatch: false` in profile, **refuse to dispatch**: report "Dispatch disabled for this repo in plan-config.yaml" and stop

```bash
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PROFILE="$REPO_ROOT/docs/superpowers/plan-config.yaml"
if [ -f "$PROFILE" ]; then
  DISPATCH_DISABLED=$(sed -n '/^dispatch:/,/^[^ ]/p' "$PROFILE" | grep -c "^dispatch: false" || true)
  if [ "$DISPATCH_DISABLED" -gt 0 ]; then
    echo "Dispatch disabled for this repo"
    exit 0
  fi
  OWNER=$(sed -n '/^dispatch:/,/^[^ ]/{s/^  owner: *//p}' "$PROFILE" | head -1)
  PROJECT_BOARD=$(sed -n '/^dispatch:/,/^[^ ]/{s/^  project_board: *"\(.*\)"/\1/p}' "$PROFILE" | head -1)
  DEFAULT_REPO=$(sed -n '/^dispatch:/,/^[^ ]/{s/^  default_repo: *//p}' "$PROFILE" | head -1)
  AGENTIC_LABEL=$(sed -n '/labels:/,/^[^ ]/{s/^    agentic: *//p}' "$PROFILE" | head -1)
  MANUAL_LABEL=$(sed -n '/labels:/,/^[^ ]/{s/^    manual: *//p}' "$PROFILE" | head -1)
fi

OWNER="${OWNER:-derio-net}"
PROJECT_BOARD="${PROJECT_BOARD:-Derio Ops}"
AGENTIC_LABEL="${AGENTIC_LABEL:-vk-ready}"
MANUAL_LABEL="${MANUAL_LABEL:-manual}"
```

**Single-repo rule:** all phases of a plan dispatch to the same repo (the plan's home repo, or the profile's `default_repo`). If the operator passes a different repo as input, warn and confirm. A plan spanning multiple repos should have been split into multiple plans per spec.
````

- [ ] **Step 2: Replace hardcoded values with profile variables**

Throughout the rest of `skills/vk-dispatch/SKILL.md`, replace hardcoded literals with the profile variables:
- Literal `"Derio Ops"` → `"$PROJECT_BOARD"`
- Literal `"vk-ready"` → `"$AGENTIC_LABEL"`
- Literal `"manual"` → `"$MANUAL_LABEL"`
- Literal `--owner derio-net` → `--owner "$OWNER"`
- Literal `derio-net/$REPO` → `$OWNER/$REPO`

In Step 3 (Create Issues), update the label block:
```bash
if [[ "$PHASE_TYPE" == "agentic" ]]; then
  gh issue edit "$ISSUE_NUM" --repo "$REPO" --add-label "$AGENTIC_LABEL"
fi

if [[ "$PHASE_TYPE" == "manual" ]]; then
  gh issue edit "$ISSUE_NUM" --repo "$REPO" --add-label "$MANUAL_LABEL"
fi
```

In Step 4 (Add to Project Board), replace the hardcoded owner and project title lookup:
```bash
PROJECT_NUM=$(gh project list --owner "$OWNER" --format json | \
  jq -r ".projects[] | select(.title == \"$PROJECT_BOARD\") | .number")
```

- [ ] **Step 3: Update frontmatter description**

```yaml
---
name: vk-dispatch
description: >
  Dispatch a phase-structured plan to GitHub Issues with profile-driven config.
  Reads dispatch settings from plan-config.yaml (project board, labels, target repo).
  Enforces single-repo plan scope — reject if plan references cross-repo phases.
  Use when: "dispatch this plan", "send to VK", "create issues from plan",
  "dispatch phases", "break this plan into issues".
---
```

- [ ] **Step 4: Verify**

```bash
grep -q "Profile Reading" skills/vk-dispatch/SKILL.md && echo "OK: profile section"
grep -q "dispatch: false" skills/vk-dispatch/SKILL.md && echo "OK: opt-out"
grep -q "Single-repo rule" skills/vk-dispatch/SKILL.md && echo "OK: repo rule"
grep -q 'AGENTIC_LABEL' skills/vk-dispatch/SKILL.md && echo "OK: label var"
grep -q '\$OWNER' skills/vk-dispatch/SKILL.md && echo "OK: owner var"
# Confirm no remaining hardcoded derio-net or Derio Ops literals
! grep -E '(--owner derio-net|"Derio Ops")' skills/vk-dispatch/SKILL.md && echo "OK: no hardcoded literals" || echo "FAIL: hardcoded refs remain"
```

- [ ] **Step 5: Commit**

```bash
git add skills/vk-dispatch/SKILL.md
git commit -m "feat: add profile-aware dispatch config to vk-dispatch

Reads dispatch.project_board, dispatch.labels, dispatch.default_repo from
plan-config.yaml. Refuses dispatch if dispatch: false in profile. Enforces
single-repo plan scope."
```

### Task 3: Rewrite vk-progress to absorb work-lifecycle

**Files:**
- Modify: `skills/vk-progress/SKILL.md`

The current vk-progress only does plan-to-Issue sync. Absorb all work-lifecycle capabilities: status board, create work item, transition state, health summary, audit.

- [ ] **Step 1: Replace skills/vk-progress/SKILL.md with the expanded version**

Write the full file:

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

- [ ] **Step 2: Verify**

```bash
wc -l skills/vk-progress/SKILL.md
# Expected: ~260-300 lines
grep -c "## Capability" skills/vk-progress/SKILL.md
# Expected: 5
grep -q "Spec Index" skills/vk-progress/SKILL.md && echo "OK: spec index sync"
grep -q "Status Board" skills/vk-progress/SKILL.md && echo "OK: status board"
grep -q "Create Work Item" skills/vk-progress/SKILL.md && echo "OK: create"
grep -q "Transition State" skills/vk-progress/SKILL.md && echo "OK: transition"
grep -q "Health" skills/vk-progress/SKILL.md && echo "OK: health"
```

- [ ] **Step 3: Commit**

```bash
git add skills/vk-progress/SKILL.md
git commit -m "feat: absorb work-lifecycle into vk-progress

Adds 4 capabilities beyond plan sync: status board, create work item,
transition state, health & audit. Profile-aware via plan-config.yaml.
Syncs plan status to spec index on plan sync. Replaces willikins skills:
work-lifecycle, progress-sync."
```

### Task 4: Update vk-execute for Phase > Task > Step hierarchy

**Files:**
- Modify: `skills/vk-execute/SKILL.md`

**Note on profile reading:** vk-execute does NOT need to read the profile. The Phase > Task > Step markers (`## Phase`, `### Task`, `- [ ] **Step`) are invariants across all repos — not configurable per-profile. The `structure:` section has been removed from the profile schema to reflect this. If future work introduces per-repo structure variations, vk-execute would need profile reading at that point.

- [ ] **Step 1: Update the description and procedure**

Update the frontmatter:
```yaml
---
name: vk-execute
description: >
  Execute an agentic phase from a VK-dispatched plan. Understands Phase > Task > Step
  hierarchy. Agent-facing skill — not directly invoked by the operator. VK workspace
  agents use this to implement their assigned phase.
---
```

Update "## How It Works" to:
```markdown
## How It Works

This skill wraps `superpowers:executing-plans` (or `superpowers:subagent-driven-development` if subagents are available) with phase-scoping constraints. The agent reads its assigned Phase, iterates through Tasks within the Phase, and executes Steps within each Task. Never touches other phases.

The plan file lives in the same repo as the workspace (single-repo plan rule). If the Issue references a plan file that doesn't exist in the workspace, stop and report — the Issue is likely misconfigured or the workspace is cloned from the wrong repo.
```

Update "### Step 3: Read and Scope the Plan":
```markdown
### Step 3: Read and Scope the Plan

1. Read the plan file at the path from the Issue body (path is repo-relative)
2. Locate the assigned phase: `## Phase <N>:`
3. Extract only the Tasks within this Phase:
   - Tasks are `### Task N:` headers
   - Steps are `- [ ] **Step N:**` checkboxes within each Task
   - A Phase typically has 1-8 Tasks, each with 3-8 Steps
4. Ignore all other phases — they belong to other agents or the operator
```

Update "### Step 5: Update Plan Checkboxes":
```markdown
### Step 5: Update Plan Checkboxes

As each Step within each Task completes, update the plan file:
- Change `- [ ]` to `- [x]` for completed Steps
- Only update checkboxes within the assigned Phase
- Never touch checkboxes in other Phases
- After completing all Steps in a Task, verify the Task is fully checked before moving to the next Task. Tasks that have explicitly ignored/skipped, after confirmation from the operator, need to be marked with `- [-]` and a comment explaining the decision must be added
```

- [ ] **Step 2: Verify**

```bash
grep -q "Phase > Task > Step" skills/vk-execute/SKILL.md && echo "OK: hierarchy"
grep -q "### Task N:" skills/vk-execute/SKILL.md && echo "OK: task awareness"
grep -q "single-repo plan rule" skills/vk-execute/SKILL.md && echo "OK: repo rule"
```

- [ ] **Step 3: Commit**

```bash
git add skills/vk-execute/SKILL.md
git commit -m "feat: update vk-execute for Phase > Task > Step hierarchy

Explicitly documents the three-level hierarchy and the single-repo plan rule.
Plan file must live in the same repo as the workspace."
```

---

## Phase 1: Plugin Infrastructure [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/2 -->

Bootstrap the plugin's own plan infrastructure, ship the canonical validator, install script, and release v0.2.0.

### Task 1: Create plan-config.yaml for superpowers-for-vk

**Files:**
- Create: `docs/superpowers/plan-config.yaml`

- [ ] **Step 1: Write the minimal profile**

```yaml
plan:
  filename: "YYYY-MM-DD-{name}.md"
  save_to: docs/superpowers/plans/

header:
  required:
    - Spec
    - Status
  status_values:
    - Not Started
    - In Progress
    - Complete

dispatch:
  target: github-issues
  owner: derio-net
  project_board: "Derio Ops"
  default_repo: derio-net/superpowers-for-vk
  labels:
    agentic: vk-ready
    manual: manual
```

**Note:** No `structure:` section — the `## Phase` / `### Task` / `- [ ] **Step` markers are invariants across all profiles, hardcoded in vk-plan and vk-execute. `dispatch.owner` is new (previously hardcoded as `derio-net`).

- [ ] **Step 2: Verify YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('docs/superpowers/plan-config.yaml'))" && echo "Valid YAML"
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plan-config.yaml
git commit -m "feat: add plan-config.yaml for superpowers-for-vk

Minimal profile: simple filename, Spec+Status headers, Derio Ops dispatch.
Bootstraps the plugin repo's own plan infrastructure."
```

### Task 2: Create canonical validator script

**Files:**
- Create: `scripts/validate-plans.sh`

- [ ] **Step 1: Write the validator**

```bash
mkdir -p scripts
```

Write `scripts/validate-plans.sh`:

```bash
#!/usr/bin/env bash
# Canonical plan validator — profile-driven.
# Ships with superpowers-for-vk plugin. Per-repo thin wrappers call this.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ERRORS=()
PROFILE=""

FILES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    *) FILES+=("$1"); shift ;;
  esac
done

if [ -z "$PROFILE" ]; then
  PROFILE="$REPO_ROOT/docs/superpowers/plan-config.yaml"
fi

if [ -f "$PROFILE" ]; then
  FILENAME_PATTERN=$(sed -n '/^plan:/,/^[^ ]/{ s/^  filename: *"\(.*\)"/\1/p }' "$PROFILE" | head -1)
  REQUIRED_HEADERS=$(sed -n '/^header:/,/^[^ ]/{/^  required:/,/^  [^ ]/{/^    - /{ s/^    - //p }}}' "$PROFILE")
  STATUS_VALUES=$(sed -n '/^header:/,/^[^ ]/{/status_values:/,/^  [^ ]/{/^    - /{ s/^    - //p }}}' "$PROFILE")
else
  FILENAME_PATTERN="YYYY-MM-DD-{name}.md"
  REQUIRED_HEADERS="Status"
  STATUS_VALUES=""
fi

if ! echo "$REQUIRED_HEADERS" | grep -q "Status"; then
  REQUIRED_HEADERS="$REQUIRED_HEADERS
Status"
fi

validate_file() {
  local f="$1"
  local base
  base="$(basename "$f" .md)"

  # Filename validation
  case "$FILENAME_PATTERN" in
    *"{layer}"*)
      if ! [[ "$base" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}--[a-z]+--[a-z0-9].*$ ]]; then
        ERRORS+=("$base: malformed filename (expected YYYY-MM-DD--<layer>--<details>)")
      fi
      ;;
    *)
      if ! [[ "$base" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9].*$ ]]; then
        ERRORS+=("$base: malformed filename (expected YYYY-MM-DD-<name>)")
      fi
      ;;
  esac

  # Header validation
  local header
  header=$(head -20 "$f")

  while IFS= read -r field; do
    [ -z "$field" ] && continue
    if ! echo "$header" | grep -q "\*\*${field}:\*\*"; then
      ERRORS+=("$base: missing **${field}:** line in header")
    fi
  done <<< "$REQUIRED_HEADERS"

  # Spec reference validation
  if echo "$REQUIRED_HEADERS" | grep -q "Spec"; then
    if echo "$header" | grep -q '\*\*Spec:\*\*'; then
      local spec_ref
      spec_ref=$(echo "$header" | sed -n 's/.*\*\*Spec:\*\* `\([^`]*\)`.*/\1/p' | head -1)
      if [ -z "$spec_ref" ]; then
        ERRORS+=("$base: **Spec:** line has no backtick-enclosed path")
      elif [ "$spec_ref" != "none" ] && [[ "$spec_ref" != willikins/* ]] && [[ "$spec_ref" != frank/* ]] && [[ "$spec_ref" != content-factory/* ]]; then
        if [ ! -f "$REPO_ROOT/$spec_ref" ]; then
          ERRORS+=("$base: spec ref not found: $spec_ref")
        fi
      fi
    fi
  fi

  # Status value validation
  if [ -n "$STATUS_VALUES" ]; then
    local status_val
    status_val=$(echo "$header" | sed -n 's/.*\*\*Status:\*\* \(.*\)/\1/p' | head -1)
    status_val="${status_val%% (*}"
    status_val="${status_val#semi-}"
    if [ -n "$status_val" ] && ! echo "$STATUS_VALUES" | grep -qx "$status_val"; then
      ERRORS+=("$base: invalid status '$status_val' — allowed: $(echo "$STATUS_VALUES" | tr '\n' ', ')")
    fi
  fi

  # Structure validation
  local has_phases=false
  if grep -q '^## Phase [0-9]' "$f"; then
    has_phases=true
  fi

  if $has_phases; then
    while IFS= read -r line; do
      if ! [[ "$line" =~ \[(manual|agentic)\] ]]; then
        ERRORS+=("$base: untagged phase: $line")
      fi
    done < <(grep '^## Phase [0-9]' "$f")

    if grep -q '^## Task [0-9]' "$f"; then
      ERRORS+=("$base: uses '## Task' — should be '### Task' (h3 inside Phase)")
    fi
  else
    if grep -q '^## Task [0-9]' "$f"; then
      ERRORS+=("$base: uses '## Task' — should be '### Task'")
    fi
  fi
}

if [ ${#FILES[@]} -gt 0 ]; then
  for f in "${FILES[@]}"; do
    [ -f "$f" ] && validate_file "$f"
  done
else
  PLANS_DIR="$REPO_ROOT/docs/superpowers/plans"
  ARCHIVE_DIR="$REPO_ROOT/docs/superpowers/archived-plans"
  for f in "$PLANS_DIR"/*.md "$ARCHIVE_DIR"/*.md; do
    [ -e "$f" ] && validate_file "$f"
  done
fi

if [ ${#ERRORS[@]} -gt 0 ]; then
  echo "Plan validation failed:" >&2
  for e in "${ERRORS[@]}"; do
    echo "  - $e" >&2
  done
  exit 1
fi
```

- [ ] **Step 2: Make executable and test**

```bash
chmod +x scripts/validate-plans.sh

# Test against the current plan file — should pass
./scripts/validate-plans.sh docs/superpowers/plans/2026-04-11-plugin-canonical-skills.md && echo "PASS: self-validation"

# Test with a bad file
cat > /tmp/bad-plan.md << 'EOF'
# Bad Plan
No status here.
EOF
./scripts/validate-plans.sh /tmp/bad-plan.md 2>&1 && echo "FAIL: should have errored" || echo "PASS: caught missing status"
rm /tmp/bad-plan.md
```

- [ ] **Step 3: Commit**

```bash
git add scripts/validate-plans.sh
git commit -m "feat: add canonical profile-driven plan validator

Reads plan-config.yaml for filename pattern, required headers, status values.
Validates both new (Phase > Task > Step) and grandfathered (flat Task) formats.
Per-repo thin wrappers call this script."
```

### Task 3: Create install script and vk-plan override rule

**Files:**
- Create: `rules/vk-plan-override.md`
- Create: `scripts/install.sh`

- [ ] **Step 1: Create the rule**

```bash
mkdir -p rules
```

Write `rules/vk-plan-override.md`:

```markdown
## Plan Skill Override

When the brainstorming skill says to invoke `writing-plans`, invoke `vk-plan` instead.
When any skill references `superpowers:writing-plans`, use `vk-plan`.
```

- [ ] **Step 2: Write the install script**

Write `scripts/install.sh`:

```bash
#!/usr/bin/env bash
# Install superpowers-for-vk skills, rules, and hooks at user level.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLAUDE_DIR="$HOME/.claude"
SKILLS_DIR="$CLAUDE_DIR/skills"
RULES_DIR="$CLAUDE_DIR/rules"
SETTINGS="$CLAUDE_DIR/settings.json"

SKILL_NAMES=(vk-plan vk-dispatch vk-execute vk-progress)

if [[ "${1:-}" == "--uninstall" ]]; then
  echo "Uninstalling superpowers-for-vk..."
  for skill in "${SKILL_NAMES[@]}"; do
    rm -rf "$SKILLS_DIR/$skill"
    echo "  Removed $SKILLS_DIR/$skill"
  done
  rm -f "$RULES_DIR/vk-plan-override.md"
  echo "  Removed $RULES_DIR/vk-plan-override.md"
  echo "Done. Note: PostToolUse hook in settings.json was NOT removed (manual cleanup)."
  exit 0
fi

echo "Installing superpowers-for-vk..."

for skill in "${SKILL_NAMES[@]}"; do
  mkdir -p "$SKILLS_DIR/$skill"
  cp "$PLUGIN_ROOT/skills/$skill/SKILL.md" "$SKILLS_DIR/$skill/SKILL.md"
  echo "  Installed $SKILLS_DIR/$skill/SKILL.md"
done

mkdir -p "$RULES_DIR"
cp "$PLUGIN_ROOT/rules/vk-plan-override.md" "$RULES_DIR/vk-plan-override.md"
echo "  Installed $RULES_DIR/vk-plan-override.md"

if [ ! -f "$SETTINGS" ]; then
  echo "  WARNING: $SETTINGS not found — skipping hook installation"
else
  if grep -q "validate-plans" "$SETTINGS"; then
    echo "  PostToolUse hook already present — skipping"
  else
    echo ""
    echo "  NOTE: Manual settings.json edit required. Add this PostToolUse hook:"
    cat << 'HOOK'
    {
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "command": "bash -c 'FILE=$(cat | jq -r \".tool_input.file_path // .tool_response.filePath // empty\"); case \"$FILE\" in */docs/superpowers/plans/*.md) REPO_ROOT=$(git -C \"$(dirname \"$FILE\")\" rev-parse --show-toplevel 2>/dev/null); [ -x \"$REPO_ROOT/scripts/validate-plans.sh\" ] && \"$REPO_ROOT/scripts/validate-plans.sh\" \"$FILE\" 2>&1 || true;; esac'",
          "statusMessage": "Validating plan..."
        }
      ]
    }
HOOK
  fi
fi

echo ""
echo "Installation complete. Verify with:"
echo "  ls ~/.claude/skills/vk-*/"
echo "  cat ~/.claude/rules/vk-plan-override.md"
```

- [ ] **Step 3: Make executable and verify**

```bash
chmod +x scripts/install.sh
bash -n scripts/install.sh && echo "Syntax OK"
```

- [ ] **Step 4: Commit**

```bash
git add rules/vk-plan-override.md scripts/install.sh
git commit -m "feat: add install script and vk-plan-override rule

install.sh copies skills to ~/.claude/skills/vk-*/, installs the
brainstorming→vk-plan redirect rule, and documents the PostToolUse hook."
```

### Task 4: Update README and bump version to 0.2.0

**Files:**
- Modify: `README.md`
- Modify: `package.json`

- [ ] **Step 1: Replace README.md**

```markdown
# superpowers-for-vk

Canonical planning and work lifecycle skills for derio-net repos. Wraps the upstream
[superpowers](https://github.com/obra/superpowers) plugin with phase-based plans,
profile-driven per-repo behavior, and work lifecycle tracking.

## Skills

| Skill | Description |
|-------|-------------|
| `vk-plan` | Canonical plan skill — phase-structured plans with profile-driven behavior and spec index maintenance |
| `vk-dispatch` | Dispatch plan phases to GitHub Issues with profile-aware config |
| `vk-execute` | Execute an agentic phase (agent-facing, Phase > Task > Step) |
| `vk-progress` | Work lifecycle — plan sync, status board, create/transition, health, audit |

## Installation

### Option 1: Plugin (recommended)

Add to `~/.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "superpowers-for-vk@derio-net": true
  }
}
```

### Option 2: User-level install

```bash
git clone https://github.com/derio-net/superpowers-for-vk
cd superpowers-for-vk
./scripts/install.sh
```

## Per-Repo Profile

Each repo can define `docs/superpowers/plan-config.yaml` to control:
- Filename patterns, required headers, status values
- Post-deploy phases (auto-appended by vk-plan)
- Dispatch config (project board, labels, target repo)

## Plan Model

- **One plan = one repo's worth of work.** Plans live in the repo they modify.
- **One phase = one GitHub Issue = one PR.** Phases are scoped for reviewability.
- **Cross-repo features use multiple plans**, coordinated via the spec's "Implementation Plans" section (maintained automatically by vk-plan).

## Requirements

- [superpowers](https://github.com/obra/superpowers) plugin installed
- GitHub CLI (`gh`) authenticated
- VK MCP server (optional): `npx vibe-kanban@latest --mcp`

## Validator

`scripts/validate-plans.sh` — canonical, profile-driven plan validator. Per-repo thin wrappers delegate here.
```

- [ ] **Step 2: Bump version**

Update `package.json`:

```json
{
    "name": "superpowers-for-vk",
    "version": "0.2.0",
    "type": "module"
}
```

Also update `.claude-plugin/plugin.json`:

```bash
python3 -c "
import json
with open('.claude-plugin/plugin.json') as f:
    d = json.load(f)
d['version'] = '0.2.0'
with open('.claude-plugin/plugin.json', 'w') as f:
    json.dump(d, f, indent=2)
    f.write('\n')
"
```

And `.claude-plugin/marketplace.json`:

```bash
python3 -c "
import json
with open('.claude-plugin/marketplace.json') as f:
    d = json.load(f)
for p in d['plugins']:
    if p['name'] == 'superpowers-for-vk':
        p['version'] = '0.2.0'
with open('.claude-plugin/marketplace.json', 'w') as f:
    json.dump(d, f, indent=2)
    f.write('\n')
"
```

- [ ] **Step 3: Verify versions match**

```bash
grep '"version"' package.json
grep '"version"' .claude-plugin/plugin.json
grep '"version"' .claude-plugin/marketplace.json
# All three should show 0.2.0
```

- [ ] **Step 4: Commit**

```bash
git add README.md package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "chore: update README and bump to v0.2.0

Documents profile-driven behavior, install script, validator, spec index
maintenance, and the one-plan-one-repo + one-phase-one-PR model."
```

---

*Last progress sync: —*
