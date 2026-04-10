---
name: vk-plan
description: >
  Write phase-structured plans with manual/agentic phase tagging for VK dispatch.
  Use when you need a plan that will be dispatched to VibeKanban, or when the user
  says "write a vk plan", "plan for vk", "create a dispatchable plan",
  "phase-structured plan", "write a plan with phases".
---

# VK Plan

## Overview

Write a phase-structured implementation plan designed for dispatch to VibeKanban. This skill wraps `superpowers:writing-plans` with additional phase structure constraints that make the plan dispatchable via `vk-dispatch`.

**Announce at start:** "I'm using the vk-plan skill to write a phase-structured plan."

## How It Works

This skill invokes `superpowers:writing-plans` with the following additional constraints layered on top. Everything in the upstream skill still applies — this adds phase structure, not replaces.

## Phase Structure

Plans are organized into sequential phases instead of flat tasks. Each phase header uses this format:

```markdown
## Phase N: <name> [manual|agentic]
```

### Rules

1. **Phases are sequential** — Phase N+1 depends on Phase N being complete. No parallel phases.
2. **Each phase is tagged** as either `manual` or `agentic`:
   - **`[manual]`** — Operator runbook. Contains work that requires human hands: clicking through UIs, creating accounts, configuring external services, running commands that need interactive auth.
   - **`[agentic]`** — Automatable work. Contains only tasks that a Claude Code agent can execute independently: writing code, running tests, creating files, committing.
3. **Each agentic phase = one PR.** Scope agentic phases so the resulting PR is reviewable and self-contained.
4. **Manual phases are never dispatched as agentic work.** They become operator runbooks on the Issue.

### Manual Phase Content

Manual phases must be complete operator runbooks. Include:
- Exact URLs to visit
- Exact commands to run (with expected output)
- Exact file paths and environment variable names
- Verification steps (how to confirm the step worked)
- Why each step connects to the next phase (so the operator understands the dependency)

The operator should be able to follow the phase without any additional context.

### Agentic Phase Content

Agentic phases follow the standard `superpowers:writing-plans` task structure — bite-sized steps with checkboxes, exact file paths, code blocks, test commands, and commit messages. All the upstream rules apply (no placeholders, complete code, TDD).

## Plan Document Header

Every VK plan starts with this header (extends the upstream header):

```markdown
# [Feature Name] Implementation Plan

> **For VK agents:** Use superpowers-for-vk:vk-execute to implement assigned phases.
> **For dispatch:** Use superpowers-for-vk:vk-dispatch to create Issues from this plan.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

**Status:** Not Started

---
```

## Example Phase Headers

```markdown
## Phase 0: Account Setup [manual]

## Phase 1: Repository Scaffold [agentic]

## Phase 2: API Key Configuration [manual]

## Phase 3: Core Pipeline Implementation [agentic]

## Phase 4: Integration Tests and CI [agentic]
```

## Save Location

Save plans to: `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`

User preferences for plan location override this default.

## Self-Review

After writing the plan, run the upstream self-review checklist from `superpowers:writing-plans`, plus:

1. **Phase tagging:** Does every phase have `[manual]` or `[agentic]`? No untagged phases.
2. **Phase sequencing:** Does each phase genuinely depend on the previous one? If two phases are independent, they should be reordered or merged.
3. **Manual completeness:** Can an operator follow each manual phase without asking questions? URLs, commands, verification — all present?
4. **Agentic scoping:** Is each agentic phase small enough for one PR? If it touches more than ~5 files or has more than ~8 tasks, consider splitting.

## Execution Handoff

After saving the plan, offer:

**"Plan ready. Dispatch to VK with `vk-dispatch`?"**

If the user says yes, invoke `superpowers-for-vk:vk-dispatch` with the plan file path.

## Integration

- **Upstream:** `superpowers:writing-plans` — all upstream rules apply
- **Downstream:** `superpowers-for-vk:vk-dispatch` — dispatches phases to GitHub Issues
- **Execution:** `superpowers-for-vk:vk-execute` — agents use this to implement agentic phases
