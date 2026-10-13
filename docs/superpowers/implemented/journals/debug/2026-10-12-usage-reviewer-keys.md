# Journal: 2026-10-12-usage-reviewer-keys

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-12T00:01:57+00:00 -->
### repro · repro · Reviewer brief re-keying (gh#1060) does not reproduce on main

A record with briefs={'rv1': 100} and a cursor unit phase/1/review-phase carrying evidence.reviewer=rv1 (and no attempt agent rv1): session_entry re-keys it to phase/1/review-phase on BOTH paths, rekey=units_by_agent(cursor) (backfill/refreshed_file) and index=unit_index(cursor) (capture/recompute).

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-10-12T00:02:00+00:00 -->
### root-cause · root-cause · Already fixed by #1041; only the brief path lacks a pin

Before #1041 (91742128~1, usage/file.py:230) units_by_agent read attempt agents only. #1041 made it a view of unit_index, which also maps evidence.reviewer (file.py:302-305). #1060 was filed from spec-review finding sr-r1-12 (written against the pre-#1041 code) at close-out without re-checking. test_usage_split pins units_by_agent including rv1, but no test pins that a reviewer's BRIEF lands on its unit, so the fix could regress silently.

<!-- fr:journal kind=finding scope=debug id=pin created=2026-10-12T00:04:51+00:00 state=fixed -->
### pin · finding [fixed] · Reviewer brief re-keying pinned on both session_entry paths

tests/unit/test_usage_split.py::test_a_reviewer_brief_is_keyed_by_its_unit_not_the_agent_id[index|rekey]. Mutation check: replacing agents.setdefault(reviewer, unit_key) in unit_index with a no-op turns both red with briefs {'rv1': 100} (the gh#1060 symptom); restored, green. No source change: the behaviour shipped in #1041 (91742128). Usage + run-cost tests: 220 passed, 10 skipped.

<!-- fr:journal kind=review scope=debug id=review created=2026-10-12T00:05:20+00:00 -->
### review · review · Review of PR #1150: no findings

Self-review of a one-test, no-source diff: the fixture's rv1 is reachable only via evidence.reviewer (the review attempt has no agent), both session_entry paths are covered, and the mutation check proves the test bites. CI runs the full suite. No findings raised.
