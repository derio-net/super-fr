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
