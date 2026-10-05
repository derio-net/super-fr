# Drive manages its herdr sessions — plan

Spec: `docs/superpowers/specs/2026-10-05-drive-herdr-sessions-design.md` (R1–R10).

Two phases, one per issue of the batch:

1. **Wave workspaces (#919, skeleton).** Live herdr fixtures first (the smoke), then the
   `group` payload hint, `wave_group`, the herdr runner's group workspaces and cross-workspace
   `existing_dispatches`, and `drive --workspace-prefix`. Requirements R1–R5.
2. **Closing finished sessions (#918).** The optional `SessionCloser` protocol and its contract,
   `HerdrRunner.close`, the pure `is_finished` + close step, the drive's probe/close effects and
   `--keep-sessions`, the fr-triage skill prose and both mirror syncs. Requirements R6–R10.

Phase 2 depends on 1: closing an emptied wave workspace (R9) needs the group the first phase
puts on every driven item.

No member issue is a phase `tracking_issue` (batch delivery rule).
