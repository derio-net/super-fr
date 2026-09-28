# Journal: 2026-09-28-closeout-always

<!-- fr:journal kind=decision scope=plan id=p0-phase-shape created=2026-09-28T19:40:54+00:00 -->
### p0-phase-shape · decision · Six phases, skeleton first, sweep last

P1 skeleton (branch_changed_paths + branch_artifacts + fragment), P2 `fr archive --branch` (hard tier: ref resolution, per-kind held lines), P3 owed_artifacts + status + archive --all + archive_twin, P4 brief split / `fr pickup --branch`, P5 skill relays + both mirror generators + tripwire + explainer check, P6 the one-time sweep checked against `fr status`'s owed set. No manual phase: the post-merge Test Plan walk is operator-driven at close-out. #733 is no phase's tracking_issue.

<!-- fr:journal kind=discovery scope=plan id=p1-scope-dir-reuse created=2026-09-28T19:48:54+00:00 phase=1 -->
### p1-scope-dir-reuse · discovery · branch_artifacts reuses fr.journal.model._SCOPE_DIR (private) rather than a new literal (phase 1)

§A says to reuse fr.journal.model's scope constants rather than new
string literals. `_SCOPE_DIR` (scope -> dir name, e.g. "spec" ->
"specs") is the only such mapping and it is module-private (leading
underscore) with no `__all__` boundary in that module. `fr.closeout`
imports it directly and inverts it once (dir name -> scope) rather
than hand-writing {"specs": "spec", "plans": "plan", "debug": "debug"}
a second time. ruff's selected rule set (E,F,I,N,W,UP) does not include
SLF001, so this does not trip lint; flagged here in case a later phase
wants `_SCOPE_DIR` promoted to a public name instead.

<!-- fr:journal kind=discovery scope=plan id=p1-owner-scope-for-run-usage created=2026-09-28T19:48:54+00:00 phase=1 -->
### p1-owner-scope-for-run-usage · discovery · BranchArtifact.owner is None for spec/run/usage in this phase — §B/§C derive it from cursor content, not path (phase 1)

The spec's BranchArtifact docstring reads "plan dir name / spec slug
for followers; journal scope for journals". P1.T2's Test Plan item
only exercises plan-dir collapsing and journal scope ownership, so
this phase leaves owner=None for spec, run and usage artifacts:
a run/usage's owning plan is `emitted.plan` inside the cursor file,
which §B/§C (fr archive --branch, owed_artifacts) read once they
exist — deriving it from the path alone would be guessing ahead of
that data. Left open for phase 2/3 to either confirm this shape or
extend BranchArtifact once the real owner-resolution need is in view.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-28T19:48:54+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

GREEN already lands the shared shape: branch_changed_paths and branch_changes_present both call the new _branch_fork_and_changes helper, so there is exactly one merge-base/fork computation path and nothing left to extract.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-09-28T19:48:54+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

branch_artifacts is one flat classification function over constants imported from their owning modules; its only smell (the private _SCOPE_DIR import) is left to review as discovery p1-scope-dir-reuse rather than widened here.
