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

## Embedding Full File Content

When a task writes a **complete file** (especially a Markdown or skill file that itself contains code fences), use explicit HTML-comment markers instead of wrapping the content in nested code fences. Agents reading a plan may literally copy the outer fence markers into the target file, producing a corrupt output whose first line is a fence instead of the expected content (e.g., YAML frontmatter's `---`).

### Required pattern

State the target path, open a BEGIN marker, paste the file content verbatim at plan-file indentation, and close with an END marker:

```
Write the following content to `skills/example/SKILL.md` verbatim. Do not include the BEGIN/END markers themselves in the output file — they are plan-level metadata.

<!-- BEGIN FILE: skills/example/SKILL.md -->
---
name: example
description: example skill
---

# Example

Body of the skill, including any fenced code blocks, with no nesting concerns.
<!-- END FILE: skills/example/SKILL.md -->
```

The BEGIN/END markers are HTML comments — invisible in rendered markdown but unambiguous as boundary tokens for both agents and mechanical extractors.

### Why not nested code fences

The historical pattern was to wrap file content in an outer fence with more backticks than any fence inside it (e.g., 5 backticks outside, 4 for nested examples, 3 for innermost code). This renders correctly but fails in execution: some agents treat the outer fence as content to be written rather than plan-file syntax. The 2026-04-11 incident shipped `skills/vk-plan/SKILL.md` and `skills/vk-progress/SKILL.md` with literal fence markers as their first and last lines. Post-hoc fix: `dd965e6`. Enforcement: `scripts/validate-skills.sh` rejects SKILL.md files whose first non-empty line is not `---`.

### Partial edits are exempt

If a task only *modifies* an existing file via targeted Edit operations (add a section, rename a symbol, bump a version), normal 3-backtick fenced blocks are fine — there is no risk of outer-fence leakage because there is no outer fence. This rule applies only to full file rewrites.

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
