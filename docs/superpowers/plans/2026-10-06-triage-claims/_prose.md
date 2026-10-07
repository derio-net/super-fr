# Triage claims across scopes and hosts — plan

Spec: `docs/superpowers/specs/2026-10-06-triage-claims-design.md` (super-fr#1043).

Phase 1 builds the claim itself: scope identity, the marker and its pure rules,
the forge's comment ids and edits, the one claim-write module, facts and
judgements schema bumps, `check`'s three sets, the `claim`/`scope` commands and
the batch-command gates. It is the skeleton: its first task proves the test
wiring. Phase 2 wires claims into every drive pass. Phase 3 adds the board's
"Held elsewhere" group, per-scope publishing and the skill. Phases 2 and 3 both
depend only on phase 1.

TDD throughout: red, green, then a refactor step or a recorded reason.
