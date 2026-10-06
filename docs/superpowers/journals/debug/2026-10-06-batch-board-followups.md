# Journal: 2026-10-06-batch-board-followups

<!-- fr:journal kind=root-cause scope=debug id=three-causes created=2026-10-06T08:13:19+00:00 -->
### three-causes · root-cause · Three independent causes, not one

#987: a merge stop (MergeStopError, e.g. unresolvable conflict) is execution-time state held only in the driver's memory (the drive session's 'reported' set in commands/triage_batch_cmd.py) and its log; the board hint is the first action of the pure drive_pass over facts+judgements, so it reads 'merge ready' (kanban._ACTION_PHRASES). A fix needs a persisted merge-stop record. #1000: batch_drive.finished_waves counts cancelled/abandoned as terminal (spec R8); render.py hides finished waves and history.py lists them as 'Finished waves' with no cancelled distinction, a presentation gap. #1001: markup/CSS of render.wave_table (table.grid in .tablewrap) at 390px. Stopped to ask the operator before fixing, per the batch's debugging rule.

<!-- fr:journal kind=repro scope=debug id=repro-1001 created=2026-10-06T08:35:52+00:00 -->
### repro-1001 · repro · Wave table wraps ids at every hyphen at 390px

Rendered the live super-fr board from a scratch copy of the triage state and opened it at 390x844. The wave table sat in a 720px scroller (p2-r2's fix), but split its width over 8 columns: Batch ~84px, Issues ~92px, so 'debug-journal-push' and 'super-fr#871' wrapped at each hyphen. Why took 217px.

<!-- fr:journal kind=finding scope=debug id=fix-987 created=2026-10-06T08:35:53+00:00 state=fixed -->
### fix-987 · finding [fixed] · Driver records merge stops; board reads them

New fr.triage.merge_stops (merge-stops.json beside drive.lock, not judgements.yaml: a new event kind would break every older closed-world reader). _merge_batch records a stop at action.head unless HeadMovedError and clears on merge/already-merged. build_board(stops=) counts a stop only while the PR is OPEN at that head: hint 'needs you: merge stopped: <reason>', needs_you; a batch whose after names it waits on it (the pure pass otherwise planned its dispatch as if the merge landed). Tests: test_triage_kanban merge-stop tests, test_triage_merge_stops, test_a_stopped_merge_is_recorded_for_the_board_and_cleared_when_it_lands, test_a_moved_head_is_not_recorded_as_a_stop.

<!-- fr:journal kind=finding scope=debug id=fix-1000 created=2026-10-06T08:35:54+00:00 state=fixed -->
### fix-1000 · finding [fixed] · Cancelled waves are named

views.cancelled_waves: finished waves whose every batch is cancelled or abandoned. The finished_waves predicate is unchanged (spec R8). History tab reads 'Wave N · cancelled'; the board's waves section says the wave was cancelled and left, with a link to history. Tests: test_a_wave_whose_batches_were_all_cancelled_is_labelled_cancelled, test_a_wave_that_left_the_board_because_it_was_cancelled_is_named.

<!-- fr:journal kind=finding scope=debug id=fix-1001 created=2026-10-06T08:35:56+00:00 state=fixed -->
### fix-1001 · finding [fixed] · Wave table stacks into labelled cards under 480px

wave_table cells carry data-label and the table is 'grid stack'; GRID_CSS adds a <=480px block that turns rows into cards with the column name before each value. Verified live at 390px: wrapper scrollWidth == clientWidth (343), nothing wraps mid-id. test_the_phone_gutter_is_sixteen_pixels now reads every phone media block. Test: test_the_wave_table_stacks_into_labelled_cards_at_phone_width.

<!-- fr:journal kind=review scope=debug id=review-1 created=2026-10-06T08:37:35+00:00 -->
### review-1 · review · Independent review: no blocking findings

An independent read-only reviewer checked the HeadMovedError order, the head the stop is recorded at, clearing, the drive lock, hint precedence, wave-key sorting, the history index and CSS scope: all correct. It made four minor findings. (1) Each pass rewrote the stop with a new time: fixed, record_stop skips the same head+reason (test_the_same_stop_again_keeps_the_first_time). (2) An unknown PR head keeps a stop live while the PR is open: by design and documented, no change. (3) Stops for batches whose PR closed are never pruned: cosmetic, since they are never shown; out of scope, not filed. (4) Test gap: the HeadMovedError guard was already pinned (test_a_moved_head_is_not_recorded_as_a_stop), and the non-open-PR guard is now pinned (test_a_merge_stop_on_a_pr_no_longer_open_no_longer_counts).
