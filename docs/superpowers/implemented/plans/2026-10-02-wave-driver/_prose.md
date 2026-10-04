# Wave driver — implementation plan

Six agentic phases, in the spec's delivery order (spec section J). Each phase is mergeable on its own.

1. **Waves and dependencies** (R1): the schema, validation, `batch list` columns, and the two helpers the driver reuses. Small, and the walking skeleton.
2. **The driver** (R2-R8, R13, R14): the pure pass, `fr triage batch drive`, close-out through the runner, `post_merge`, the lock. Tier `hard`: it changes the merge and dispatch path every batch relies on.
3. **Repo groups** (R15): scope and facts schema 4, before any view reads them.
4. **Decision views** (R9, R16-R20): kind, features, unplaced, snapshots, Since last report, Needs you now, Next up, wave tabs, the board's order.
5. **Origins** (R10): the engine, the verbs and the `fr-origins` skill.
6. **Architecture page** (R11, R12): generated measured sections, authored fragments, the `fr-audit` rewrite.

Every phase ends with its acceptance row moved and its skill and mirror changes in the same phase. The release fragment (minor) is added in phase 1.
