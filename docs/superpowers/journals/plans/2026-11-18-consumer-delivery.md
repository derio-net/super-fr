<!-- fr:journal-schema=4 -->
# Journal: 2026-11-18-consumer-delivery

<!-- fr:journal kind=discovery scope=plan id=p1-bun-flaky-under-load created=2026-11-18T16:03:17+00:00 phase=1 -->
### p1-bun-flaky-under-load · discovery · bun timing tests time out on a loaded host (phase 1)

marker relative-PATH, pin registration and quiet-placement tests failed only while pytest ran in parallel; green alone (host load average above 30).

<!-- fr:journal kind=decision scope=plan id=p1-rule-list-env-var created=2026-11-18T16:03:17+00:00 phase=1 -->
### p1-rule-list-env-var · decision · install.sh hands the rule list to the delivery as FR_OPENCODE_RULES (phase 1)

One space-separated env var keeps the positional contract (install <dir>) that every caller and test uses; the list stays defined once, in CLAUDE_RULES.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-18T16:03:17+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

smoke and change fragment only, no code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-18T16:03:17+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

docs and acceptance bookkeeping, no code to clean
