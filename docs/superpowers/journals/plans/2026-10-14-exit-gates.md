<!-- fr:journal-schema=2 -->
# Journal: 2026-10-14-exit-gates

<!-- fr:journal kind=decision scope=plan id=plan-shape created=2026-10-13T23:06:47+00:00 -->
### plan-shape · decision · Eight agentic phases, one per ask, serial; no [manual] phase

The live verification (labels, routing, collected close-out, release) is post-merge Test Plan rows, not a phase. Skill and doc prose rides the phase that changes the behaviour it describes.

<!-- fr:journal kind=discovery scope=plan id=p1-r24-changes-existing-test created=2026-10-13T23:42:28+00:00 phase=1 -->
### p1-r24-changes-existing-test · discovery · R24 makes a section-less spec with a row verify live and no reason an error (phase 1)

test_plan_self_review_verification::test_a_spec_with_no_section_passes_unchanged asserted the opposite on a row with verify: live; it now uses a row with no verify: (the still-unchanged case). The brainstorm warning passes shape_default None, so it checks explicit strategies only, as before.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-10-13T23:42:28+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

Task 1 only adds a constants module and a fragment; there was nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-13T23:42:28+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

The spec_section and ExitBlock additions are each one new branch/field beside the existing ones; nothing duplicated to merge.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-10-13T23:42:28+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

Task 6 adds scenario scripts, their wiring, one prose sentence and matrix moves; nothing to clean.
