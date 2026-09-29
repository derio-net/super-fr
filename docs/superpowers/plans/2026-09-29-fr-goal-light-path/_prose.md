# fr-goal light path — implementation plan

Spec: `docs/superpowers/specs/2026-09-29-fr-goal-light-path-design.md` (super-fr#780).

Three agentic phases, one per independently reviewable ask:

1. **One call per step** (§B, R4/R5): `fr run advance` chains cli steps; `fr run resolve --record`
   advances after a `done` record. Walking skeleton: every later phase and every later run
   benefits, and it is the smallest change touching the run engine.
2. **Suite-log reuse** (§D, R6): offered `tests` evidence on phase units, a code-tree hash that
   ignores fr's artifact trees, and `deliver`'s `tests: reuse`. Its own ask; a different review
   surface (telemetry + evidence gates).
3. **The light shape** (§A, §C, R1–R3, R7): the `fr-goal-light` manifest, the record-kind v5
   `shape` key and brainstorm rebind, the `single-phase` derived gate, and the agent/skill prose
   that describes all three phases' behaviour — last, so the prose describes shipped code.

No member issue is a `tracking_issue`. The benchmark (R8) is the post-merge Test Plan, a
`verify: post-merge` row linked to phase 3.
