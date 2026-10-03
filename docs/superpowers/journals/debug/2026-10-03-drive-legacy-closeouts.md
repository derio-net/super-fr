# Journal: 2026-10-03-drive-legacy-closeouts

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-03T19:11:25+00:00 -->
### repro · repro · drive --once plans a close-out for every batch merged before 5.2.0

On derio-net/super-fr with fr 5.2.0, `fr triage batch drive --once --repo derio-net/super-fr` (no --yes) prints 50 `closeout <id>: start derio-net/super-fr/run/closeout-<id>` lines and `in flight 4, merged 50, pending 3, closing 50`, and no other action. Every batch that merged before the driver existed is planned for a close-out, including batches closed out by hand (e.g. gate-ordering, archived in #874). With --yes it would open 50 runner tabs and run post_merge 50 times. Found by wave-driver Test Plan item 15.
