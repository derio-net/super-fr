<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-plan-ops-split

<!-- fr:journal kind=discovery scope=plan id=plan-ops-split-review-modules created=2026-11-27T11:18:22+00:00 phase=1 -->
### plan-ops-split-review-modules · discovery · fr.plan_review is five modules: vocabulary, journal, checks, sizing and __init__ (phase 1)

checks.py would have held about 1,000 lines, past the spec's ~800-line
trigger, so the phase-sizing, tier and scope-field sub-checks
(`_split_record_hint`, `_phase_sizing_issues`, `_tier_issues`,
`_scope_field_issues`) moved to `fr/plan_review/sizing.py`. sizing imports
checks, journal and vocabulary; checks imports journal and vocabulary; no
module of the package imports `fr.plan_ops`. `_spec_journal_entries` lives in
journal.py beside `journal_entries`, as a three-line call to it. plan_ops.py
is 641 lines (budget 700, from 2,600).

<!-- fr:journal kind=discovery scope=plan id=plan-ops-split-reviewed-note created=2026-11-27T11:18:22+00:00 phase=1 -->
### plan-ops-split-reviewed-note · discovery · The reviewed note reads `still true, import-only change`, not `still true: ...` (phase 1)

A `reviewed:` stamp is a plain YAML scalar in the page front matter, and the
spec's literal note `still true: import-only change` holds `: `, which makes
the front matter unreadable (fr docs check reported bad-page on all six). The
six stamped pages (fr-brainstorming-and-plan, fr-dispatch, cli,
dispatch-lifecycle, plan-model, workflow-shapes) carry
`2026-11-27 still true, import-only change (plan_ops split)`. fr docs check
is clean.

<!-- fr:journal kind=discovery scope=plan id=plan-ops-split-test-edits created=2026-11-27T11:18:22+00:00 phase=1 -->
### plan-ops-split-test-edits · discovery · Test edits beyond import lines: module-qualified calls renamed to the new home (phase 1)

No assertion's expected value changed. Three tests spelled a moved name through
the module rather than an import, so the module name changed on those lines:
test_plan_ops_feature_root.py (`plan_ops.` -> `plan_rework.` in the patch and
the four asserts), test_policy_off_acceptance.py (`plan_ops._acceptance_link_issues(plan)`
-> `_acceptance_link_issues(plan)`, imported from fr.plan_review.checks) and
test_v2_apply.py (`raise plan_ops.PlanEditError` -> `raise PlanEditError`,
imported from fr.plan_errors). Two docstrings in test_dispatch_lint_corpus.py
and one in fr/refs.py now name the new homes.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-27T11:18:22+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a single RED step: the new test file is the whole task, there is no production code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-27T11:18:22+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

a verbatim move of four functions and one class; the bodies may not change (R12), so the cleanup is the move itself

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-27T11:18:22+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

a verbatim move of the table section; bodies frozen by the spec's cut-and-paste rule

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-27T11:18:22+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the moves are verbatim and the one permitted body change (the merged journal read, R3) is the refactor; checks.py was split into checks.py and sizing.py to stay under ~800 lines

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-27T11:18:22+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

a verbatim move of the rework section; bodies frozen by the spec's cut-and-paste rule

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-27T11:28:40+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Docstrings still name fr.plan_ops for the moved sizing reader and rework writer (phase 1)

requirements.py:15 listed fr.plan_ops as a phase-sizing reader; plan_ops.py:1-14 said rework writes happen there; _yaml.py:29 named plan_ops as the router.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-27T11:28:40+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Reviewed-stamp note differs from R14's literal wording (phase 1)

Pages carry "still true, import-only change (plan_ops split)"; R14 said "still true: import-only change".

<!-- fr:journal kind=review scope=plan id=p1-review-r1 created=2026-11-27T11:28:40+00:00 phase=1 -->
### p1-review-r1 · review · Phase 1 code review — verbatim moves, no cycle, two wording findings (phase 1)

Independent reviewer compared every moved top-level body by ast against origin/main (byte-identical except the merged journal read), checked journal_entries against both old readers, import direction (fresh-interpreter sys.modules check), every monkeypatch target, R9 re-export identity, R10 callers, R11 test diffs, budget, docs check and fragment; ran 517 targeted tests green. Findings: p1-r1, p1-r2.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-27T11:28:40+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Docstrings still name fr.plan_ops for the moved sizing reader and rework writer (phase 1)

requirements.py, plan_ops.py and _yaml.py docstrings now name fr.plan_review, fr.plan_rework and fr._plan_io (3d771d421).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-27T11:28:40+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Reviewed-stamp note differs from R14's literal wording (phase 1)

The colon form breaks the page's YAML front matter (discovery logged by the executor), so the spec's R14 now states the comma form the pages carry (3d771d421).
