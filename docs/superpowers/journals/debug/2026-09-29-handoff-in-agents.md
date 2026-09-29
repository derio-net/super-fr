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

<!-- fr:journal kind=finding scope=debug id=f-self-fetch created=2026-09-29T11:54:53+00:00 state=fixed -->
### f-self-fetch · finding [fixed] · Executor and phase reviewer fetch the operator input themselves

Source: fr-phase-executor.md gains a first section running `fr journal handoff --scope plan` on every dispatch; new plugins/super-fr/agents/fr-phase-reviewer.md does the same; review-phase names `agent: super-fr:fr-phase-reviewer`; guard hook, install allowlist, OpenCode mirrors, fr-goal §5/§6 wired. Failing-first: tests/unit/test_operator_input_prose.py (first-section self-fetch, reviewer tools, manifest agent), test_hooks_phase_executor_guard.py::TestPhaseReviewerGuard, mirror enumerations. Full suite 7596 passed.

<!-- fr:journal kind=finding scope=debug id=rv-reviewer-counted-as-implementer created=2026-09-29T11:56:47+00:00 state=open review_scope=in -->
### rv-reviewer-counted-as-implementer · finding [open] (reviewer: in scope) · A claimed fr-phase-reviewer is refused as the phase's implementer

Naming agent: on review-phase records agent_type on the review unit (run_cmd.py _open_dispatch). The OpenCode plugin's --open-unit claim now matches it (_ran_as), so the reviewer's session id becomes the review unit's holder; _verify_reviewer's implementers set takes every phase/N/* unit with agent_type+agent, so reviewer=<that id> exits 2. Before this change agent_type was None and the unit was never claimable.
