# Journal: 2026-10-12-usage-reviewer-keys

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-12T00:01:57+00:00 -->
### repro · repro · Reviewer brief re-keying (gh#1060) does not reproduce on main

A record with briefs={'rv1': 100} and a cursor unit phase/1/review-phase carrying evidence.reviewer=rv1 (and no attempt agent rv1): session_entry re-keys it to phase/1/review-phase on BOTH paths, rekey=units_by_agent(cursor) (backfill/refreshed_file) and index=unit_index(cursor) (capture/recompute).

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-10-12T00:02:00+00:00 -->
### root-cause · root-cause · Already fixed by #1041; only the brief path lacks a pin

Before #1041 (91742128~1, usage/file.py:230) units_by_agent read attempt agents only. #1041 made it a view of unit_index, which also maps evidence.reviewer (file.py:302-305). #1060 was filed from spec-review finding sr-r1-12 (written against the pre-#1041 code) at close-out without re-checking. test_usage_split pins units_by_agent including rv1, but no test pins that a reviewer's BRIEF lands on its unit, so the fix could regress silently.
