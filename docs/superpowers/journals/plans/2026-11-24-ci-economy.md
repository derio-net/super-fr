<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-ci-economy

<!-- fr:journal kind=decision scope=plan id=p1-replaced-cancel-is-dropped created=2026-11-24T15:50:24+00:00 phase=1 -->
### p1-replaced-cancel-is-dropped · decision · slot_check drops a cancelled run that another run of the same name replaces (phase 1)

The plan said "keep the verdict rules otherwise", but with CANCELLED now pending, a
combination whose check was cancelled and then re-run green would stay pending
forever (any run pending -> pending). Spec R4 scopes the rule to "a cancelled
required check that no newer run replaces", so `queue_exec._unreplaced` drops a
cancelled run when any non-cancelled run of the same name exists before the verdict
and the `late` list are computed. Test:
test_a_cancelled_check_replaced_by_a_newer_run_reads_as_the_newer_run.

<!-- fr:journal kind=decision scope=plan id=p1-cancelled-need-wording created=2026-11-24T15:50:24+00:00 phase=1 -->
### p1-cancelled-need-wording · decision · read_slots words a cancelled check's Need apart from a never-reported one (phase 1)

The existing Need blamed a workflow missing `push: branches: ['fr-queue/**']`, which
is wrong for a check that ran and was cancelled. read_slots now emits a second Need,
"check X was cancelled on combination <sha> and no run replaced it within N min:
re-run the cancelled workflow on <sha>", for late names that did report.

<!-- fr:journal kind=decision scope=plan id=p1-rest-bucket-keeps-gh-names created=2026-11-24T15:50:24+00:00 phase=1 -->
### p1-rest-bucket-keeps-gh-names · decision · The REST client keeps gh's `cancel` and `skipping` bucket names (phase 1)

`real_ghrestclient._BUCKET` became `_bucket(state)`: SKIPPED/NEUTRAL -> skipping,
CANCELLED -> cancel (both as `gh pr checks` renders them), every other state through
`fr.checkstate.verdict_of`. Readers turn a bucket into a verdict with
`bucket_verdict`, so `cancel` is pending everywhere. `batch_merge.FAILING_BUCKETS` was
dropped rather than aliased: no other module imported it.

<!-- fr:journal kind=discovery scope=plan id=p1-verify-ci-cancelled-gate created=2026-11-24T15:50:24+00:00 phase=1 -->
### p1-verify-ci-cancelled-gate · discovery · verify_ci waits on a cancelled gate without marking its workflow busy (phase 1)

A cancelled finished gate check joins the `running` list and the `_where` text, but
not the `unfinished` list that decides which workflows are busy, so a failed gate in
the same workflow is still refused rather than read as a re-run in flight. A
skipped gate still refuses (only success passes there), unchanged.

<!-- fr:journal kind=discovery scope=plan id=p1-docs-currency created=2026-11-24T15:50:24+00:00 phase=1 -->
### p1-docs-currency · discovery · Seven covered pages owed a stamp; the wave-driver explainer gained one paragraph (phase 1)

`fr docs check` named fr-devops-gate, fr-triage, fr-wave-driver, index,
herdr-control-sessions, ops and workflow-shapes. Only fr-wave-driver.md describes
how the queue reads checks; it now says a cancelled check waits for its replacement
and shows under Needs you now after queue.check_wait_minutes. The rest got a
`reviewed` note. The row ci-cancelled-reads-pending moved not-implemented -> ci with
eight unit refs (fr acceptance set-status, its own commit).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-24T15:50:24+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

fr/checkstate.py was written green in its final shape (four constants, three pure functions); the only cleanup, moving the test's imports to the top, landed in the same commit

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-24T15:50:24+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the late list reuses slot_check's existing by-name grouping; the shared overdue test was factored as it was written, and read_slots' wording split is two short branches

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-24T17:11:51+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · verify_ci waits forever (exit 75) on a cancelled gate nothing replaces (phase 1)

ci_evidence.py: a cancelled gate with no unfinished check raised CiPending with a 'when CI finishes' message; before this change it refused clearly.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-24T17:11:51+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · settle/evaluate.py still compared bucket == 'pending' for `running` (phase 1)

A cancelled check was not counted as running while a gate was absent; missed reader.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-24T17:11:51+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · the check-state tripwire only paired cancel with fail/failure and skipped lists (phase 1)

A set like {CANCELLED, TIMED_OUT} or a list escaped it.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-24T17:11:51+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · queue_exec._unreplaced keyed on name alone (phase 1)

commit_checks de-duplicates per (workflow, name), so another workflow's same-named run wrongly replaced a cancel.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-24T17:11:51+00:00 phase=1 state=open review_scope=out -->
### p1-r5 · finding [open] (reviewer: out of scope) · real_glabclient._CI_FAIL still treats canceled as failing (phase 1)

The spec exempts GitLab (gh#611); not caused by this change.

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-11-24T17:11:51+00:00 phase=1 -->
### p1-review-1 · review · phase 1 review: 4 in-scope findings fixed, 1 out of scope (phase 1)

Independent reviewer read spec, plan and the phase diff; every reader conversion verified correct; raised p1-r1..p1-r5. All in-scope findings fixed in 669a5e7e7 with tests (test_run_ci_evidence: stranded cancelled gate refused, running cancel waits; test_settle_evaluate: cancelled counts as running; test_queue_exec: per-workflow replacement; tripwire widened). Spec R3 amended for p1-r1.

<!-- fr:journal kind=lens scope=plan id=lens-errors-1 created=2026-11-24T17:11:51+00:00 phase=1 lens=errors step=review-phase -->
### lens-errors-1 · lens · every new pending path (verify_ci, queue, settle) must bound its wait and say who is told (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-24T17:11:51+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: verify_ci waits forever (exit 75) on a cancelled gate nothing replaces (phase 1)

verify_ci refuses a cancelled gate once nothing on the sha runs, naming the gate and the re-run (669a5e7e7); pending only while a run is in flight; spec R3 amended.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-24T17:11:51+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: settle/evaluate.py still compared bucket == 'pending' for `running` (phase 1)

settle/evaluate.py:151 reads through bucket_verdict; test_a_cancelled_check_counts_as_running_while_a_gate_is_absent.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-24T17:11:51+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: the check-state tripwire only paired cancel with fail/failure and skipped lists (phase 1)

Tripwire pairs any cancelled spelling with any FAILED_STATES member or 'fail', and scans list literals.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-24T17:11:51+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: queue_exec._unreplaced keyed on name alone (phase 1)

_unreplaced keys on (workflow, name); late lists a required name with any unreplaced cancel; test added.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-24T17:11:51+00:00 phase=1 state=open resolves=p1-r5 out_of_scope=true -->
### p1-r5-resolved · finding [out-of-scope] · resolves p1-r5: real_glabclient._CI_FAIL still treats canceled as failing (phase 1)

GitLab's reader is outside the queue and exempt by the spec (Design §A, gh#611); this change did not touch it.

<!-- fr:journal kind=decision scope=plan id=p2-verdict-needs-classify created=2026-11-24T18:08:41+00:00 phase=2 -->
### p2-verdict-needs-classify · decision · ci_lane verdict requires classify to succeed in every lane (phase 2)

R17 names the classifier only for the landed lane. A failed classify leaves no lane
(and the lane check already fails), but the verdict also lists `classify` among each
lane's required jobs, so a reason names it directly. Any result but success or
skipped (an unknown one included) fails like failure and cancelled.

<!-- fr:journal kind=decision scope=plan id=p2-landed-strict-match created=2026-11-24T18:08:41+00:00 phase=2 -->
### p2-landed-strict-match · decision · landed_run matches path, event, head_branch prefix, conclusion and a different id exactly (phase 2)

`path` must equal `.github/workflows/ci.yml` (the captured payloads carry no `@ref`
suffix), `event` push, `head_branch` start with `fr-queue/`, `conclusion` success
and an integer id other than this run's. Any other payload shape, a non-zero `gh`
exit, non-JSON or a missing `gh` reads `full`. The fixtures are captures of this
repo's own runs (tests/fixtures/ci_lane/README.md); no fr-queue run existed yet, so
the queue case changes only `head_branch` on the captured CI run.

<!-- fr:journal kind=discovery scope=plan id=p2-pinned-tests-moved created=2026-11-24T18:08:41+00:00 phase=2 -->
### p2-pinned-tests-moved · discovery · Five workflow-shape tests pinned what the lanes change (phase 2)

test_ci_shards (ci-ok's old RESULTS case script; now runs ci_lane.py verdict as a
subprocess), test_ci_merge_group (change-fragment keeps its condition, lane rule
appended; a skipped change-fragment passes the full-lane verdict),
test_ci_split_workflow (split-check needs classify), test_pages_workflow and
test_docs_currency_flows (site-build and docs-check skip only in the landed lane,
where the fr-queue run on the same sha already ran them). ci-ok now checks out the
repo and sets up uv to run the verdict script.

<!-- fr:journal kind=discovery scope=plan id=p2-docs-currency created=2026-11-24T18:08:41+00:00 phase=2 -->
### p2-docs-currency · discovery · fr docs check names no page for ci.yml or scripts/ci_lane.py (phase 2)

`uv run fr docs check --base origin/main` reports 32 pages current: no page covers
.github/workflows/ci.yml or scripts/. AGENTS.md's CI job list and a CI lanes
paragraph after Tiers were updated.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-24T18:08:41+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

lane_for and pull_request_lane were written green in final shape; the only cleanup (ruff format) landed in the task's commit

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-24T18:08:41+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

landed_run is one filter and landed_lane one fallible read; the long test lines were wrapped in the same commit

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-11-24T18:08:41+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

verdict is one table of required and skippable jobs per lane; the test helper name clash was fixed before the commit

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-24T18:13:34+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · test_validate_artifacts_runs_in_every_lane does not pin the strict step's if (phase 2)

tests/unit/test_ci_lanes_workflow.py: dropping or inverting the strict step's condition would leave main with only --allow-migratable, all green.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-24T18:13:34+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · landed_run's exact path match is unverified for real fr-queue runs (phase 2)

scripts/ci_lane.py: a path with an @ref suffix would silently disable the landed skip (fails safe).

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-24T18:13:34+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · classify installs uv and Python 3.14 at the head of every run's critical path (phase 2)

Every job waits on classify; a stdlib-only script needs no install.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-24T18:13:34+00:00 phase=2 state=open review_scope=out -->
### p2-r4 · finding [open] (reviewer: out of scope) · a manual re-run of an older run in a PR's concurrency group cancels the newer in-progress run (phase 2)

GitHub concurrency semantics of R1's per-ref group; the head's ci-ok then reads cancelled (pending in fr's readers). Not a defect of this diff.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-24T18:13:34+00:00 phase=2 state=open review_scope=out -->
### p2-r5 · finding [open] (reviewer: out of scope) · light-lane soundness for docs-only PRs depends on R19/R20 (a later phase) (phase 2)

Phase 3 ships own_artifacts selection.

<!-- fr:journal kind=review scope=plan id=p2-review-1 created=2026-11-24T18:13:34+00:00 phase=2 -->
### p2-review-1 · review · phase 2 review: no critical findings; 3 in-scope fixed, 2 out of scope (phase 2)

Independent reviewer checked concurrency, ci-ok always()/toJSON(needs), skip propagation, light classification (HEAD^2, merge base, renames), landed match and token, strict validation on main, scoped-tests env, verdict vs R17; raised p2-r1..p2-r5. Fixes in the commit 'fix(ci): pin validate-artifacts' step conditions...': both validate steps' if pinned; landed_run ignores an @ref suffix (test); classify runs on the runner's python3 with no uv, ci_lane.py made Python-3.10-parseable (two except clauses) and pinned by a test.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-24T18:13:34+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: test_validate_artifacts_runs_in_every_lane does not pin the strict step's if (phase 2)

test_validate_artifacts_runs_in_every_lane asserts both steps' if strings.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-24T18:13:34+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: landed_run's exact path match is unverified for real fr-queue runs (phase 2)

landed_run compares path.split('@')[0]; test_a_path_with_a_ref_suffix_still_names_the_ci_workflow.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-24T18:13:34+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: classify installs uv and Python 3.14 at the head of every run's critical path (phase 2)

classify drops setup-uv and runs python3 scripts/ci_lane.py; test_classify_runs_on_the_runners_own_python and a Python 3.10 parse test.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-24T18:13:34+00:00 phase=2 state=open resolves=p2-r4 out_of_scope=true -->
### p2-r4-resolved · finding [out-of-scope] · resolves p2-r4: a manual re-run of an older run in a PR's concurrency group cancels the newer in-progress run (phase 2)

A GitHub concurrency behaviour on a rare manual re-run of an old run; this diff did not cause it, and fr reads the cancelled ci-ok as pending, not red.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-24T18:13:34+00:00 phase=2 state=refuted resolves=p2-r5 -->
### p2-r5-resolved · finding [refuted] · resolves p2-r5: light-lane soundness for docs-only PRs depends on R19/R20 (a later phase) (phase 2)

Not a defect: phase 3 of this same PR ships R19/R20 (own_artifacts selection) before delivery; the PR is never delivered with phase 2 alone.

<!-- fr:journal kind=decision scope=plan id=p3-root-climb-depth created=2026-11-24T20:27:17+00:00 phase=3 -->
### p3-root-climb-depth · decision · The tripwire flags a __file__ climb only when it reaches the checkout root (phase 3)

R20 names `Path(__file__)...parents[...]`. Read literally that flags every module
reading `tests/fixtures` (`parents[1] / "fixtures"`), which reads nothing a
docs/.fr/.changes change moves. `_climbs` counts the levels an expression stands
above `__file__` (`.parent` +1, `.parents[k]` +k+1, `resolve()`/`absolute()`/`Path()`
neutral, `os.path.dirname` +1, through module names bound in two steps) and flags
only a climb that reaches the module's own depth, i.e. the root.

<!-- fr:journal kind=decision scope=plan id=p3-alias-by-binding created=2026-11-24T20:27:17+00:00 phase=3 -->
### p3-alias-by-binding · decision · A root alias counts by what it is bound to, not by its name (phase 3)

`REPO` is the commonest alias in tests/ for the root and also the commonest name for a
repo slug (`REPO = "example-org/demo"`); a name match flagged 130 modules that read no
checkout file. So an alias the module binds is judged by its binding (a climb, or a
helper import that exposes the root); an alias named without a binding (a star
import) is flagged, and so is a test asking for conftest's `repo_root` fixture
unless the module defines its own.

<!-- fr:journal kind=discovery scope=plan id=p3-marked-modules created=2026-11-24T20:27:17+00:00 phase=3 -->
### p3-marked-modules · discovery · 250 test modules resolve the root; all now carry own_artifacts (phase 3)

225 got a new `pytestmark = pytest.mark.own_artifacts` after their imports (88 of them
also `import pytest`); 25 had a single-mark `pytestmark`, merged into a list. Many are
flagged transitively: `tests/unit/record_support.py` imports
`tests/integration/test_fr_goal_shape.py`'s helpers, which read the shipped workflow
from the root. A plain `pytest --collect-only` selects the same 18369/18516 before and
after.

<!-- fr:journal kind=discovery scope=plan id=p3-tripwire-blind-spots created=2026-11-24T20:27:17+00:00 phase=3 -->
### p3-tripwire-blind-spots · discovery · What the own_artifacts tripwire cannot see (phase 3)

Stated in its docstring: a test that reaches the checkout only through a subprocess
whose cwd it does not pass, a root found at run time (`Path.cwd()`,
`git rev-parse --show-toplevel`, a package's `__file__`), and a fixture other than
`repo_root` that hands the root over.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-11-24T20:27:17+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

root_readers was restructured for speed and precision before the RED commit (per-module analysis computed once); GREEN was a mechanical marker insertion with nothing left to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-24T20:27:17+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

touches_own_artifacts and the keep_item flag were written in their final shape; the conftest wiring is two lines

<!-- fr:journal kind=review scope=plan id=review-p3 created=2026-11-24T20:32:58+00:00 phase=3 -->
### review-p3 · review · Phase 3 review (own_artifacts marker, fr-scope selection, tripwire) (phase 3)

Independent reviewer read d73314be3..e858898c6 against R19/R20. touches_own_artifacts, the
conftest wiring (scenario always dropped) and the pytestmark mass edit are correct. Three
tripwire findings: p3-r1 fixed, p3-r2 fixed in part, p3-r3 refuted.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-24T20:32:58+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · _is_marked counted a mark on one test as marking the whole module (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-24T20:32:58+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · _climbs missed a name holding .parents then indexed, negative indexes and ../.. joins (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-24T20:32:58+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · ROOT_ALIASES is a hand-kept list (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-24T20:32:58+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: _is_marked counted a mark on one test as marking the whole module (phase 3)

_is_marked now reads only a module-level pytestmark assignment. test_a_mark_on_one_test_does_not_cover_the_module pins that a module with one marked test and one unmarked root reader is flagged. No module in tests/ relied on a per-test mark, and the real-repo tripwire stays green.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-24T20:32:58+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: _climbs missed a name holding .parents then indexed, negative indexes and ../.. joins (phase 3)

_climbs treats X.parents as one above X, so a name holding .parents and indexed later counts (test_a_name_holding_parents_then_indexed_is_flagged). parents[-1] is the filesystem root, not the checkout, so it is correctly not a root climb. No test module in tests/ joins "../..", and the docstring already says the tripwire is not sound against every spelling.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-24T20:32:58+00:00 phase=3 state=refuted resolves=p3-r3 -->
### p3-r3-resolved · finding [refuted] · resolves p3-r3: ROOT_ALIASES is a hand-kept list (phase 3)

The alias list only covers names a module uses without binding them (star imports from conftest). A new alias a helper defines by climbing from __file__ is caught through the helper-import path whatever its name, and an alias a module binds is judged by what it is bound to. A new unbound name would need a new star-imported constant in conftest, which is the case the dated list documents.

<!-- fr:journal kind=decision scope=plan id=p4-regen-value created=2026-11-24T21:40:00+00:00 phase=4 -->
### p4-regen-value · decision · The builder takes one Regen value; QueuePorts keeps mirrors and generated as the spec names them (phase 4)

`QueuePorts` gains `mirrors` and `generated` (spec §C); `_build` folds them into a frozen
`queue_exec.Regen(mirrors, generated, timeout=600)` that `build` threads to `_resolve`, so the
signatures grow by one argument rather than three. A failed mirror raises
`MirrorFailedError(MergeConflictError)`, whose words become the BuildConflict's reason, so the
hand-back names the command (R11).

<!-- fr:journal kind=decision scope=plan id=p4-stamp-needs-no-mirror created=2026-11-24T21:40:00+00:00 phase=4 -->
### p4-stamp-needs-no-mirror · decision · A stamp-only conflict resolves with no mirrors; a generated conflict with none is real (phase 4)

R11's "a repo that declares no mirrors treats every such path as a real conflict" is read as
the generated kinds only (whole generated paths and generated-block hunks): a `reviewed:`
stamp hunk needs no command, and the plan's case (c) builds it with no mirrors declared.
`Classified.regenerate` names the hunk paths that took a generated block.

<!-- fr:journal kind=decision scope=plan id=p4-mirror-sandbox-scope created=2026-11-24T21:40:00+00:00 phase=4 -->
### p4-mirror-sandbox-scope · decision · The mirror hardening is defence in depth, not a sandbox (phase 4)

The queue admits only entries the operator approved or a trust rule attributed, and CI runs
the same combination, so the PR code a mirror runs has passed the operator's trust gate.
What is added is proportionate on the driver host (p4-mirror-export); a container or VM is
out of scope (p4-s6). Nothing in the spec's wording blocked any of it.

<!-- fr:journal kind=decision scope=plan id=p4-mirror-export created=2026-11-24T21:40:00+00:00 phase=4 -->
### p4-mirror-export · decision · The mirrors never see a git directory; they run in a git-less export of the combination (phase 4)

Three security rounds showed that guarding the scratch worktree's git dir piecemeal (a
snapshot/restore of config and hooks, hardened git flags) does not converge: the gitdir can
be redirected through `.git`/`commondir`, the restore followed symlinks in `hooks/`, and a
background child could write after the comparison. The guard is replaced by a structural
invariant. `_regenerate` exports the resolved worktree's tracked files
(`Worktree.export_tracked`: regular files with their mode, symlinks recreated, never
followed) into a fresh temp dir with no `.git`; each `mirrors:` argv runs there
(`gitseam.run_mirror`: `mirror_env` as the whole environment, an empty temp HOME and XDG
config/data dirs, uv's cache and Python dirs resolved from the parent env first, the
explicit UV_* list, `start_new_session=True`, and `os.killpg` of the group once it exits or
times out). `snapshot_export` diffs the export before and after (new paths the repo ignores,
like `.venv` and `__pycache__`, asked of the scratch worktree's rules, are no change); a
change outside the `generated:` globs and blocks, a changed path that is not a regular file,
or markers left hand the entry back. Only the changed generated paths are copied back
(`Worktree.take_generated`: each parent lstat-checked, `O_NOFOLLOW`). The git-state guard,
`HARDENED_GIT` and the cached dirs are deleted, and `GIT_CONFIG_GLOBAL`/`NOSYSTEM` are out of
the env. Checked live: super-fr's five mirrors run in a git-less export of this worktree
(sync-readme 6.5 s, the rest under 0.5 s) and change nothing outside the globs.

<!-- fr:journal kind=discovery scope=plan id=p4-facts-not-an-artifact created=2026-11-24T21:40:00+00:00 phase=4 -->
### p4-facts-not-an-artifact · discovery · facts.json is not a registered artifact kind; FACTS_READS derives from FACTS_SCHEMA (phase 4)

facts.json lives in the triage state directory, not under an artifact locator, so the bump to
17 needs no migration. `FACTS_READS = range(3, FACTS_SCHEMA + 1)`, so 16 still loads; the one
pin in test_triage_model.py moved, the refused-stamp case moved from 17 to 18, and a schema-16
file with a `mirrors`-only config now reads `generated == []`.

<!-- fr:journal kind=discovery scope=plan id=p4-docs-currency created=2026-11-24T21:40:00+00:00 phase=4 -->
### p4-docs-currency · discovery · fr docs check named cli.md; the wave-driver explainer gained the queue's conflict rules (phase 4)

`fr docs check --base origin/main` named only docs/reference/cli.md (triage_batch_cmd.py moved,
no help text did: stamp bumped). docs/explainers/fr-wave-driver.md now says which conflicts the
queue settles, that the mirrors are the base's while the scripts are the PRs', and what the
hardening does and does not do. The fr-triage skill says the same; both mirrors re-synced.

<!-- fr:journal kind=discovery scope=plan id=p4-fast-tier-scope created=2026-11-24T21:40:00+00:00 phase=4 -->
### p4-fast-tier-scope · discovery · The declared fast tier selects 18,452 of 18,599 tests on this branch; a neighbour run stood in (phase 4)

`uv run pytest --fr-scope origin/main -n 2` reaches nearly the whole suite on this branch
(phase 3 touched 250 test modules and the conftest; the facts model is imported everywhere),
and on a host at load ~18 it ran at about 3% per quarter hour, so it was stopped. Scoped to
this phase's base (`--fr-scope 1fdc627f7`) it still selects 9,756. Instead the touched tests
and their neighbours ran (`tests/unit/test_triage*.py`, `test_queue*`, `test_wave_queue*`,
`tests/integration/test_queue*.py`, every `test_tripwire_*`, the smoke, settings, validate and
import-direction tests): 4,413 passed, 4 failed, the four committed scenario facts fixtures
generated at schema 16. Regenerated with their own generators (schema 17), the fixture tests
and `tests/integration/test_scenarios.py` (`-m ""`) then passed, 95 tests. CI is this repo's
suite evidence (`tests: ci`).

<!-- fr:journal kind=finding scope=plan id=p4-s1 created=2026-11-24T21:40:00+00:00 phase=4 state=open review_scope=in -->
### p4-s1 · finding [open] (reviewer: in scope) · A conflicted path with no marker hunk, or not two regular blobs, counted as hunk-resolved (phase 4)

Security review: classify_conflicts resolved any text it could read, so a modify/delete, a
binary add/add, a type change or a marker-less file was "resolved" as it stood. Reproduced red
by test_a_stamp_page_one_entry_deleted_is_a_real_conflict and
test_a_binary_add_add_conflict_is_a_real_conflict (both built without raising).

<!-- fr:journal kind=finding scope=plan id=p4-s2 created=2026-11-24T21:40:00+00:00 phase=4 state=open review_scope=in -->
### p4-s2 · finding [open] (reviewer: in scope) · Mirrors run PR-controlled code with the driver's whole environment (phase 4)

Security review: run_argv inherited every variable (GH_TOKEN, FR_*, SSH_AUTH_SOCK). Red:
test_a_mirror_runs_with_no_forge_credential_or_ssh_agent saw all of them.

<!-- fr:journal kind=finding scope=plan id=p4-s3 created=2026-11-24T21:40:00+00:00 phase=4 state=open review_scope=in -->
### p4-s3 · finding [open] (reviewer: in scope) · A mirror could write the common git dir's hooks or config, which later git calls run (phase 4)

Security review (HIGH): the scratch worktree is linked, so its common dir is the clone's
`.git`. Red: the planted hook and core.fsmonitor stayed and the build pushed; a clone's
post-commit hook ran for the rebase commit made after the mirrors.

<!-- fr:journal kind=finding scope=plan id=p4-s4 created=2026-11-24T21:40:00+00:00 phase=4 state=open review_scope=in -->
### p4-s4 · finding [open] (reviewer: in scope) · Mirrors inherited the operator's HOME, reaching ~/.config/gh, ~/.ssh, ~/.netrc (phase 4)

Security review (MEDIUM).

<!-- fr:journal kind=finding scope=plan id=p4-s5 created=2026-11-24T21:40:00+00:00 phase=4 state=open review_scope=in -->
### p4-s5 · finding [open] (reviewer: in scope) · Mirrors kept every UV_* not named like a credential, index URLs included (phase 4)

Security review (MEDIUM).

<!-- fr:journal kind=finding scope=plan id=p4-s7 created=2026-11-24T21:40:00+00:00 phase=4 state=open review_scope=in -->
### p4-s7 · finding [open] (reviewer: in scope) · The git-state guard's cached dirs could be redirected through `.git` or `commondir` (phase 4)

Security review, round three.

<!-- fr:journal kind=finding scope=plan id=p4-s8 created=2026-11-24T21:40:00+00:00 phase=4 state=open review_scope=in -->
### p4-s8 · finding [open] (reviewer: in scope) · The git-state restore followed symlinks in hooks/ (phase 4)

Security review, round three.

<!-- fr:journal kind=finding scope=plan id=p4-s9 created=2026-11-24T21:40:00+00:00 phase=4 state=open review_scope=in -->
### p4-s9 · finding [open] (reviewer: in scope) · A background child of a mirror could write after the comparison (TOCTOU) (phase 4)

Security review, round three.

<!-- fr:journal kind=finding scope=plan id=p4-s6 created=2026-11-24T21:40:00+00:00 phase=4 state=open review_scope=out -->
### p4-s6 · finding [open] (reviewer: out of scope) · Mirrors run as the driver's user on its host; no container or VM isolates them (phase 4)

A container or VM sandbox for mirror commands is out of scope for this feature (operator's
direction): the entries have passed the queue's trust gate and CI runs the same code. The
in-process hardening (p4-s2..p4-s5) is defence in depth only.

<!-- fr:journal kind=finding scope=plan id=p4-acceptance-anchor created=2026-11-24T21:40:00+00:00 phase=4 state=open review_scope=in -->
### p4-acceptance-anchor · finding [open] (reviewer: in scope) · ci-cancelled-reads-pending cited a test the phase 1 review renamed (phase 4)

`fr acceptance check` failed on `test_run_ci_evidence.py#test_a_cancelled_gate_is_pending_never_refused`,
renamed in 669a5e7e7 into two tests; the row is re-pointed to both.

<!-- fr:journal kind=finding scope=plan id=p4-s1-resolved created=2026-11-24T21:40:00+00:00 phase=4 state=fixed resolves=p4-s1 -->
### p4-s1-resolved · finding [fixed] · resolves p4-s1: A conflicted path with no marker hunk, or not two regular blobs, counted as hunk-resolved (phase 4)

ebdc00b12: classify_conflicts takes the unmerged index stages (Worktree.unmerged_stages, `git
ls-files -u`); a hunk path needs stages 2 and 3 as regular blobs and at least one resolved
hunk, a whole generated path a regular stage 2; anything else is real. Unit tests for
modify/delete both ways, a symlink type change, a submodule, no stages and no markers.

<!-- fr:journal kind=finding scope=plan id=p4-s2-resolved created=2026-11-24T21:40:00+00:00 phase=4 state=fixed resolves=p4-s2 -->
### p4-s2-resolved · finding [fixed] · resolves p4-s2: Mirrors run PR-controlled code with the driver's whole environment (phase 4)

Superseded by the export design (p4-mirror-export): `gitseam.run_mirror` passes `mirror_env`
as the WHOLE environment, in a git-less export. `mirrors:` come from the collected base
config, pinned by test_the_mirrors_are_the_bases_never_a_queued_prs (a PR rewriting them
changes nothing). Tests: test_a_mirror_runs_with_no_forge_credential_or_ssh_agent. The trust
boundary is in regen.py's docstring, the fr-triage skill and the wave-driver explainer.

<!-- fr:journal kind=finding scope=plan id=p4-s3-resolved created=2026-11-24T21:40:00+00:00 phase=4 state=fixed resolves=p4-s3 -->
### p4-s3-resolved · finding [fixed] · resolves p4-s3: A mirror could write the common git dir's hooks or config, which later git calls run (phase 4)

Superseded by the export design (p4-mirror-export): the mirror runs in a temp copy with no
`.git` and no link to any git dir, so it cannot reach hooks, config or a commondir, and its
process group is killed when it ends. Tests: test_a_mirror_sees_no_git_directory,
test_git_itself_finds_no_repository_where_a_mirror_runs,
test_a_background_child_of_a_mirror_is_killed (red with killpg disabled),
test_a_generated_path_turned_into_a_symlink_hands_back,
test_only_the_generated_changes_are_copied_back,
test_a_mirror_writing_outside_the_generated_files_hands_the_entry_back.

<!-- fr:journal kind=finding scope=plan id=p4-s4-resolved created=2026-11-24T21:40:00+00:00 phase=4 state=fixed resolves=p4-s4 -->
### p4-s4-resolved · finding [fixed] · resolves p4-s4: Mirrors inherited the operator's HOME, reaching ~/.config/gh, ~/.ssh, ~/.netrc (phase 4)

Export design (p4-mirror-export): HOME, XDG_CONFIG_HOME and XDG_DATA_HOME point into a
fresh temp dir; UV_CACHE_DIR and UV_PYTHON_INSTALL_DIR are resolved from the parent env
first (uv's own defaults). uv checked to run the real sync scripts this way. Pinned by
test_mirror_env_names_its_variables_and_swaps_home.

<!-- fr:journal kind=finding scope=plan id=p4-s5-resolved created=2026-11-24T21:40:00+00:00 phase=4 state=fixed resolves=p4-s5 -->
### p4-s5-resolved · finding [fixed] · resolves p4-s5: Mirrors kept every UV_* not named like a credential, index URLs included (phase 4)

Export design (p4-mirror-export): MIRROR_UV_NAMES is the explicit list UV_CACHE_DIR,
UV_PYTHON_INSTALL_DIR, UV_PYTHON, UV_NO_PROGRESS, UV_OFFLINE, UV_FROZEN; UV_INDEX_URL and
UV_EXTRA_INDEX_URL are dropped (same test).

<!-- fr:journal kind=finding scope=plan id=p4-s7-resolved created=2026-11-24T21:40:00+00:00 phase=4 state=fixed resolves=p4-s7 -->
### p4-s7-resolved · finding [fixed] · resolves p4-s7: The git-state guard's cached dirs could be redirected through `.git` or `commondir` (phase 4)

Export design (p4-mirror-export) - the mirror sees no git dir, and the guard and its cached dirs are deleted.

<!-- fr:journal kind=finding scope=plan id=p4-s8-resolved created=2026-11-24T21:40:00+00:00 phase=4 state=fixed resolves=p4-s8 -->
### p4-s8-resolved · finding [fixed] · resolves p4-s8: The git-state restore followed symlinks in hooks/ (phase 4)

Export design (p4-mirror-export) - nothing is restored any more; copy-back is lstat-checked per component and O_NOFOLLOW.

<!-- fr:journal kind=finding scope=plan id=p4-s9-resolved created=2026-11-24T21:40:00+00:00 phase=4 state=fixed resolves=p4-s9 -->
### p4-s9-resolved · finding [fixed] · resolves p4-s9: A background child of a mirror could write after the comparison (TOCTOU) (phase 4)

Export design (p4-mirror-export) - each mirror runs in its own session and its process group is killed once it ends; test_a_background_child_of_a_mirror_is_killed.

<!-- fr:journal kind=finding scope=plan id=p4-s6-resolved created=2026-11-24T21:40:00+00:00 phase=4 state=open resolves=p4-s6 out_of_scope=true -->
### p4-s6-resolved · finding [out-of-scope] · resolves p4-s6: Mirrors run as the driver's user on its host; no container or VM isolates them (phase 4)

A sandboxing container/VM for mirrors is outside this feature by the operator's direction.

<!-- fr:journal kind=finding scope=plan id=p4-acceptance-anchor-resolved created=2026-11-24T21:40:00+00:00 phase=4 state=fixed resolves=p4-acceptance-anchor -->
### p4-acceptance-anchor-resolved · finding [fixed] · resolves p4-acceptance-anchor: ci-cancelled-reads-pending cited a test the phase 1 review renamed (phase 4)

Row re-pointed with fr acceptance set-status (--drop-level/--level).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-11-24T21:40:00+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

two additive lines (a defaulted list field and the stamp with its comment); nothing to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t2 created=2026-11-24T21:40:00+00:00 phase=4 -->
### no-refactor-p4-t2 · discovery · no-refactor-because P4.T2 (phase 4)

regen.py was written in its final shape, one private _resolve behind resolve_hunks and classify_conflicts; the only cleanup (a long test line) landed in the same commit

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t3 created=2026-11-24T21:40:00+00:00 phase=4 -->
### no-refactor-p4-t3 · discovery · no-refactor-because P4.T3 (phase 4)

the regen inputs travel as one frozen Regen value through build/_combine/_merged_tree/_keeps_merge_content/_resolve, so no further extraction was owed

<!-- fr:journal kind=review scope=plan id=review-p4 created=2026-11-24T21:44:36+00:00 phase=4 -->
### review-p4 · review · Phase 4 review (generated-file and stamp conflict resolution, git-less mirror run) (phase 4)

Independent reviewer read 1fdc627..HEAD against R8-R14 and decision p4-mirror-export. Ours/theirs
per strategy, the stamp rule, block classification, index-stage checks, the mirror env allowlist,
killpg, the copy-back and the R13 config all check out; no path pushes a bad combination unhanded.
Four in-scope findings (three fixed, one refuted), two out of scope.

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-11-24T21:44:36+00:00 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · Worktree.read/write_resolved translated CRLF to LF, rewriting a hunk-resolved CRLF file whole (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-11-24T21:44:36+00:00 phase=4 state=open review_scope=in -->
### p4-r2 · finding [open] (reviewer: in scope) · An unclosed generated-block open marker let later hunks resolve as ours and hid the file tail from _skeleton (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r3 created=2026-11-24T21:44:36+00:00 phase=4 state=open review_scope=in -->
### p4-r3 · finding [open] (reviewer: in scope) · An OSError from export_tracked/snapshot_export was not caught, so no abort and no clean hand-back (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r4 created=2026-11-24T21:44:36+00:00 phase=4 state=open review_scope=in -->
### p4-r4 · finding [open] (reviewer: in scope) · A mirror's mode-only change is invisible to the stray check and the copy-back (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r5 created=2026-11-24T21:44:36+00:00 phase=4 state=open review_scope=out -->
### p4-r5 · finding [open] (reviewer: out of scope) · The mirror shares the operator's uv cache and python installs, which queued code could poison (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r6 created=2026-11-24T21:44:36+00:00 phase=4 state=open review_scope=out -->
### p4-r6 · finding [open] (reviewer: out of scope) · Mirror timeout is per command, output is uncapped, killpg after reap has a pid-reuse window (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-11-24T21:44:36+00:00 phase=4 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: Worktree.read/write_resolved translated CRLF to LF, rewriting a hunk-resolved CRLF file whole (phase 4)

read and write_resolved use newline=''; test_the_worktree_reads_and_writes_crlf_unchanged and test_a_crlf_file_keeps_its_line_endings_through_a_resolution pin it.

<!-- fr:journal kind=finding scope=plan id=p4-r2-resolved created=2026-11-24T21:44:36+00:00 phase=4 state=fixed resolves=p4-r2 -->
### p4-r2-resolved · finding [fixed] · resolves p4-r2: An unclosed generated-block open marker let later hunks resolve as ours and hid the file tail from _skeleton (phase 4)

_resolve returns None when a block is still open at EOF, and _skeleton compares an unbalanced file whole; two tests pin it.

<!-- fr:journal kind=finding scope=plan id=p4-r3-resolved created=2026-11-24T21:44:36+00:00 phase=4 state=fixed resolves=p4-r3 -->
### p4-r3-resolved · finding [fixed] · resolves p4-r3: An OSError from export_tracked/snapshot_export was not caught, so no abort and no clean hand-back (phase 4)

_regenerate catches (GitError, OSError) around the export, both snapshots, the mirror runs and the copy-back, so an I/O error aborts and hands back as MirrorFailedError.

<!-- fr:journal kind=finding scope=plan id=p4-r4-resolved created=2026-11-24T21:44:36+00:00 phase=4 state=refuted resolves=p4-r4 -->
### p4-r4-resolved · finding [refuted] · resolves p4-r4: A mirror's mode-only change is invisible to the stray check and the copy-back (phase 4)

Git tracks only the executable bit, the five declared mirrors write Markdown and YAML outputs and never chmod, and a mode-only change kept at the old mode loses no generated content: the combination's text is what CI tests and what lands.

<!-- fr:journal kind=finding scope=plan id=p4-r5-resolved created=2026-11-24T21:44:36+00:00 phase=4 state=open resolves=p4-r5 out_of_scope=true -->
### p4-r5-resolved · finding [out-of-scope] · resolves p4-r5: The mirror shares the operator's uv cache and python installs, which queued code could poison (phase 4)

Same trust boundary as p4-s6: entries are approved before the queue runs them, and the spec makes the mirror run defence in depth, not a sandbox; a private cold uv cache per run is a cost trade-off for a later issue.

<!-- fr:journal kind=finding scope=plan id=p4-r6-resolved created=2026-11-24T21:44:36+00:00 phase=4 state=open resolves=p4-r6 out_of_scope=true -->
### p4-r6-resolved · finding [out-of-scope] · resolves p4-r6: Mirror timeout is per command, output is uncapped, killpg after reap has a pid-reuse window (phase 4)

R11 fixes the timeout per command; the pid-reuse window needs the whole group gone and the id recycled between wait and killpg, and output size is bounded by the declared repo scripts.

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-24T21:56:01+00:00 -->
### lens-review-1 · review · Lens review (security, errors, tests, docs-accuracy) of the whole ci-economy diff

Four lens reviewers read the feature diff from merge base ec7d198296a6. Twelve findings in
scope (eleven fixed, one partly refuted and fixed for the case that is real); the out-of-scope
parts are filed at deliver. Fixes: commits 8f6736b1a and 1775a6258.

<!-- fr:journal kind=finding scope=plan id=l-security-r1 created=2026-11-24T21:56:01+00:00 state=open review_scope=in -->
### l-security-r1 · finding [open] (reviewer: in scope) · A mirror could write a path with a .git component that matches a generated glob, and git add --all ran over it

<!-- fr:journal kind=finding scope=plan id=l-security-r2 created=2026-11-24T21:56:01+00:00 state=open review_scope=in -->
### l-security-r2 · finding [open] (reviewer: in scope) · The new lane jobs had no permissions block and kept checkout credentials; GH_TOKEN reached the PR's own ci_lane.py

<!-- fr:journal kind=finding scope=plan id=l-security-r3 created=2026-11-24T21:56:01+00:00 state=open review_scope=in -->
### l-security-r3 · finding [open] (reviewer: in scope) · landed_run trusted the API's head_sha filter without re-checking each run

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-24T21:56:01+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · ci_lane fell back to the full lane silently on gh, git and parse failures

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-24T21:56:01+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · settle reported a stranded cancelled check as still running, naming neither it nor the re-run

<!-- fr:journal kind=finding scope=plan id=l-errors-r3 created=2026-11-24T21:56:01+00:00 state=open review_scope=in -->
### l-errors-r3 · finding [open] (reviewer: in scope) · The ops gate collapsed a cancelled, unreplaced check into pending

<!-- fr:journal kind=finding scope=plan id=l-errors-r4 created=2026-11-24T21:56:01+00:00 state=open review_scope=in -->
### l-errors-r4 · finding [open] (reviewer: in scope) · verify_ci could wait on a gate holding a cancelled and a successful check with nothing running

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-24T21:56:01+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · Workflow if: conditions were pinned by substring, so `<full> || true` passed

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-24T21:56:01+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · verdict was not tested with failed or cancelled shard jobs or scoped-tests

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-24T21:56:01+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · landed_run was not tested against cancelled/skipped conclusions or another sha

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-24T21:56:01+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · Pages said the early conflict probe uses the merge's own rules; it resolves only version and lock files

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-24T21:56:01+00:00 state=open review_scope=in -->
### l-docs-accuracy-r2 · finding [open] (reviewer: in scope) · Two places said mirrors run in the combination's worktree; they run in a git-less copy

<!-- fr:journal kind=finding scope=plan id=l-security-r1-resolved created=2026-11-24T21:56:01+00:00 state=fixed resolves=l-security-r1 -->
### l-security-r1-resolved · finding [fixed] · resolves l-security-r1: A mirror could write a path with a .git component that matches a generated glob, and git add --all ran over it

_regenerate hands back any changed path with a .git or .. component or an absolute path before the glob checks; snapshot_export no longer lets ignore rules hide a .git path. Integration test with and without a .gitignore entry (1775a6258).

<!-- fr:journal kind=finding scope=plan id=l-security-r2-resolved created=2026-11-24T21:56:01+00:00 state=fixed resolves=l-security-r2 -->
### l-security-r2-resolved · finding [fixed] · resolves l-security-r2: The new lane jobs had no permissions block and kept checkout credentials; GH_TOKEN reached the PR's own ci_lane.py

classify, scoped-tests and ci-ok hold read-only permissions and check out with persist-credentials false; GH_TOKEN is set only for a push to main (8f6736b1a, test_the_lane_jobs_keep_no_credential_in_their_checkout). A workflow-level permissions block for the older jobs predates this change and is filed at deliver.

<!-- fr:journal kind=finding scope=plan id=l-security-r3-resolved created=2026-11-24T21:56:01+00:00 state=fixed resolves=l-security-r3 -->
### l-security-r3-resolved · finding [fixed] · resolves l-security-r3: landed_run trusted the API's head_sha filter without re-checking each run

landed_run takes the sha and requires run.head_sha == sha; tested with another sha. Runs come from this repo's own actions/runs endpoint, so head_repository adds nothing.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-24T21:56:01+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: ci_lane fell back to the full lane silently on gh, git and parse failures

Every fallback prints `ci_lane: <cause>; taking the full lane` to stderr; a landed miss names the sha. Tests read stderr for the gh and git cases.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-24T21:56:01+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: settle reported a stranded cancelled check as still running, naming neither it nor the re-run

settle has a (ci, cancelled) hint naming the cancelled checks and the re-run; verdict stays pending (1775a6258).

<!-- fr:journal kind=finding scope=plan id=l-errors-r3-resolved created=2026-11-24T21:56:01+00:00 state=fixed resolves=l-errors-r3 -->
### l-errors-r3-resolved · finding [fixed] · resolves l-errors-r3: The ops gate collapsed a cancelled, unreplaced check into pending

_checks_green raises 'checks were cancelled with no newer run: <names>; re-run the workflow' when every waiting check is cancelled (1775a6258).

<!-- fr:journal kind=finding scope=plan id=l-errors-r4-resolved created=2026-11-24T21:56:01+00:00 state=fixed resolves=l-errors-r4 -->
### l-errors-r4-resolved · finding [fixed] · resolves l-errors-r4: verify_ci could wait on a gate holding a cancelled and a successful check with nothing running

The real client already keeps the latest check per (workflow, name), so the duplicate shape is refuted for that path; the real case, one gate name across two workflows, now uses _unreplaced and a gate with an unreplaced cancelled check is stranded and refused once nothing runs (1775a6258).

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-24T21:56:01+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: Workflow if: conditions were pinned by substring, so `<full> || true` passed

Shard and other jobs' if: are asserted equal to the whole expression (8f6736b1a).

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-24T21:56:01+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: verdict was not tested with failed or cancelled shard jobs or scoped-tests

Shard jobs are tested skipped, failure and cancelled in the full lane, and scoped-tests skipped, failure and cancelled in the light lane.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-24T21:56:01+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: landed_run was not tested against cancelled/skipped conclusions or another sha

cancelled, skipped, neutral and timed_out conclusions and a different head_sha are near-miss cases of test_no_other_run_is_trusted.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-24T21:56:01+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: Pages said the early conflict probe uses the merge's own rules; it resolves only version and lock files

fr-wave-driver.md and the fr-triage skill (mirrors synced) now say the probe uses only the version and lock file rules and a stamp or generated conflict still counts there. Teaching the probe the new rules is filed at deliver.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-24T21:56:01+00:00 state=fixed resolves=l-docs-accuracy-r2 -->
### l-docs-accuracy-r2-resolved · finding [fixed] · resolves l-docs-accuracy-r2: Two places said mirrors run in the combination's worktree; they run in a git-less copy

.fr/triage.yaml and the skill say the mirrors run on a copy of the combination's tracked files with no git directory.

<!-- fr:journal kind=finding scope=plan id=l-out-workflow-permissions created=2026-11-24T21:58:17+00:00 state=open review_scope=out -->
### l-out-workflow-permissions · finding [open] (reviewer: out of scope) · ci.yml has no workflow-level permissions block; the older jobs run with the repo's default token

Raised under the security lens (l-security-r2). This change gave its own lane jobs read-only tokens and credential-free checkouts; the older jobs predate it.
