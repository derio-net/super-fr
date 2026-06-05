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

## Pre-flight (mandatory)

1. **Audit first, with the read-only verb:** `vk status <plan-dir>` —
   safely allowlistable, never mutates. Read the header line (created
   date + age, tick counts, dispatch state) and the per-phase table.
   A locally-complete plan shows "would refuse create"; if the plan is
   genuinely done, run `vk archive <plan-dir>` instead of dispatching.
2. **Never-dispatched plan? Search the target repo for evidence the
   work already landed** (the stoa incident: 0/59 steps ticked, but 15
   merged PRs and the deliverable tree existed in the target repo).
   Check merged PRs mentioning the plan/spec slug and the plan's
   deliverable paths: `gh pr list --repo <target> --state merged
   --search "<slug>"`, `gh api repos/<target>/contents/<path>`.
   Evidence found → STOP and reconcile with the operator; do not
   dispatch.
3. The plan and its referenced spec MUST be merged to the default
   branch before running `vk apply --yes`. The CLI refuses with exit 2
   otherwise, listing the unreachable paths. If you've just written the
   plan, open a PR for spec+plan and merge it before running this
   workflow. The dispatch + writeback is then a separate (small) PR —
   see step 5.

If `git remote set-head origin --auto` has never been run on
your checkout, `vk apply --yes` will tell you to run it before
anything else.

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
   bridge's checkout can see the URLs on its next tick. Subject:
   `vk apply: persist tracking_issue for <plan>`. **Body: list the
   created Issue URLs** — the forensics/`vk undispatch` trail when a
   dispatch turns out to be wrong.
6. **On refusal, stop.** Wait for instructions.

For machine-parseable output:

```bash
vk apply <plan-dir> --format json
```

## Error handling

| Exit | Meaning | Action |
|------|---------|--------|
| 0 | Success or no diff | Relay URLs (if any) |
| 2 | Usage error, completion-guard refusal (plan locally complete — `vk archive` it, or `--force` to override), or legacy layout (`vk migrate dirs --yes`) | Paste CLI error verbatim; pick the verb it names |
| 4 | gh / network failure during apply | Check `gh auth status`, retry |
| 5 | Plan parse error (`PlanSchemaError`) | Paste CLI error; inspect plan files |

## Idempotency

`vk apply` is fully idempotent: running it twice in a row yields the same end
state. There is no separate "create then sync" workflow — every invocation
reconciles. Re-run after editing the plan to push the deltas.

## Reconciliation across the plan lifecycle

- **Phase added / edited:** `vk apply <plan-dir> --yes` updates labels and
  body for affected Issues.
- **Body enrichment:** Issue bodies embed a spec link, the plan prose
  (`_prose.md`), and the phase's `NN.yaml` — including its `state:` block —
  in collapsed `<details>` blocks. Each apply re-syncs the body as steps
  tick, so GitHub shows live progress.
- **Phase complete:** the renderer projects `state == CLOSED` once
  `state.completion.at` is set; `vk apply --yes` closes the Issue.
- **Auto-close drift:** `vk apply` is the antidote — re-running detects an
  Issue that's still open despite a merged PR and closes it.

## Integration

- Author / edit plans: vk-plan skill.
- Execute a phase: vk-execute skill.
- Read-only audit (allowlist-safe): `vk status <plan-dir>`.
- Spec rollups: `vk spec status [<spec>|--all]`.
- Finished plan: `vk archive <plan-dir>` (or `--all`) moves it — and its
  spec, when every row is implemented — to `docs/superpowers/implemented/`.
- Dispatched in error: `vk undispatch <plan-dir> --yes` closes the Issues
  (reason: not planned) and nulls the `tracking_issue` fields.
