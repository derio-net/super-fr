# Journal: 2026-09-25-lean-cost-aware-process

<!-- fr:journal kind=discovery scope=plan id=1ad42589d6f1 created=2026-09-25T15:10:06 phase=1 -->
### 1ad42589d6f1 · discovery · no-refactor-because P1.T5 (phase 1)

Skill prose, install wiring, generated mirrors and a render check: no code structure to refactor.

<!-- fr:journal kind=discovery scope=plan id=526bcacc56d4 created=2026-09-25T19:37:52 phase=1 -->
### 526bcacc56d4 · discovery · Claude Code writes tool_use blocks on LATER records of a message (phase 1)

telemetry._distinct_messages drops every record after the first per message.id, which is right for summing usage but loses the tool_use blocks (usually written on later records). Added telemetry.message_groups (first record + all records of the id); _distinct_messages now delegates to it, so there is still one dedupe rule. cost-state token totals do NOT equal transcript sums (the harness counts side queries/compaction), so harness dollars are split, never reconstructed.

<!-- fr:journal kind=discovery scope=plan id=834e40db0862 created=2026-09-25T19:37:53 phase=1 -->
### 834e40db0862 · discovery · Model deviations: Cost.by_model, Message.agent, reader session arg (phase 1)

Cost gains by_model (per-model harness dollars — rollup divides each model's dollars, so it needs them); Message gains agent (main | subagent type) so subagent spend is attributable; UsageReader.read takes (source, session=None) because OpenCode/Hermes sources are a DB plus a session id. Claude Code cache writes without a TTL split book at the 1h rate (the audit prototype's convention); OpenCode's untyped cache.write books at 5m.
