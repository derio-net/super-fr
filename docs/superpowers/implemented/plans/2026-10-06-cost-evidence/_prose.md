# Cost evidence — implementation plan

Spec: `docs/superpowers/specs/2026-10-06-cost-evidence-design.md` (batch
`cost-evidence`: #838, #793, #593, #627).

Three agentic phases, one per ask:

1. **Usage split (skeleton).** Every usage message learns its agent id. A
   capture then records main vs subagent figures per step (#593 option 0) and
   per-unit executor/reviewer/orchestrator figures (the data for #793). The
   `usage` kind moves to version 2. Everything else reads what this phase
   writes.
2. **Tier, bound model and the per-phase tables.** The cursor keeps the tier
   and the model it was bound to at dispatch beside the model that ran (run
   kind 9). `fr run cost` and the PR body render the per-phase table (#838,
   #793 item 4). Tier `hard`: it changes `_open_dispatch`, which every
   dispatch goes through, and adds a run-kind migration.
3. **Before/after.** `fr usage compare`, plus the audit that answers #627,
   #793 item 5 and #593's decision rules from its output.

Phases 2 and 3 depend only on phase 1 and touch disjoint files.
Every phase ends with the full suite, run after its last code commit.
