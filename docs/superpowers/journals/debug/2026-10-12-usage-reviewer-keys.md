# Journal: 2026-10-12-usage-reviewer-keys

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-12T00:01:57+00:00 -->
### repro · repro · Reviewer brief re-keying (gh#1060) does not reproduce on main

A record with briefs={'rv1': 100} and a cursor unit phase/1/review-phase carrying evidence.reviewer=rv1 (and no attempt agent rv1): session_entry re-keys it to phase/1/review-phase on BOTH paths, rekey=units_by_agent(cursor) (backfill/refreshed_file) and index=unit_index(cursor) (capture/recompute).
