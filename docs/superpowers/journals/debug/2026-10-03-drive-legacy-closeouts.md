# Journal: 2026-10-03-drive-legacy-closeouts

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-03T19:11:25+00:00 -->
### repro · repro · drive --once plans a close-out for every batch merged before 5.2.0

On derio-net/super-fr with fr 5.2.0, `fr triage batch drive --once --repo derio-net/super-fr` (no --yes) prints 50 `closeout <id>: start derio-net/super-fr/run/closeout-<id>` lines and `in flight 4, merged 50, pending 3, closing 50`, and no other action. Every batch that merged before the driver existed is planned for a close-out, including batches closed out by hand (e.g. gate-ordering, archived in #874). With --yes it would open 50 runner tabs and run post_merge 50 times. Found by wave-driver Test Plan item 15.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-10-03T19:11:26+00:00 -->
### root-cause · root-cause · drive_pass owes a close-out to any landed batch without a closeout event, and the default selection is 'all' when no batch has a wave

`batch_drive.drive_pass` step 2 skips a landed batch only when it has a `CloseoutEvent`, an event type that exists only since schema 3 (5.2.0); no pre-driver batch carries one, and nothing in judgements or facts records a hand close-out. `drive` with no ids selects "batches with a wave, else all" (spec Design B), and no super-fr batch has a wave yet, so all 74 batches are selected and the 50 landed ones all owe a close-out. The board had the same defect (wave-driver ri-3) and was fixed by requiring `b.wave` in `views.needs_you`; the driver pass never got the guard, and the spec never stated it.
