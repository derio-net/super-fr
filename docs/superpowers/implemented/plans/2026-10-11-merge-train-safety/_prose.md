# Merge train safety — implementation plan

Spec: `docs/superpowers/specs/2026-10-11-merge-train-safety-design.md`.

Four phases, one per independently reviewable ask:

1. **The `approved-fr` label gate (#1129, R1–R6, R8).** This is the skeleton. It brings in the facts and the
   judgements schema 9 events that every later phase reads, so it lands first.
2. **Red-PR recovery (#1082), strict up-to-date and skip-held (#1076).** These change the driver's and
   `batch merge`'s behaviour around a PR that cannot merge yet. Both read phase 1's `update` events.
3. **Merge queues (#1062 piece 3) and `merge_group` CI.** These reuse phase 2's `base_rules` and
   `red_decision`.
4. **The release pushed as the app, the protection script and the runbook (#1062 pieces 1–2).**
   Applying the protection to the live repo is post-merge (the spec's Test Plan), not a phase.

Every phase is TDD: red, then green, then refactor or a recorded reason. Each phase ends with the full suite run
after its last code commit.
