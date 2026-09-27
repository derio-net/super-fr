# Triage batch launch — implementation plan

Spec: `docs/superpowers/specs/2026-09-27-triage-batch-launch-design.md` (closes super-fr#704, super-fr#687).

Two phases, one per issue, in dependency order: both edit `render_brief`, and #687's debug brief is
written against the brief #704 leaves behind (no subagent-model line).

- **Phase 1 (#704, walking skeleton):** `resolve_launch` gains the orchestrator rung and reports
  `model_source`; dispatch reads the binding from the target checkout's `docs/superpowers/models.yaml`
  over the user config; the brief stops pinning subagent models. Change fragment lands here.
- **Phase 2 (#687):** `Batch.skill` (goal|debug, default goal, so schema-2 files load unchanged),
  `batch_branch(batch)` / `batch_workflow(batch)`, the debug brief, `--skill`, and the
  mixed-theme warning; docs and both mirror syncs.

No member issue is a phase `tracking_issue`: the batch bridge owns neither.
