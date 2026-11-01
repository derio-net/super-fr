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

<!-- fr:journal kind=decision scope=plan id=p2-manifest-key-held-by-own-tracker created=2026-11-01T19:11:33+00:00 phase=2 -->
### p2-manifest-key-held-by-own-tracker · decision · a manifest key held only by fr's own tracker is the manifest's again (phase 2)

After a first `--yes`, the tracker fr filed makes `fr debt` hold the manifest entry's key,
and `collect_candidates` refused the manifest ("fr debt already holds this key"), so a
second `--yes --from` exited 2 instead of being a no-op (R7). A key in the fold only
because of an `owned_trackers` issue now yields to the manifest entry (candidates.py).

<!-- fr:journal kind=decision scope=plan id=p2-plan-entry-issue created=2026-11-01T19:11:33+00:00 phase=2 -->
### p2-plan-entry-issue · decision · PlanEntry gained an optional `issue` (the closed issue whose ask this is) (phase 2)

Apply needs the closed issue to link, and a manifest `closed-issue` item names it under a
non-`issue:` key, so `to_entry` now records `Candidate.issue_number`. Optional and
defaulted; the plan file lives outside the repo and is not a registered artifact kind.

<!-- fr:journal kind=decision scope=plan id=p2-open-issue-key-is-its-own-tracker created=2026-11-01T19:11:33+00:00 phase=2 -->
### p2-open-issue-key-is-its-own-tracker · decision · an open `issue:` entry gets its PR label but no tracker (phase 2)

An `issue:` candidate whose issue is still open is its own tracker; filing a second one
would duplicate it. `--yes` labels the PR and reports "adopt it to label it". The spec
is silent; this is the conservative reading of R8.

<!-- fr:journal kind=discovery scope=plan id=p2-apply-signature created=2026-11-01T19:11:33+00:00 phase=2 -->
### p2-apply-signature · discovery · apply_plan takes the re-resolved plan entries as `candidates`, plus repo= and tracking= (phase 2)

The command re-resolves each candidate's delivering PR (delivery.py) into PlanEntry
objects exactly as the dry run does and passes those, so R15's comparison is entry to
entry; `repo=` carries `owed_identity` for the plan-repo refusal.

<!-- fr:journal kind=discovery scope=plan id=p2-fake-pr-view-labels created=2026-11-01T19:11:33+00:00 phase=2 -->
### p2-fake-pr-view-labels · discovery · FakeGhClient.pr_view now reports labels written by edit_pr_labels (phase 2)

It returned only the record's labels, so the fake could not show a second apply that
reads the PR's labels; it now unions `pr_labels`. Existing tests unaffected.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-01T19:11:33+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

new helpers appended to the phase-1 trackers.py; nothing duplicated, no existing code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-01T19:11:33+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

apply.py is a new module built on _Writer (one write path per verb) from the start; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-11-01T19:11:33+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

a scenario, a stub and docs only; no production code touched

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-01T19:51:53+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · already-passed PR printed `fr gate pass` as its discharge instead of the key's §H discharge command (phase 2)

Raised by the dispatched phase-2 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-01T19:51:53+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · open issue: path counted its note as a write, was untested, and left no marker for §H (phase 2)

Raised by the dispatched phase-2 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-01T19:51:53+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · manifest takeover overrode row/plan/journal keys that also had a tracker (phase 2)

Raised by the dispatched phase-2 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-01T19:51:53+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · _target reported any read failure as 'does not exist' and skipped (phase 2)

Raised by the dispatched phase-2 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-01T19:51:53+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · R9 closed only the lowest-numbered fr-owned duplicate per run (phase 2)

Raised by the dispatched phase-2 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-11-01T19:51:53+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · tracker gate-marker mismatch skipped with no stated remedy (phase 2)

Raised by the dispatched phase-2 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-11-01T19:51:53+00:00 phase=2 state=open review_scope=in -->
### p2-r7 · finding [open] (reviewer: in scope) · no test for a foreign adopt-marker comment, nor for the open-issue path (phase 2)

Raised by the dispatched phase-2 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r8 created=2026-11-01T19:51:53+00:00 phase=2 state=open review_scope=in -->
### p2-r8 · finding [open] (reviewer: in scope) · run_for_head re-parsed every cursor per entry (phase 2)

Raised by the dispatched phase-2 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r9 created=2026-11-01T19:51:53+00:00 phase=2 state=open review_scope=out -->
### p2-r9 · finding [open] (reviewer: out of scope) · 02.yaml's `-k gate-backfill` selects no test; the ids are test_gate_backfill_* (phase 2)

Raised by the dispatched phase-2 code reviewer.

<!-- fr:journal kind=review scope=plan id=p2-review created=2026-11-01T19:51:53+00:00 phase=2 -->
### p2-review · review · phase 2 code review (phase 2)

9 findings raised (p2-r1..p2-r9): p2-r1..p2-r8 fixed; p2-r9 (out, plan text) resolved out-of-scope. 141 targeted tests and the 1178 FakeGhClient-using tests pass after the fixes.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-01T19:51:53+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: already-passed PR printed `fr gate pass` as its discharge instead of the key's §H discharge command (phase 2)

Fixed in 00822b176: one pure trackers.discharge_command(key, repo_root=) per key kind, used by apply; test and docs corrected. Phase 3 reuses it.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-01T19:51:53+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: open issue: path counted its note as a write, was untested, and left no marker for §H (phase 2)

Fixed in 564500cfa: a bare owed on an open issue: key is refused at the dry run (adopt it, or give the manifest an issue:) and skipped at apply; notes are no longer counted as writes; tests.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-01T19:51:53+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: manifest takeover overrode row/plan/journal keys that also had a tracker (phase 2)

Fixed in 564500cfa: a manifest takes a key back only when the fold's source for it is issue; refusal test for a row key with a tracker.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-01T19:51:53+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: _target reported any read failure as 'does not exist' and skipped (phase 2)

Fixed in 564500cfa: only a forge not-found reads as missing; other errors are recorded (exit 1); FakeGhClient.view_issue now raises a 404 like the real client (1178 FakeGhClient-using tests green).

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-01T19:51:53+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: R9 closed only the lowest-numbered fr-owned duplicate per run (phase 2)

Fixed in 564500cfa: every fr-owned duplicate for the key is closed; two-duplicate test.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-11-01T19:51:53+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: tracker gate-marker mismatch skipped with no stated remedy (phase 2)

Fixed in 564500cfa: the skip line names the remedy; documented in docs/gate-backfill.md.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-11-01T19:51:53+00:00 phase=2 state=fixed resolves=p2-r7 -->
### p2-r7-resolved · finding [fixed] · resolves p2-r7: no test for a foreign adopt-marker comment, nor for the open-issue path (phase 2)

Fixed in 564500cfa: tests added (the code already ignored foreign comments).

<!-- fr:journal kind=finding scope=plan id=p2-r8-resolved created=2026-11-01T19:51:53+00:00 phase=2 state=fixed resolves=p2-r8 -->
### p2-r8-resolved · finding [fixed] · resolves p2-r8: run_for_head re-parsed every cursor per entry (phase 2)

Fixed in 564500cfa: trackers.runs_by_head indexes cursors once per apply.

<!-- fr:journal kind=finding scope=plan id=p2-r9-resolved created=2026-11-01T19:51:53+00:00 phase=2 state=open resolves=p2-r9 out_of_scope=true -->
### p2-r9-resolved · finding [out-of-scope] · resolves p2-r9: 02.yaml's `-k gate-backfill` selects no test; the ids are test_gate_backfill_* (phase 2)

Plan step text, not code: the scenarios run and pass with -k gate_backfill (orchestrator and executors used that); the plan's literal command is cosmetic and the plan is not behaviour this change ships.

<!-- fr:journal kind=decision scope=plan id=p3-close-lives-in-gatebackfill created=2026-11-01T20:07:00+00:00 phase=3 -->
### p3-close-lives-in-gatebackfill · decision · close_gate_trackers lives in fr/gatebackfill/close.py and fr.verification.labels re-exports it (phase 3)

Keeps the fr.gatebackfill -> fr.verification direction free of a cycle (close.py imports
only ghclient/labels/archive_followups; trackers are imported lazily). Both routes import
it via fr.verification.labels. It returns a CloseReport (closed, adopt commands,
discharge commands, errors) and takes optional root (discharge commands) and dry_run.

<!-- fr:journal kind=decision scope=plan id=p3-driver-prints-no-discharge created=2026-11-01T20:07:00+00:00 phase=3 -->
### p3-driver-prints-no-discharge · decision · the driver route passes no repo root, so it prints no discharge commands (phase 3)

The driver has no checkout of the repo the PR is in at that point; its one-line output
names the closed trackers and any error. The discharge commands print from `fr gate pass`.

<!-- fr:journal kind=decision scope=plan id=p3-retry-exit-code created=2026-11-01T20:07:00+00:00 phase=3 -->
### p3-retry-exit-code · decision · the retry path exits 1 when the close failed; the normal path exits 0 (phase 3)

After a normal pass the pass itself succeeded, so a tracker failure is reported and the
retry command printed with exit 0; on the retry path the close is the whole job, so a
failure exits 1. The old test that a gate:<g>-passed PR refuses was dropped: it is now the
retry (a PR with neither label still refuses, tested).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-11-01T20:07:00+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

one new helper module; both routes call it, nothing duplicated or existing to clean

<!-- fr:journal kind=decision scope=plan id=p3-driver-prints-discharge created=2026-11-01T20:25:34+00:00 phase=3 -->
### p3-driver-prints-discharge · decision · the driver route prints the adopt close and discharge lines (supersedes p3-driver-prints-no-discharge) (phase 3)

The earlier rationale was wrong: the driver does know the repo's checkout (_Driver.path_of). _pass_gate now passes root=path_of(repo) and emits the adopt gh issue close lines and the discharge lines after the gate-pass line, as R12 requires on both routes. With no checkout path the discharge lines are omitted.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-01T20:50:31+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · retry hint omitted the required --notes (and --repo/--host), so the printed command failed (phase 3)

Raised by the dispatched phase-3 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-01T20:50:31+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · driver route passed no root and printed no adopt/discharge commands (R12) (phase 3)

Raised by the dispatched phase-3 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-01T20:50:31+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · retry trusted a hand-applied gate:<g>-passed label (phase 3)

Raised by the dispatched phase-3 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-11-01T20:50:31+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · an empty viewer_login let author-less (ghost) comments match (phase 3)

Raised by the dispatched phase-3 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-11-01T20:50:31+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · no test asserted the fr:owed label bound on list_issues (phase 3)

Raised by the dispatched phase-3 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-11-01T20:50:31+00:00 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · driver close failure path untested (phase 3)

Raised by the dispatched phase-3 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-11-01T20:50:31+00:00 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · GatedWorld.trackers was a shared mutable class attribute (phase 3)

Raised by the dispatched phase-3 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r8 created=2026-11-01T20:50:31+00:00 phase=3 state=open review_scope=out -->
### p3-r8 · finding [open] (reviewer: out of scope) · non-forge exceptions escape close_gate_trackers and could crash the driver after the pass (phase 3)

Raised by the dispatched phase-3 code reviewer.

<!-- fr:journal kind=review scope=plan id=p3-review created=2026-11-01T20:50:31+00:00 phase=3 -->
### p3-review · review · phase 3 code review (phase 3)

8 findings raised (p3-r1..p3-r8): p3-r1..p3-r7 fixed; p3-r8 (out, pre-existing driver exception boundary) resolved out-of-scope. 126 targeted and 1230 FakeGhClient-using tests pass after the fixes.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-01T20:50:31+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: retry hint omitted the required --notes (and --repo/--host), so the printed command failed (phase 3)

Fixed in 357ba3f6c: the hint carries --notes (quoted), --repo and a non-default --host; the test re-invokes the printed line.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-01T20:50:31+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: driver route passed no root and printed no adopt/discharge commands (R12) (phase 3)

Fixed in 89daa45fa: _pass_gate passes root=self.path_of(repo) and emits adopt close lines and discharge lines after the pass line; tested via _drive --once --yes; journal p3-driver-prints-discharge supersedes p3-driver-prints-no-discharge.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-01T20:50:31+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: retry trusted a hand-applied gate:<g>-passed label (phase 3)

Fixed in 625712643: the retry requires this account's fr:gate-pass <g> comment on the PR, else exit 2; tests for hand-labelled and fr-passed PRs.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-11-01T20:50:31+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: an empty viewer_login let author-less (ghost) comments match (phase 3)

Fixed in 625712643: empty login records an error and closes/adopts nothing.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-11-01T20:50:31+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: no test asserted the fr:owed label bound on list_issues (phase 3)

Fixed in 89daa45fa: fakes record labels; test asserts ["fr:owed"].

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-11-01T20:50:31+00:00 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: driver close failure path untested (phase 3)

Fixed in 89daa45fa: test pins the pass reported as success, failed_write false, exit 0 on a close failure.

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-11-01T20:50:31+00:00 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: GatedWorld.trackers was a shared mutable class attribute (phase 3)

Fixed in 89daa45fa: moved into __init__.

<!-- fr:journal kind=finding scope=plan id=p3-r8-resolved created=2026-11-01T20:50:31+00:00 phase=3 state=open resolves=p3-r8 out_of_scope=true -->
### p3-r8-resolved · finding [out-of-scope] · resolves p3-r8: non-forge exceptions escape close_gate_trackers and could crash the driver after the pass (phase 3)

The same exposure already exists for the driver's pass_gate call (non-forge exceptions are not caught there either); this change adds no new exception class to that path. Hardening the driver's exception boundary is the driver's concern.

<!-- fr:journal kind=decision scope=plan id=p4-devops-no-run-evidence created=2026-11-01T21:22:25+00:00 phase=4 -->
### p4-devops-no-run-evidence · decision · the board's gate-labelled PR reason uses --no-run-evidence for devops (phase 4)

The board reads no repo checkout, so it cannot resolve the run whose cursor names the PR's head; gated_pr_lane calls trackers.pass_command(gate, pr) with no run id, which prints --no-run-evidence for devops. The operator swaps in --run when a run exists.

<!-- fr:journal kind=decision scope=plan id=p4-gated-card-not-batch-card created=2026-11-01T21:22:25+00:00 phase=4 -->
### p4-gated-card-not-batch-card · decision · a gate-labelled PR outside a lane is a GatedCard in its column, not a Card (phase 4)

Card is built around a Batch (events, members, session status), which a bare PR has none of, so kanban.ColumnView gains `gated` (GatedCard repo/number/title/url/reason) beside `cards`, counted in the column header, and Board.gated_count keeps the page from reading "No batches" when only gated PRs exist. lanes.unlisted_gated_prs is the one filter (batch PR in a lane, or ledger unread) that needs_you and build_board both call.

<!-- fr:journal kind=decision scope=plan id=p4-lane-reason-shared created=2026-11-01T21:22:25+00:00 phase=4 -->
### p4-lane-reason-shared · decision · lane_of's landed branch now speaks gated_pr_lane's reason (phase 4)

The one held-gate rule is gated_pr_lane(pr); lane_of calls it on the batch PR (the ledger is that PR's labels). Its reason changed from "landed, held by a post-merge gate (...)" to "merged, held by gate:<g> ..." and now carries pass_command (with --notes), as R13 asks; the existing lane tests (walk, `fr gate pass --pr N --gate g`) stay green.

<!-- fr:journal kind=discovery scope=plan id=p4-facts-schema-pins created=2026-11-01T21:22:25+00:00 phase=4 -->
### p4-facts-schema-pins · discovery · several test modules pin FACTS_SCHEMA literally (phase 4)

Moving FACTS_SCHEMA 12 to 13 turned red literal pins in test_triage_* (collect, cli, facts_schema3, exit_gates_facts, labels_filter, model, state_integrity); updated them. Committed scenario fixtures stamped schema 12 still load (13 reads 3..13) and were left alone.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-11-01T21:22:25+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

one read added across the existing adapters, following list_open_prs; nothing duplicated to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t2 created=2026-11-01T21:22:25+00:00 phase=4 -->
### no-refactor-p4-t2 · discovery · no-refactor-because P4.T2 (phase 4)

collect gained one helper beside _closed_in_progress; no shared code to extract

<!-- fr:journal kind=discovery scope=plan id=p4-facts-schema-pins-2 created=2026-11-01T21:39:33+00:00 phase=4 -->
### p4-facts-schema-pins-2 · discovery · Correction to p4-facts-schema-pins: six scenario fixtures WERE regenerated (phase 4)

p4-facts-schema-pins says the scenario fixtures were left alone. That is wrong: commit 0f99f1461 regenerated six of them (cancelled-terminal, claims-expired, claims-held, config-skew, retire-sync, settle facts JSON) for the schema 13 facts. The older entry stays as written; this one corrects it.

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-11-01T21:50:41+00:00 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · board.html never surfaced gated_unread or a gated-prs truncation; an unread repo looked like empty lanes (phase 4)

Raised by the dispatched phase-4 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-11-01T21:50:41+00:00 phase=4 state=open review_scope=in -->
### p4-r2 · finding [open] (reviewer: in scope) · lane_of's batch path printed --no-run-evidence for devops, which gate pass refuses while the run names the branch (phase 4)

Raised by the dispatched phase-4 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p4-r3 created=2026-11-01T21:50:41+00:00 phase=4 state=open review_scope=in -->
### p4-r3 · finding [open] (reviewer: in scope) · gated_pr_lane reason had no separator between gate and owed act (phase 4)

Raised by the dispatched phase-4 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p4-r4 created=2026-11-01T21:50:41+00:00 phase=4 state=open review_scope=in -->
### p4-r4 · finding [open] (reviewer: in scope) · gated-PR Need ref 'PR #n' was not repo-qualified (phase 4)

Raised by the dispatched phase-4 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p4-r5 created=2026-11-01T21:50:41+00:00 phase=4 state=open review_scope=in -->
### p4-r5 · finding [open] (reviewer: in scope) · glab/tea scopes got a permanent gated-unread Need per repo (phase 4)

Raised by the dispatched phase-4 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p4-r6 created=2026-11-01T21:50:41+00:00 phase=4 state=open review_scope=in -->
### p4-r6 · finding [open] (reviewer: in scope) · two label reads per collected repo per pass; one OR search would halve it (phase 4)

Raised by the dispatched phase-4 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p4-r7 created=2026-11-01T21:50:41+00:00 phase=4 state=open review_scope=in -->
### p4-r7 · finding [open] (reviewer: in scope) · journal p4-facts-schema-pins said fixtures were left alone, but six were regenerated (phase 4)

Raised by the dispatched phase-4 code reviewer.

<!-- fr:journal kind=finding scope=plan id=p4-r8 created=2026-11-01T21:50:41+00:00 phase=4 state=open review_scope=out -->
### p4-r8 · finding [open] (reviewer: out of scope) · facts schema pinned in three model.py places and seven test modules (phase 4)

Raised by the dispatched phase-4 code reviewer.

<!-- fr:journal kind=review scope=plan id=p4-review created=2026-11-01T21:50:41+00:00 phase=4 -->
### p4-review · review · phase 4 code review (phase 4)

8 findings raised (p4-r1..p4-r8): r1–r5 and r7 fixed, r6 refuted with reasoning, r8 (out, pre-existing) resolved out-of-scope. 278 affected tests green after the fixes; the 3988-test triage/gate/tripwire/acceptance set was green before them.

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-11-01T21:50:41+00:00 phase=4 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: board.html never surfaced gated_unread or a gated-prs truncation; an unread repo looked like empty lanes (phase 4)

Fixed in dc237f1cd: gated_notes() feeds board.html's notes with each unread repo and gated-prs truncation; render test.

<!-- fr:journal kind=finding scope=plan id=p4-r2-resolved created=2026-11-01T21:50:41+00:00 phase=4 state=fixed resolves=p4-r2 -->
### p4-r2-resolved · finding [fixed] · resolves p4-r2: lane_of's batch path printed --no-run-evidence for devops, which gate pass refuses while the run names the branch (phase 4)

Fixed in dc237f1cd: pass_command gained a resolve-run mode omitting both flags, used on the batch path; bare PRs keep --no-run-evidence; test.

<!-- fr:journal kind=finding scope=plan id=p4-r3-resolved created=2026-11-01T21:50:41+00:00 phase=4 state=fixed resolves=p4-r3 -->
### p4-r3-resolved · finding [fixed] · resolves p4-r3: gated_pr_lane reason had no separator between gate and owed act (phase 4)

Fixed in dc237f1cd: 'held by gate:tester (walk its gated rows, or `…`); gate:devops (`…`)'.

<!-- fr:journal kind=finding scope=plan id=p4-r4-resolved created=2026-11-01T21:50:41+00:00 phase=4 state=fixed resolves=p4-r4 -->
### p4-r4-resolved · finding [fixed] · resolves p4-r4: gated-PR Need ref 'PR #n' was not repo-qualified (phase 4)

Fixed in dc237f1cd: ref is <owner/repo>#<n>; two-repo test.

<!-- fr:journal kind=finding scope=plan id=p4-r5-resolved created=2026-11-01T21:50:41+00:00 phase=4 state=fixed resolves=p4-r5 -->
### p4-r5-resolved · finding [fixed] · resolves p4-r5: glab/tea scopes got a permanent gated-unread Need per repo (phase 4)

Fixed in dc237f1cd folds unsupported reads into one Need per backend; 199abe794 (orchestrator) types the unsupported backend from the UnsupportedForgeOperation cause instead of parsing the message, with a test that a look-alike message stays a real failure.

<!-- fr:journal kind=finding scope=plan id=p4-r6-resolved created=2026-11-01T21:50:41+00:00 phase=4 state=refuted resolves=p4-r6 -->
### p4-r6-resolved · finding [refuted] · resolves p4-r6: two label reads per collected repo per pass; one OR search would halve it (phase 4)

GitHub's REST issues?labels= filter ANDs its labels, so the single OR query exists only on the CLI search path; keeping one read shape across both transports (the cloud driver runs REST-only) beats a CLI-only optimisation. The cost stays linear in collected repos either way (2N vs N, same class), and paced/partial passes skip carried repos. Revisit if collect quota becomes the bottleneck.

<!-- fr:journal kind=finding scope=plan id=p4-r7-resolved created=2026-11-01T21:50:41+00:00 phase=4 state=fixed resolves=p4-r7 -->
### p4-r7-resolved · finding [fixed] · resolves p4-r7: journal p4-facts-schema-pins said fixtures were left alone, but six were regenerated (phase 4)

Fixed in 8f592de1f: correcting plan-journal discovery p4-facts-schema-pins-2 (append-only).

<!-- fr:journal kind=finding scope=plan id=p4-r8-resolved created=2026-11-01T21:50:41+00:00 phase=4 state=open resolves=p4-r8 out_of_scope=true -->
### p4-r8-resolved · finding [out-of-scope] · resolves p4-r8: facts schema pinned in three model.py places and seven test modules (phase 4)

Pre-existing pattern from earlier schema bumps; this change moved the pin 12→13 everywhere it already lived and added no new pin site.
