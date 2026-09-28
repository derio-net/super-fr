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

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-09-28T19:55:45+00:00 phase=1 -->
### p1-review · review · Phase 1 review: 2 minor findings (1 fixed, 1 refuted) (phase 1)

Independent reviewer (general-purpose, sonnet) over d37afdba..527cc106 with spec §A and plan 01.yaml. Verdict: ready, no critical/important issues. It confirmed the branch_changes_present lift is byte-for-byte behaviour-preserving (86 hardened tests re-run green). Findings: p1-r1 (private _SCOPE_DIR import, in scope) fixed; p1-r2 (spec owner None, in scope) refuted. Declined to judge: owner semantics for plan/spec journals (§B/§C), list ordering (no caller yet), duplicate-path defence (§B unions first), §B–§G behaviour (later phases).

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-09-28T19:55:45+00:00 phase=1 state=fixed review_scope=in -->
### p1-r1 · finding [fixed] (reviewer: in scope) · fr.closeout imported the module-private fr.journal.model._SCOPE_DIR (phase 1)

closeout.py:21 coupled to a private name nothing lints. Fixed by promoting it to public `SCOPE_DIRS` (its only other users are journal_path/archived_journal_path in the same module), plus test_every_journal_scope_is_classified, which pins that every scope in SCOPE_DIRS is classified with no edit to fr.closeout. Phase 3's archive_twin journal pairs will read the same public map.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-09-28T19:55:45+00:00 phase=1 state=refuted review_scope=in -->
### p1-r2 · finding [refuted] (reviewer: in scope) · BranchArtifact.owner is None for a spec artifact (phase 1)

Refuted: spec §A defines `owner` as "plan dir name / spec slug for followers", and a spec is an owner, not a follower (followers are its spec journal, plus runs/usage for plans). Run/usage owners come from the cursor's `emitted.plan`, which phase 2 (§B) reads. That is planned work in a later phase, not a defect here.

<!-- fr:journal kind=discovery scope=plan id=p2-branch-refs-lift created=2026-09-28T20:07:16+00:00 phase=2 -->
### p2-branch-refs-lift · discovery · verify-merge's ref resolution lifted to fr.isolation.local.resolve_branch_refs (phase 2) (phase 2)

`_branch_refs` was bound to the workspace ops object (it used
`self._run_network`, whose env came from `self._network_env`). It is
now a module-level `resolve_branch_refs(run, repo_root, branch, remote)`
returning `(refs, branch_fetched)` with an EMPTY list when neither ref
resolves; `network_env`/`run_network` moved beside it. The method keeps
its IsolationError on no refs, so verify-merge's behaviour is unchanged
(234 isolation tests green). `fr archive --branch` calls the helper with
`subprocess_runner` and ignores `branch_fetched`: the §B.3 content check
over every resolving ref is its guard, and the brief still runs
verify-merge (PR state included) first.

<!-- fr:journal kind=decision scope=plan id=p2-sweep-report-shape created=2026-09-28T20:07:16+00:00 phase=2 -->
### p2-sweep-report-shape · decision · --branch prints every sweep move but only the branch's own specs' notes, as held lines (phase 2) (phase 2)

§B.4 says "report only its moves" and "a branch spec that stays live
prints held: <spec> — <note>". Every move the sweep makes is staged, so
hiding one would leave an unexplained rename in the operator's commit:
all moves print as `archived:`. The sweep's notes for specs the branch
did NOT touch are dropped (that is the "only"); a branch spec left live
takes its note by `<spec-name>: ` prefix, else the fallback "not every
Implementation Plans row is archived yet" (an active local row yields
no note). The sweep runs when the branch touched a spec or a plan moved,
matching single-plan archive's "sweep after a move".

<!-- fr:journal kind=discovery scope=plan id=p2-emitted-plan-and-private-journal-mover created=2026-09-28T20:07:16+00:00 phase=2 -->
### p2-emitted-plan-and-private-journal-mover · discovery · New public fr.archive.emitted_plan; archive_cmd imports the private _archive_journal the spec names (phase 2) (phase 2)

A held run/usage names its plan from the cursor's `emitted.plan`
(p1-owner-scope-for-run-usage's open question): `emitted_plan(cursor)`
is the reverse of `find_run_for_plan`, reading any cursor version via
`_read_any_version`; usage finds its cursor live, else archived.
BranchArtifact's shape is left as phase 1 made it — the owner is read
at the point of use, no extension needed. `archive_cmd` imports
`fr.archive._archive_journal` because §B.4 names it for debug journals;
it is the same private-import smell review p1-r1 fixed for
`_SCOPE_DIR`, left as is here since promoting it renames six call
sites. Phase 3 (§C's --all debug/orphan journals) will call it too and
may want the public name.

<!-- fr:journal kind=discovery scope=plan id=p2-run-held-even-when-plan-archived created=2026-09-28T20:07:16+00:00 phase=2 -->
### p2-run-held-even-when-plan-archived · discovery · A branch run/usage whose plan is already archived is held, not moved, by --branch (phase 2) (phase 2)

§B.4 says an unmoved run/usage is held naming its plan, with no orphan
exception (unlike plan/spec journals, which follow an already-archived
owner). Implemented literally, with a reason true in both cases:
"follows plan <p>, which did not move in this run". §C's orphan rule (`fr archive --all`, phase 3) is what
clears such a cursor; phase 3 may want --branch to share it.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-09-28T20:07:16+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

GREEN was itself the extraction: verify-merge's bound _branch_refs/_network_env/_run_network became module-level resolve_branch_refs/network_env/run_network with the methods delegating, so there is one ref-resolution path and nothing left to clean; the one duplication T1 introduced (IsolationError -> exit 2) was folded into _refuse_on_isolation_error in P2.T2.S3.
