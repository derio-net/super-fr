# Raw-input relay — implement-phase and review-phase see the verbatim input

Spec: `docs/superpowers/specs/2026-09-28-raw-input-relay-design.md` (super-fr#778).

One agentic phase. A new pure module, `fr.operator_input`, owns the rule text, the
brief payload and the handoff markdown (the `fr.harness.long_commands` precedent),
so the brief, the handoff and the prose cannot drift. `fr run advance` puts
`operator_input` on every grouped member brief, loading it before the write-claim so
a bad spec journal refuses without stranding a `running` unit; `fr journal handoff`
opens with the same content, fenced, even before the plan journal exists. fr-goal
§5/§6 relay it verbatim to executor and reviewer; the phase-executor agent file
states the rule. No artifact kind changes shape; one ci row's acceptance text is
reworded because it asserted the opposite.

A single phase is deliberate: the pieces are small and share one module, and a
second phase would only re-read the handoff.
