# ✅ SHIPPED 2026-05-13 via PR #122

This plan is complete (all steps ticked `x`, phase `completion.at` set on the date above). consumed by v2 bridge rebuild (#147) as foundational infrastructure (writeback persists tracking_issue back to plan yaml; bridge depends on this for idempotency)

Original content preserved below.

---

# vk apply tracking_issue writeback

Closes the duplicate-Issue regression where re-running `vk apply --yes` (or
`vk.bridge.tick`) against a plan whose Issues were already created emits
another `IssueCreate` per phase. The dispatch decision in `vk/diff.py:117-132`
pivots per-phase on `phase.tracking_issue is None`; today the URL returned
by `gh.create_issue` is captured into `ApplyResult.created_issues` but never
written back to the plan yaml. The fix is small: persist
`phase.tracking_issue` after every successful `IssueCreate`, and the existing
diff pivot does the rest.

See the design spec at
`docs/superpowers/specs/2026-05-13-vk-apply-tracking-issue-writeback-design.md`
for the full rationale — options considered, overwrite semantics, failure
handling, branch-context / manual-phase / local-only workflow notes, and the
JSON-shape rationale.

## Shape

One phase, four tasks. TDD throughout — each task lands its tests before its
implementation, and ends at an "all green" gate so the implementing agent
can pause cleanly.

- **T1** introduces `plan_ops.set_tracking_issue()` as a new library writer
  mirroring the `tick()` / `complete_phase()` pattern. Helper + unit tests.
- **T2** wires the CLI (`apply_cmd._apply_one`) to call the writer after
  `apply()` returns, with structured failure surfacing in both text and JSON
  output (`tracking_issue_writeback_failures` key, always present).
- **T3** wires the bridge (`bridge/__init__.py::tick`) to do the same, with
  formatted-string failures matching the existing `TickResult.failures`
  contract — no shape change to the daemon-facing surface.
- **T4** flips the most diagnostic assertion (replaces the manual
  `tracking_issue` stamps in `test_v2_full_lifecycle.py` with calls to the
  new helper), updates `vk-dispatch` to remind operators to commit the
  staged writeback, bumps the version triple, and runs the full lint+test
  pass.

## Why this is one phase, not several

The fix is ~300-500 LOC across a tightly-coupled set: one new helper, two
callers that must adopt it, one skill update that depends on the behavior
existing, one version bump that ships when behavior is observable. Splitting
the library primitive into its own phase would land a helper with no
consumers — defensible review-isolation, but disproportionate process for
the size. The "one phase = one PR" convention applies cleanly here.

## Out of scope

- Auto-commit / auto-branch / auto-PR from `vk apply` (deliberately operator-
  driven; revisit only if the bridge gains a different deployment model).
- Backfilling `tracking_issue` for already-orphaned Issues — one-off cases
  hand-edited by operator, or covered by `vk plan migrate` for historical
  v1 → v2 plans.
- Other state writes from apply (e.g. `state.completion.at`) — those flow
  through `vk plan tick` / `complete-phase` and are owned by `vk-execute`.
- Cross-repo `depends_on:` semantics — separate spec backlog (thread #4 in
  the post-v2.1.0 cleanup).
