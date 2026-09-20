# Journal: 2026-09-20-opencode-tier-binding-reaches-dispatch

<!-- fr:journal kind=discovery scope=plan id=x-plan1 created=2026-09-20T08:55:16 -->
### x-plan1 · discovery · Plan-authoring notes: two self-review hits, and fr plan create dropped tier again

1. `fr plan create` dropped `tier:` from all three agentic phase headers again — issue #434, now observed a second time in super-fr itself (the first was the gh#494 plan last night). Re-added directly to 01-03.yaml; self-review passes after.

2. The agentic-purity gate flagged P1.T1.S1 on `\bby hand\b`. FALSE POSITIVE in substance: the phrase was "never by hand-writing agent content", a clause FORBIDDING a manual operation, not instructing one. Reworded to "never from agent content written inline in the test" — the gate cannot distinguish a prohibition from an instruction, and rewording is cheaper than arguing with it. Worth knowing when authoring: negated manual-operation phrases trip it.

3. Renumbering steps inside an existing phase file requires rebuilding `state.steps` too — the parser enforces that the state keys match the task step ids exactly (`missing=[P3.T4.S1] extra=[P3.T2.S2]`). Splitting P3.T2 into single-step tasks to satisfy the refactor-step rule therefore meant editing both halves of the file. The error message names both sides, which made it a 30-second fix rather than a hunt — worth noting as a case where fr fails usefully.
