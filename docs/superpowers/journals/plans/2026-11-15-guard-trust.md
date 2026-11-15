<!-- fr:journal-schema=4 -->
# Journal: 2026-11-15-guard-trust

<!-- fr:journal kind=discovery scope=plan id=p1-full-suite-starved created=2026-11-15T18:01:31+00:00 phase=1 -->
### p1-full-suite-starved · discovery · full suite could not finish on this host (load 15-23, several concurrent suites) (phase 1)

`pytest -n auto` advanced ~14 tests/min (4% in 55 min) beside other sessions' suites, so it was stopped.
Evidence instead: the touched suites (isolation decision core, claude and hermes hooks, archive,
artifact-paths tripwire, mirror/parity tripwires, harness tests), the new archive tests and
`bun test` (293 pass) are green; `fr docs check` and the change-fragment gate pass. The full
suite is owed (deliver reruns it).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-15T18:01:31+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

two one-line additions beside the existing plans test; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-15T18:01:31+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

prose and generated mirrors only; nothing to clean
