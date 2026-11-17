# Acceptance edits and artifact adoption — plan

Spec: `docs/superpowers/specs/2026-11-17-batch-acceptance-edits-design.md`.

Two agentic phases, one per subsystem the batch touches.

**Phase 1 (acceptance, tier hard)** fixes the origin-only reword (#1439, spec §A), adds
the `-design` fragment repair and teaches the merged-row rule to read a merged
`-design` fragment as its one spelling (#1461, §F), and restores the 17 notes the gate
backfill sweep replaced (#1394, §B). It is `hard` because §F changes the merged-row
check every `fr acceptance check` and `deliver` relies on. The skeleton's smoke is its
first task.

**Phase 2 (artifacts and runs, standard)** names an undecodable artifact in every
runner refusal (#1390, §C), moves the four non-triage `git check-ignore` sites onto one
helper in `fr.git` (#1154, §D), and names adopted runs after their plan with a warning
on the default branch (#1219, §E).

No phase names a member issue as its `tracking_issue`. Each phase is TDD: red, green,
then a refactor step. Verification is the CI suite (spec `## Verification`); there is no
Test Plan and no manual phase.
