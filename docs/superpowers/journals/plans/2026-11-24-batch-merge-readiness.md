<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-batch-merge-readiness

<!-- fr:journal kind=decision scope=plan id=p1-readiness-module-imports created=2026-11-25T00:48:18+00:00 phase=1 -->
### p1-readiness-module-imports · decision · readiness imports wave_queue; wave_queue imports readiness lazily (phase 1)

`fr.triage.readiness` needs `QueueSnapshot`, `base_refusal`, `is_deferred` and the new
`queue_held_reason` from `wave_queue`, and `wave_queue._ready` / `plan_queue` call
`batch_readiness`. So readiness imports wave_queue at module level and wave_queue
imports readiness inside the two functions (and under TYPE_CHECKING for
`QueuePlan.readiness`), the same lazy pattern batch_drive and wave_queue already use.

<!-- fr:journal kind=decision scope=plan id=p1-livepr-url created=2026-11-25T00:48:18+00:00 phase=1 -->
### p1-livepr-url · decision · LivePr gains url so R6's links need no host guess (phase 1)

R6 links the PR and its checks tab; `LivePr` carried no URL. Both Snapshot builders
now fill `LivePr.url` from the batch PR's facts; `fact_cursors` (in readiness.py)
fills `Snapshot.cursors` the same way for both builders.

<!-- fr:journal kind=decision scope=plan id=p1-queue-held-verdict created=2026-11-25T00:48:18+00:00 phase=1 -->
### p1-queue-held-verdict · decision · Queue held means another scope holds the hold, or this scope's open queue is halted (phase 1)

R5's first verdict reads `wave_queue.queue_held_reason`: the R31 hold of another scope
(`held_by_other`, now shared with `_held`) or the `live_halt` of this scope's open
queue. It never changes `admits`, which stays the queue's own entry rule.

<!-- fr:journal kind=discovery scope=plan id=p1-test-worlds-default-delivered created=2026-11-25T00:48:18+00:00 phase=1 -->
### p1-test-worlds-default-delivered · discovery · Every queue and drive test world now defaults to a delivered run (phase 1)

83 existing tests assumed approved + green merges. Their snapshot helpers (planner,
operator view, batch_drive, draft_red), the board fixtures (`DELIVERED` in
triage_board_fixtures) and the drive command's World/DriveCheckout (a delivered PR
head serves one `deliver: done` cursor; `world.pr(..., delivered=False)` opts out)
now default to delivered, so each still tests what it did; new tests cover the hold.

<!-- fr:journal kind=discovery scope=plan id=p1-batch-drive-at-budget created=2026-11-25T00:48:18+00:00 phase=1 -->
### p1-batch-drive-at-budget · discovery · batch_drive.py sits exactly at its 2275-line budget (phase 1)

`_member_reports` now reads `batch_readiness`, and `Snapshot.cursors` / `LivePr.url`
were added; comments were trimmed to stay at 2275. Phase 2's board work in batch_drive
has no headroom: put it in readiness.py or kanban.

<!-- fr:journal kind=discovery scope=plan id=p1-cursor-unread-not-cached created=2026-11-25T00:48:18+00:00 phase=1 -->
### p1-cursor-unread-not-cached · discovery · The driver no longer caches an unread cursor head (phase 1)

`_Driver.cursor_at` used to cache `None` for a head the clone could not reach, so a
head fetched later in the same process was never read again. It now caches only a
`read` answer (a commit never changes); an `unread` one is asked again next pass.

<!-- fr:journal kind=discovery scope=plan id=p1-facts-fixtures-regenerated created=2026-11-25T00:48:18+00:00 phase=1 -->
### p1-facts-fixtures-regenerated · discovery · Facts schema 17 regenerates six committed scenario fixtures (phase 1)

`tests/scenarios/fixtures/*-facts.json` carry the facts stamp; their generators
(`make_*_facts.py`) were re-run, so only the `schema` line moved.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-25T00:48:18+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a smoke task: one docstring module, one test and a fragment, nothing to clean
