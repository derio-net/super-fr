# Journal: 2026-10-12-quota-pacing

<!-- fr:journal kind=decision scope=plan id=p1-pacing-loop-only created=2026-10-12T06:55:45+00:00 phase=1 -->
### p1-pacing-loop-only · decision · Pacing applies to a looping drive and the cloud pass, not --once or plan mode (phase 1)

`--once` and a plan-only run keep today's behaviour (a rate limit exits with the read error's code); a loop waits, and the cloud pass exits 3. `essential` (below the floor) is decided by `quota.decide` but the loops ignore it until phase 2 builds the essential-only pass, so the quota line never claims a pass that does not exist.

<!-- fr:journal kind=discovery scope=plan id=p1-stale-exhausted-reading created=2026-10-12T06:55:45+00:00 phase=1 -->
### p1-stale-exhausted-reading · discovery · An exhausted /rate_limit reading whose reset has passed must not be waited on (phase 1)

A wait whose end is already past sleeps 0 s, and the loop would re-read and re-run forever, spending the budget it was meant to spare (found by a test whose clock was the real one). `decide` runs the pass, and `after_rate_limit` backs off as a secondary limit, when the reading's reset plus 30 s is not ahead of now.

<!-- fr:journal kind=discovery scope=plan id=p1-collect-fakes-returned-none created=2026-10-12T06:55:45+00:00 phase=1 -->
### p1-collect-fakes-returned-none · discovery · Three existing tests faked collect_into with None for the facts (phase 1)

recollect now reads facts.skipped and facts.unviewed (R2), so the fakes in test_triage_batch_drive_cmd and test_triage_batch_drive_disruption return the world's facts, as the real function does.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-12T06:55:45+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the floor reader shared the host file's mapping loader with api: in the same change (one reader of forge.yaml); nothing else to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-12T06:55:45+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the seam is one method on each adapter plus one pass-through; nothing to extract
