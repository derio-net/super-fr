# Journal: 2026-10-04-drive-cap-held

<!-- fr:journal kind=repro scope=debug id=f6334fddb4de created=2026-10-04T04:25:20+00:00 -->
### f6334fddb4de · repro · drive plan silent when the in-flight cap holds the selection

gh#913: four unselected batches in flight, two selected wave-1 batches proposed, max_inflight 4. `drive --once` printed only `in flight 0, merged 0, pending 2, closing 0` and dispatched nothing, no line saying why. Repro as a pure drive_pass snapshot: unselected occupants fill the cap, selected batches proposed → actions == ().

<!-- fr:journal kind=root-cause scope=debug id=622436665143 created=2026-10-04T04:25:21+00:00 -->
### 622436665143 · root-cause · drive_pass's cap branch counts a held batch as pending and emits no action

`fr/triage/batch_drive.py` drive_pass step 4: `if cap_used >= snap.max_inflight: pending += 1; continue`. The cap reads every batch (rg-3) but the summary's in-flight figure reads only the selection, so the only output is a pending count that looks idle. Every other non-dispatch reason (dead dependency) emits a `blocked` action; the cap emits nothing. Single cause; the command (`_act`) only prints actions it is given.

<!-- fr:journal kind=finding scope=debug id=2d48a20cc162 created=2026-10-04T04:37:49+00:00 state=fixed -->
### 2d48a20cc162 · finding [fixed] · drive_pass emits a held action when the in-flight cap holds a batch

`batch_drive.py`: new `held` ActionKind; the cap branch tracks the occupying batch ids (in flight, not merging this pass, plus this pass's dispatches) and emits `held <id>: the in-flight cap (N) is full: <occupants>`. `triage_batch_cmd._act` treats `held` like `blocked`. Pinned by `test_a_batch_the_cap_holds_says_so_and_names_the_occupants` and the CLI's `test_the_cap_counts_batches_outside_the_selection` (both red first). Two existing tests asserted the silence (`actions == ()`) and were updated.
