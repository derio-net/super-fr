---
name: vk-plan
description: >
  Write phase-structured plans with operator collaboration. Use when:
  "write a plan", "vk plan", "create a plan". Invoked by brainstorming handoff.
---

# vk-plan

Produce implementation plans through collaborative dialogue. Conversational parts
stay here; mechanical parts delegate to the `vk plan` CLI.

**Announce at start:** "I'm using vk-plan to create the implementation plan."

## Format

Plans are always phased. Dispatch intent is an orthogonal concern, expressed by
the presence (or absence) of a `dispatch:` block in `plan-config.yaml`. Flat
plans are deprecated — migrate with `vk plan convert <plan> --to phased`
before continuing.

## Procedure

1. Read context (recent commits, existing plans, spec file).
2. Confirm scope. Decompose if too large.
3. Propose 2-3 approaches with tradeoffs. Recommend one.
4. Present plan structure section by section, get approval.
5. Create skeleton: `vk plan new <name> --spec <spec-path> --save`
6. Fill in body via Edit tool.
7. Run self-review: `vk plan self-review <plan-path>`
8. Update spec index: `vk plan spec-index <plan-path> --yes`
9. Present execution handoff:
   - Dispatch via `vk-dispatch` — if `plan-config.yaml` has a `dispatch:` block
   - Subagent-driven via `subagent-driven-development`
   - Inline via `executing-plans`

## Rules

- TDD: test first, always. No speculative generality.
- No placeholders: every step has actual code, commands, expected output.
- Bite-sized steps: 2-5 minutes each.
- Use BEGIN/END markers for full-file embeds, not nested fences.
- **Cross-repo completeness:** If the spec lists multiple plans across repos,
  write ALL of them before offering the execution handoff. For each target repo:
  read its `plan-config.yaml`, write the plan in that repo's `plans/` directory,
  and update the spec index. Only offer dispatch/execution after all plans exist.

## Integration

- Upstream: brainstorming hands off via vk-plan-override
- Downstream: vk-dispatch, subagent-driven-development, executing-plans
