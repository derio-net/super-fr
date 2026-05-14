---
name: vk-dispatch
description: >
  Reconcile a plan's GitHub Issues via the vk CLI (`vk apply`). Use when:
  "dispatch this plan", "send to VK", "create issues from plan", "sync plan to GitHub".
---

# vk-dispatch

Wraps the `vk apply` CLI. The single command renders the plan, observes
GitHub state, diffs, and emits the mutations needed to bring GitHub in line
with the plan. Works for first-time creation, incremental updates, and
ongoing reconciliation — there's no separate "first dispatch" verb in v2.

**Announce at start:** "I'm using vk-dispatch to reconcile this plan via `vk apply`."

## Procedure

1. **Preview** (dry-run is the default):
   ```bash
   vk apply <plan-dir>
   ```
   The output lists the mutations `vk` would perform: ensure-labels, create
   Issue, edit labels, edit body, set state.
2. **Present the preview to the operator verbatim.** Ask: *"Proceed? (yes/no)"*
3. **On approval:**
   ```bash
   vk apply <plan-dir> --yes
   ```
4. **Relay the Issue URLs** from the apply output (`created:` block).
5. **Commit the staged writeback.** `vk apply --yes` stages the
   `tracking_issue` line into each affected `<plan>/<NN>.yaml`.
   Commit and push (or open a PR — operator's convention) so the
   bridge's checkout can see the URLs on its next tick. Suggested
   message: `vk apply: persist tracking_issue for <plan>`.
6. **On refusal, stop.** Wait for instructions.

For machine-parseable output:

```bash
vk apply <plan-dir> --format json
```

## Error handling

| Exit | Meaning | Action |
|------|---------|--------|
| 0 | Success or no diff | Relay URLs (if any) |
| 2 | Usage error (bad flag combination) | Paste CLI error verbatim |
| 4 | gh / network failure during apply | Check `gh auth status`, retry |
| 5 | Plan parse error (`PlanSchemaError`) | Paste CLI error; inspect plan files |

## Idempotency

`vk apply` is fully idempotent: running it twice in a row yields the same end
state. There is no separate "create then sync" workflow — every invocation
reconciles. Re-run after editing the plan to push the deltas.

## Reconciliation across the plan lifecycle

- **Phase added / edited:** `vk apply <plan-dir> --yes` updates labels and
  body for affected Issues.
- **Phase complete:** the renderer projects `state == CLOSED` once
  `state.completion.at` is set; `vk apply --yes` closes the Issue.
- **Auto-close drift:** `vk apply` is the antidote — re-running detects an
  Issue that's still open despite a merged PR and closes it.

## Integration

- Author / edit plans: vk-plan skill.
- Execute a phase: vk-execute skill.
- Spec rollups: `vk spec status [<spec>|--all]`.
