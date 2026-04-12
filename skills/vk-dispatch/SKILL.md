---
name: vk-dispatch
description: >
  Dispatch a phase-structured plan to GitHub Issues via the vk CLI. Use when:
  "dispatch this plan", "send to VK", "create issues from plan". Requires a
  phased plan and a plan-config.yaml with an explicit dispatch: block.
---

# vk-dispatch

Wraps the `vk dispatch` CLI command. The CLI does all mechanical work: parse,
idempotency check, create issues, add to board, inject tracking comments, commit.

**Announce at start:** "I'm using vk-dispatch to dispatch this plan via the vk CLI."

## Procedure

1. **Dry run.**
   ```bash
   vk dispatch <plan-path> --dry-run
   ```
2. **Present the dry-run output to the operator verbatim.** Ask: *"Proceed? (yes/no)"*
3. **On approval:**
   ```bash
   vk dispatch <plan-path> --yes
   ```
4. **Relay the Issue URLs** from the apply output.
5. **On refusal, stop.** Wait for instructions.

## Error handling

| Exit | Meaning | Action |
|------|---------|--------|
| 0 | Success or noop | Relay URLs |
| 1 | Gate disabled / config error | Paste CLI error verbatim |
| 2 | Plan parse error (flat format) | Suggest `vk plan convert --to phased` |
| 3 | gh error | Check `gh auth status` |
| 4 | Partial success | CLI shows which failed |

## Integration

- Convert flat to phased: `vk plan convert <plan> --to phased --group-by-tag`
- Sync progress after dispatch: use vk-progress skill
- Execute a dispatched phase: use vk-execute skill
