# Plan-pipeline bugfixes: purity gate, 1-based phases, label normalization

Four authoring/dispatch-pipeline fixes shipped as one PR. Spec:
`docs/superpowers/specs/2026-06-04-plan-pipeline-bugfixes-design.md`.

1. **Agentic-purity gate (#252).** Two error-severity lints in
   `vk plan self-review`: an agentic phase containing a `state: '-'` step whose
   note defers to a later phase, and an agentic step whose text matches a
   conservative manual-operation phrase list. Plus an authoring rule in the
   vk-plan skill: collect all manual steps into a manual phase.
2. **1-based phase numbering.** `PhaseHeader.number >= 1` at schema level
   (pydantic `Field(ge=1)`) plus a pre-flight in `plan_ops.create()` so a bad
   phase list fails before any file is written. Deployment note: frank's live
   `2026-03-25--repo--safe-update-automation` plan has a phase 0 and needs
   operator remediation after upgrade (bridge skips it gracefully meanwhile).
3. **Dispatch pinning.** Verified `diff()` already emits `IssueCreate` for every
   phase, manual included; a pinning test keeps it true.
4. **Label normalization.** `normalize_label_slug()` strips `^YYYY-MM-DD-+`
   (date prefix plus ALL dashes) inside `plan_label()`/`spec_label()`, fixing
   frank's `spec:-auto--…` leading-dash labels and removing dates from plan
   labels. One-time managed-label churn on live issues at next apply/tick.

TDD throughout: every code change lands with its failing test first.
Patch version bump 2.2.14 → 2.2.15 (src/** + skills/** change).
