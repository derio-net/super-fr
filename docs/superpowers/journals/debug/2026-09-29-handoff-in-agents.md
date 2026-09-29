# Journal: 2026-09-29-handoff-in-agents

<!-- fr:journal kind=repro scope=debug id=repro-take10 created=2026-09-29T11:09:18+00:00 -->
### repro-take10 · repro · Raw operator input never reaches executor/reviewer when the orchestrator does not relay it

super-fr-3 take 10 (fr 4.35.0, OpenCode): run A's orchestrator replaced the input with a pointer — 0 hits for brief phrases in the executor's and review-phase reviewer's first messages; the executor saw it only after running `fr journal handoff` itself. Run B's re-dispatched reviewers got none or a paraphrase. Static repro: plugins/super-fr/agents/fr-phase-executor.md 'Inputs' says the operator input is 'in your task prompt' and never instructs a self-fetch; review-phase in fr-goal.yaml names no agent: at all.
