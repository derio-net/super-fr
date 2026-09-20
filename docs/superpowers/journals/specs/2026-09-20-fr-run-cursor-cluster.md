# Journal: 2026-09-20-fr-run-cursor-cluster

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-09-20T15:17:51 -->
### d1 · decision · #499: advance refuses a running agent step (exit 2), with --redispatch as the deliberate escape

Operator chose the issue's own preference over a loud-but-permissive warning. Exit 2 is already this module's code for every refusal (not-running, already-done, second-writer), so no new exit-code contract is introduced; a distinct exit 3 was offered and declined as precision nothing in-repo consumes.

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-09-20T15:17:51 -->
### d2 · decision · #501: actionable split-flag error, and advance prints the resolve command BEFORE the JSON brief

Issue's option 1 (teach the flag) over option 2 (accept the composite silently). The hint line goes before the JSON because run_cmd already treats the brief as the line a naive 'tail -1' parses off stdout — the gate-degradation notice has the same ordering constraint and says so.

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-09-20T15:17:51 -->
### d3 · decision · #500: bind the session on all three surfaces — CLI flag, hook, skill prose

fr run start --session/--harness passthrough (harness-neutral), fr-session-bind.sh extended from 'fr isolation up|exec|down' to also match 'fr run start --branch' (Claude Code binds with no agent cooperation), and fr-goal SKILL.md names 'fr isolation attach' as the documented fallback. Hook-only was declined because the fr-session-bind parity row is opencode:absent / hermes:absent, which would make a CLI-shaped problem Claude-Code-shaped.

<!-- fr:journal kind=decision scope=spec id=d4 created=2026-09-20T15:18:10 -->
### d4 · decision · #496: manual phases are a STRUCTURAL invariant, not a runtime skip — enforced at plan authoring

Operator's reframing, chosen over three runtime-behaviour options. A tag: manual phase must be in the plan's TRAILING block or already plan_locally_complete; anything else is a severity=error issue in fr.plan_ops.self_review. fr-goal's plan-review step is 'kind: cli' running 'fr plan self-review', so a mis-shaped plan fails loudly BEFORE phase 1 is dispatched. Rationale: an invariant can be checked at authoring; a behaviour can only be observed at dispatch.

<!-- fr:journal kind=decision scope=spec id=d5 created=2026-09-20T15:18:10 -->
### d5 · decision · #496: front-loading survives as 'trailing OR already complete'

The rule is 'no manual phase may be OUTSTANDING when an agentic phase after it runs', not bare position. fr-goal §3's front-load exception (pause for the go) ends with the operator ticking that phase's steps, so by loop time it has nothing to dispatch and stays valid. Trailing-only-no-exception was declined: it would have made §3 unexpressible, i.e. a doctrine rewrite riding on a bug-fix cluster.

<!-- fr:journal kind=decision scope=spec id=d6 created=2026-09-20T15:18:11 -->
### d6 · decision · #496: the trailing manual block stays OUTSIDE the cursor's step list

for_each: phase enumerates agentic phases only; the trailing block is recorded as 'phase/<n>: manual' in the group's items map (values are already free-form strings — no schema change) and named at group completion. A real 'manual' step in fr-goal.yaml was declined: _check_step_drift refuses any run started against the old step list, so every in-flight fr-goal run would have to restart.

<!-- fr:journal kind=decision scope=spec id=d7 created=2026-09-20T15:18:11 -->
### d7 · decision · Post-merge Test Plan ships as a back-loaded [manual] phase

Three of the four bugs were found by RUNNING the pipeline, not reading it; CI fixtures create their own runs and so satisfy the assumptions by construction. The plan therefore ends with a manual live-verification phase — which also makes this plan its own fixture for d4/d6.

<!-- fr:journal kind=discovery scope=spec id=x1 created=2026-09-20T15:18:11 -->
### x1 · discovery · #500 reproduced live by the run that exists to fix it

The first command of this pipeline, 'fr run start fr-goal --branch fix/fr-run-cursor-cluster', produced a workspace that 'fr isolation status' immediately reported as sessions=none, alongside sibling workspaces entered via 'fr isolation up' that carry a uuid. Mechanism confirmed in plugins/super-fr/hooks/fr-session-bind.sh: its verb regex is start-anchored on 'fr isolation (up|exec|down)', which 'fr run start' cannot match.

<!-- fr:journal kind=discovery scope=spec id=x2 created=2026-09-20T15:18:12 -->
### x2 · discovery · Tier bindings ARE bound — under harness key 'claude-code', not 'claude'

'fr models resolve --tier X --harness claude' prints nothing and exits 0, which reads identically to unbound. The configured key in ~/.config/fr/models.yaml is 'claude-code' (mechanical/standard -> claude-sonnet-5, hard -> claude-opus-5). No model-per-tier question was needed; noting it because 'prints nothing, exits 0' is indistinguishable from a wrong --harness value.
