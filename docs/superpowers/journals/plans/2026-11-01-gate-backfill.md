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

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-01T18:49:30+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · archived plans: by_commit pooled live+archived first-adds, so the archive git-mv read as an add and every archived plan came out ambiguous (phase 1)

Raised by the dispatched phase-1 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-01T18:49:30+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · printed `fr closeout outcome … --na` for a spec: step lacked --supersede, so it was always refused (step already recorded owed) (phase 1)

Raised by the dispatched phase-1 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-01T18:49:30+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · an unconfirmed manifest pr: override fell through to run/commit/issue and its rejection was lost (phase 1)

Raised by the dispatched phase-1 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-01T18:49:30+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · merge_plan kept an earlier default `owed` (and a computed gate) over newly computed review defaults (phase 1)

Raised by the dispatched phase-1 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-01T18:49:30+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · open_issues was capped at 500 silently (phase 1)

Raised by the dispatched phase-1 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-01T18:49:30+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · by_run re-parsed every cursor per candidate, 2–3 pr_view per PR, rev-list per path (phase 1)

Raised by the dispatched phase-1 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-11-01T18:49:30+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · the run step matched the emitted spec by exact path, so archived specs never matched (phase 1)

Raised by the dispatched phase-1 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-11-01T18:49:30+00:00 phase=1 state=open review_scope=in -->
### p1-r8 · finding [open] (reviewer: in scope) · write_plan sat outside the try: an unwritable --plan path gave a traceback (phase 1)

Raised by the dispatched phase-1 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r9 created=2026-11-01T18:49:30+00:00 phase=1 state=open review_scope=in -->
### p1-r9 · finding [open] (reviewer: in scope) · the no-forge-write test used a denylist that missed pr_ready/delete_branch (phase 1)

Raised by the dispatched phase-1 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r10 created=2026-11-01T18:49:30+00:00 phase=1 state=open review_scope=in -->
### p1-r10 · finding [open] (reviewer: in scope) · dead _KEY regex; is_ours duplicated owned_owed_key's author/label logic (phase 1)

Raised by the dispatched phase-1 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r11 created=2026-11-01T18:49:30+00:00 phase=1 state=open review_scope=in -->
### p1-r11 · finding [open] (reviewer: in scope) · _lookalikes did not exclude fr-owned trackers of other keys (phase 1)

Raised by the dispatched phase-1 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r12 created=2026-11-01T18:49:30+00:00 phase=1 state=open review_scope=in -->
### p1-r12 · finding [open] (reviewer: in scope) · the spec:+tick refusal omitted the 'record it ran' hint (phase 1)

Raised by the dispatched phase-1 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r13 created=2026-11-01T18:49:30+00:00 phase=1 state=open review_scope=out -->
### p1-r13 · finding [open] (reviewer: out of scope) · owed keys from issue markers reached filesystem paths unvalidated (path traversal) (phase 1)

Raised by the dispatched phase-1 code reviewer.

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-11-01T18:49:30+00:00 phase=1 -->
### p1-review · review · phase 1 code review (phase 1)

13 findings raised (p1-r1..p1-r13), p1-r1..p1-r12 fixed; p1-r13 (out) resolved out-of-scope, hardened here anyway; 115 targeted tests pass after the fixes.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-01T18:49:30+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: archived plans: by_commit pooled live+archived first-adds, so the archive git-mv read as an add and every archived plan came out ambiguous (phase 1)

Fixed in 06445c9a8: one plan's (or spec's) live and archived paths are grouped and the oldest add wins; fixture tests for an archived plan and spec.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-01T18:49:30+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: printed `fr closeout outcome … --na` for a spec: step lacked --supersede, so it was always refused (step already recorded owed) (phase 1)

Fixed in 14cf38207: --supersede added to both closeout commands; spec §E/§H updated to match.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-01T18:49:30+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: an unconfirmed manifest pr: override fell through to run/commit/issue and its rejection was lost (phase 1)

Fixed in 06445c9a8: a manifest pr is returned alone; unconfirmed → unresolved with 'manifest pr #N: <reason>'.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-01T18:49:30+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: merge_plan kept an earlier default `owed` (and a computed gate) over newly computed review defaults (phase 1)

Fixed in df3b7fcb1: entries record default_decision and computed_gate; only values differing from them carry over.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-01T18:49:30+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: open_issues was capped at 500 silently (phase 1)

Fixed in fb920ea84: a cap hit adds a note to the summary.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-01T18:49:30+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: by_run re-parsed every cursor per candidate, 2–3 pr_view per PR, rev-list per path (phase 1)

Fixed in 06445c9a8: DeliveryCache indexes cursors once and memoizes pr_view; Git caches the first-parent line; a test counts one pr_view per PR.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-11-01T18:49:30+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: the run step matched the emitted spec by exact path, so archived specs never matched (phase 1)

Fixed in 06445c9a8: basenames compared, as for plans.

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-11-01T18:49:30+00:00 phase=1 state=fixed resolves=p1-r8 -->
### p1-r8-resolved · finding [fixed] · resolves p1-r8: write_plan sat outside the try: an unwritable --plan path gave a traceback (phase 1)

Fixed in f96a981be: exit-2 refusal, tested.

<!-- fr:journal kind=finding scope=plan id=p1-r9-resolved created=2026-11-01T18:49:30+00:00 phase=1 state=fixed resolves=p1-r9 -->
### p1-r9-resolved · finding [fixed] · resolves p1-r9: the no-forge-write test used a denylist that missed pr_ready/delete_branch (phase 1)

Fixed in f96a981be: a read allowlist is asserted instead.

<!-- fr:journal kind=finding scope=plan id=p1-r10-resolved created=2026-11-01T18:49:30+00:00 phase=1 state=fixed resolves=p1-r10 -->
### p1-r10-resolved · finding [fixed] · resolves p1-r10: dead _KEY regex; is_ours duplicated owned_owed_key's author/label logic (phase 1)

Fixed in 46909de7a: _KEY removed; archive_followups.is_owned_issue extracted and shared, owned_owed_key unchanged (its tests green).

<!-- fr:journal kind=finding scope=plan id=p1-r11-resolved created=2026-11-01T18:49:30+00:00 phase=1 state=fixed resolves=p1-r11 -->
### p1-r11-resolved · finding [fixed] · resolves p1-r11: _lookalikes did not exclude fr-owned trackers of other keys (phase 1)

Fixed in 46909de7a: every fr-owned tracker is excluded.

<!-- fr:journal kind=finding scope=plan id=p1-r12-resolved created=2026-11-01T18:49:30+00:00 phase=1 state=fixed resolves=p1-r12 -->
### p1-r12-resolved · finding [fixed] · resolves p1-r12: the spec:+tick refusal omitted the 'record it ran' hint (phase 1)

Fixed in 14cf38207: hint names the exact --ran … --supersede command.

<!-- fr:journal kind=finding scope=plan id=p1-r13-resolved created=2026-11-01T18:49:30+00:00 phase=1 state=open resolves=p1-r13 out_of_scope=true -->
### p1-r13-resolved · finding [out-of-scope] · resolves p1-r13: owed keys from issue markers reached filesystem paths unvalidated (path traversal) (phase 1)

The key source is the pre-existing debt fold, as the reviewer says; this change hardened its own use of it anyway in 46909de7a (keys filtered through OWED_KEY_RE, traversal test). Whether the debt engine itself should filter is the debt fold's concern.

<!-- fr:journal kind=finding scope=plan id=p1-load-flakes-resolved created=2026-11-01T18:49:30+00:00 phase=1 state=open resolves=p1-load-flakes out_of_scope=true -->
### p1-load-flakes-resolved · finding [out-of-scope] · resolves p1-load-flakes: Six wall-clock-sensitive tests failed in a 2h loaded full-suite run, pass alone (phase 1)

Six timing-bound tests (idle guard, records commit, visual evidence) failed only in a 2-hour run on an oversubscribed host; the same 133 tests pass alone (re-run by the orchestrator). No file of this change is involved.
