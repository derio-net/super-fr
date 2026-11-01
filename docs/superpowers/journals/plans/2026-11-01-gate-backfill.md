<!-- fr:journal-schema=3 -->
# Journal: 2026-11-01-gate-backfill

<!-- fr:journal kind=decision scope=plan id=p1-trust-boundary created=2026-11-01T18:22:52+00:00 phase=1 -->
### p1-trust-boundary · decision · Only this account's fr:owed-labelled issues are trackers (phase 1)

Per a security review (R8), trackers are picked only through archive_followups.owned_owed_key(issue, viewer_login()); the gate-marker drop of an issue: candidate additionally needs the issue to be ours (author + fr:owed label, via trackers.is_ours) but not the owed-marker-on-last-line rule, because such an issue's key comes from its marker and would never be an issue: candidate. A foreign marker is only text, at most a look-alike suggestion.

<!-- fr:journal kind=discovery scope=plan id=p1-agentic-open-phase-source created=2026-11-01T18:22:52+00:00 phase=1 -->
### p1-agentic-open-phase-source · discovery · An open agentic phase of a merged plan cannot come from the plan sweep (phase 1)

closeout._plan_merged requires every agentic phase landed, so plan_sweep never lists an open agentic phase as owed; such a plan:...#pN key arrives only from a journal owed entry or an owed-marker issue. gate_for still returns None for it (review).

<!-- fr:journal kind=discovery scope=plan id=p1-spec-slug-includes-date created=2026-11-01T18:22:52+00:00 phase=1 -->
### p1-spec-slug-includes-date · discovery · spec:<slug> keys carry the dated slug (phase 1)

spec_slug_of drops only a trailing -design, so the key is spec:2026-05-01-thing#step1; find_spec matches by that slug over live and implemented specs.

<!-- fr:journal kind=finding scope=plan id=p1-load-flakes created=2026-11-01T18:22:52+00:00 phase=1 state=open review_scope=out -->
### p1-load-flakes · finding [open] (reviewer: out of scope) · Six wall-clock-sensitive tests failed in a 2h loaded full-suite run, pass alone (phase 1)

tests/integration/test_run_idle_guard.py::test_it_acts_again_once_the_cursor_has_moved, tests/unit/test_records_commit.py::test_a_record_commit_gives_up_on_a_stuck_index_lock_quickly (7.15s vs a 5s bound) and four tests in tests/unit/test_run_evidence_visual.py (file mtime vs the unit's open time, seconds apart) failed under the shared slot's load. Re-run alone: 62 passed. No file this phase touches is involved.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-01T18:22:52+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a one-command skeleton, nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-01T18:22:52+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

new pure model module, no duplicated helper

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-01T18:22:52+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

new module; the only shared helper (split_key) is already single-sourced

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-01T18:22:52+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

new module; the PR-subject regex lives once in delivery.py and the cursor listing moved to fr.run.cursors in this task
