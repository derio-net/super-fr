# Journal: 2026-09-20-opencode-tier-binding-reaches-dispatch

<!-- fr:journal kind=discovery scope=plan id=x-plan1 created=2026-09-20T08:55:16 -->
### x-plan1 · discovery · Plan-authoring notes: two self-review hits, and fr plan create dropped tier again

1. `fr plan create` dropped `tier:` from all three agentic phase headers again — issue #434, now observed a second time in super-fr itself (the first was the gh#494 plan last night). Re-added directly to 01-03.yaml; self-review passes after.

2. The agentic-purity gate flagged P1.T1.S1 on `\bby hand\b`. FALSE POSITIVE in substance: the phrase was "never by hand-writing agent content", a clause FORBIDDING a manual operation, not instructing one. Reworded to "never from agent content written inline in the test" — the gate cannot distinguish a prohibition from an instruction, and rewording is cheaper than arguing with it. Worth knowing when authoring: negated manual-operation phrases trip it.

3. Renumbering steps inside an existing phase file requires rebuilding `state.steps` too — the parser enforces that the state keys match the task step ids exactly (`missing=[P3.T4.S1] extra=[P3.T2.S2]`). Splitting P3.T2 into single-step tasks to satisfy the refactor-step rule therefore meant editing both halves of the file. The error message names both sides, which made it a 30-second fix rather than a hunt — worth noting as a case where fr fails usefully.

<!-- fr:journal kind=discovery scope=plan id=p1-smoke1 created=2026-09-20T09:00:42 phase=1 -->
### p1-smoke1 · discovery · Skeleton smoke: opencode agent list cannot show resolved model; file content asserted instead (phase 1)

Ran the materialiser end to end under a sandboxed XDG_CONFIG_HOME + HOME (never
the operator's real ~/.config): seeded config/opencode/agent/ from the
committed .opencode/agent/ mirror (fr-phase-executor{,-hard,-mechanical,-standard}.md),
wrote config/fr/models.yaml binding opencode/{mechanical,standard,hard} to
anthropic/claude-haiku-4-5, anthropic/claude-sonnet-4-5, anthropic/claude-opus-4-1,
then called materialize_agents(config_home, models_cfg=load_models(...)).

`opencode agent list` (v1.18.31) registered all four agents under that
XDG_CONFIG_HOME both before and after materialization, byte-identical output
(diff empty) except this run's own permission tool-output pattern — its output
is only a permission-rules dump per agent, with NO model field at all, so the
binary cannot confirm a resolved model either way. Confirmed instead by reading
the agent files directly: each tier file carries exactly one `model: <bound>`
line immediately after `mode: subagent` (hard -> anthropic/claude-opus-4-1,
mechanical -> anthropic/claude-haiku-4-5, standard -> anthropic/claude-sonnet-4-5),
and the untiered fr-phase-executor.md has no model: line at all.

Stating this plainly rather than implying `agent list` confirmed the binding:
it only confirms agent NAME registration, not model resolution. Anyone adding
a stronger live check later needs a different opencode surface (none found
in 1.18.31's `agent` subcommand family).
