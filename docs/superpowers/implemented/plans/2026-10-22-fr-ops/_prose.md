# fr ops — implementation plan

Spec: `docs/superpowers/specs/2026-10-22-fr-ops-design.md` (gh#1220).

Four agentic phases, one per independently reviewable ask:

1. **Op model, carriers, evidence, `fr ops status`** (skeleton). The read side and every
   artifact shape change (the new `ops` kind, journal kind 2 → 3), so the migration lands
   first and alone. Its first task is the smoke: an empty `fr ops` group green in CI.
2. **Apply, attest, the ops profile, helpers.** The write side against target systems,
   plus `fr init scaffold --ops` and the two credential-free candidate scenarios.
3. **Gates and deliver.** Test Plan tags, the `devops` promotion in `run_exit`, the
   pre-merge hold in the triage merge path, `fr gate pass --run`, and the PR-body section.
   This depends only on phase 1, because it reads recorded evidence and never applies.
4. **The DevOps stage.** The `fr ops gate` sequencer, the pickup brief, the
   `fr-devops-gate` skill and its mirrors, `docs/ops.md`, and the gate-stage scenario.

Not in this plan, but done at `deliver`: file the frank follow-up issue (migrate
`scripts/ci-budget-ops.sh` to `check`/`apply` fields, and teach `/sync-runbook` to carry
them), file the out-of-scope finding sr-22, and regenerate
`docs/explainers/01-fr-goal.html` on the host.

The live post-merge walk is the spec's single `[devops]` Test Plan step
(`fr-ops-live-first-run`), not a phase.
