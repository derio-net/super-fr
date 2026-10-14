<!-- fr:journal-schema=2 -->
# Journal: 2026-10-14-merge-truth

<!-- fr:journal kind=decision scope=plan id=p1-settle-drops-release-op created=2026-10-14T00:20:45+00:00 phase=1 -->
### p1-settle-drops-release-op · decision · A settle op replaces the release op for the same key (phase 1)

plan_sync drops the owed release for a key that also has a settle target (a closed member of a releasing batch): settle releases the own marker and unlabels in one pass, and carries the batch so claims_released is still recorded. Otherwise the pass would edit the same issue twice.

<!-- fr:journal kind=decision scope=plan id=p1-settle-closed-needs-now created=2026-10-14T00:20:45+00:00 phase=1 -->
### p1-settle-closed-needs-now · decision · settle_closed takes now= beside the planned arguments (phase 1)

The plan's signature (client, repo, number, me, trusted) has no clock; the released marker form needs one, so settle_closed(client, repo, number, *, me, now, trusted) is keyword-only. A label-only settle (no own marker) returns the new Done action 'unlabelled', distinct from 'none' (left alone).

<!-- fr:journal kind=decision scope=plan id=p1-carried-settle-waits created=2026-10-14T00:20:45+00:00 phase=1 -->
### p1-carried-settle-waits · decision · Settle of a carried repo waits, by the key's repo (phase 1)

settle is in _LIVE_READ_ACTIONS and read_repo() resolves it by env.owner_repo(key) because a settle may name no batch; a skipped repo's settles are not planned (unread filter, same key repo). facts.json is host-local (not a REF_FILES entry), so retire writes it with write_text_atomic and no state-ref publication is needed.

<!-- fr:journal kind=discovery scope=plan id=p1-fake-forge-closed-filter created=2026-10-14T00:20:45+00:00 phase=1 -->
### p1-fake-forge-closed-filter · discovery · FakeForge now filters the closed read by label (phase 1)

tests/unit/triage_fixtures.py FakeForge.list_issues returned the closed set regardless of the label filter; with two label reads it now filters (gh ANDs labels, one per read), so the single-label tests keep their meaning.

<!-- fr:journal kind=discovery scope=plan id=p1-idle-guard-flake-under-load created=2026-10-14T00:20:45+00:00 phase=1 -->
### p1-idle-guard-flake-under-load · discovery · test_run_idle_guard hang test fails under the full parallel suite only (phase 1)

Full suite: 12309 passed, 118 skipped, 1 failed (tests/integration/test_run_idle_guard.py::test_fails_open_when_fr_hangs_and_does_not_hang_with_it). The file passes alone (52 passed); the test is wall-clock bound and touches nothing this phase changed.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-10-14T00:20:45+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

skeleton task: a change fragment and a stub; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-14T00:20:45+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

release() rewrites its marker in one edit line; settle_closed's differs (labels, state check), so no shared helper is worth extracting

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-14T00:20:45+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

plan_sync/execute grew by one branch each; ClaimOp.label is the only shared bit and was added with the change

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-14T00:20:45+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

the settle path reuses claim_sync.execute and _claim_write; the repo-of-op lookup was extracted as _op_repo/read_repo in the same change

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t7 created=2026-10-14T00:20:45+00:00 phase=1 -->
### no-refactor-p1-t7 · discovery · no-refactor-because P1.T7 (phase 1)

the withdraw path is its own helper (_withdraw_take) from the start; nothing duplicated

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t8 created=2026-10-14T00:20:45+00:00 phase=1 -->
### no-refactor-p1-t8 · discovery · no-refactor-because P1.T8 (phase 1)

one helper (_forget_claims) added; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t9 created=2026-10-14T00:20:45+00:00 phase=1 -->
### no-refactor-p1-t9 · discovery · no-refactor-because P1.T9 (phase 1)

scenario scripts and the shared fake gh; nothing to clean
