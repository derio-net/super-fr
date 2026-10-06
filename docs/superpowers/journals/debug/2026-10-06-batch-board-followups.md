# Journal: 2026-10-06-batch-board-followups

<!-- fr:journal kind=root-cause scope=debug id=three-causes created=2026-10-06T08:13:19+00:00 -->
### three-causes · root-cause · Three independent causes, not one

#987: a merge stop (MergeStopError, e.g. unresolvable conflict) is execution-time state held only in the driver's memory (the drive session's 'reported' set in commands/triage_batch_cmd.py) and its log; the board hint is the first action of the pure drive_pass over facts+judgements, so it reads 'merge ready' (kanban._ACTION_PHRASES). A fix needs a persisted merge-stop record. #1000: batch_drive.finished_waves counts cancelled/abandoned as terminal (spec R8); render.py hides finished waves and history.py lists them as 'Finished waves' with no cancelled distinction, a presentation gap. #1001: markup/CSS of render.wave_table (table.grid in .tablewrap) at 390px. Stopped to ask the operator before fixing, per the batch's debugging rule.

<!-- fr:journal kind=repro scope=debug id=repro-1001 created=2026-10-06T08:35:52+00:00 -->
### repro-1001 · repro · Wave table wraps ids at every hyphen at 390px

Rendered the live super-fr board from a scratch copy of the triage state and opened it at 390x844. The wave table sat in a 720px scroller (p2-r2's fix), but split its width over 8 columns: Batch ~84px, Issues ~92px, so 'debug-journal-push' and 'super-fr#871' wrapped at each hyphen. Why took 217px.
