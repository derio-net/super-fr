# Journal: 2026-09-29-handoff-in-agents

<!-- fr:journal kind=repro scope=debug id=repro-take10 created=2026-09-29T11:09:18+00:00 -->
### repro-take10 · repro · Raw operator input never reaches executor/reviewer when the orchestrator does not relay it

super-fr-3 take 10 (fr 4.35.0, OpenCode): run A's orchestrator replaced the input with a pointer — 0 hits for brief phrases in the executor's and review-phase reviewer's first messages; the executor saw it only after running `fr journal handoff` itself. Run B's re-dispatched reviewers got none or a paraphrase. Static repro: plugins/super-fr/agents/fr-phase-executor.md 'Inputs' says the operator input is 'in your task prompt' and never instructs a self-fetch; review-phase in fr-goal.yaml names no agent: at all.

<!-- fr:journal kind=root-cause scope=debug id=rc-relay-only created=2026-09-29T11:09:19+00:00 -->
### rc-relay-only · root-cause · Input delivery depends solely on the orchestrator's prompt relay

The only delivery path is fr-goal §5/§6 prose telling the orchestrator to copy the brief's operator_input VERBATIM into child prompts. An instruction to the orchestrator is absorbed under load (A paraphrased to a pointer; B dropped it on re-dispatch). The executor agent file treats the input as already present; the review-phase reviewer has no shipped agent definition, so nothing it is given says to fetch the input. `fr journal handoff` already emits the input first (fr/operator_input.to_markdown) and is witnessed to work when the child runs it.

<!-- fr:journal kind=decision scope=debug id=d-shipped-reviewer created=2026-09-29T11:47:47+00:00 -->
### d-shipped-reviewer · decision · Operator chose a shipped fr-phase-reviewer over executor-only or reusing fr-spec-reviewer

review-phase had no shipped agent, so a self-fetch needed one. Asked once (scope fork); operator picked the recommended option. `agent:` is not a member id, so no cursor drifts; _verify_reviewer checks agent type only for flat steps, so fr accepts the same reviewers it did before.
