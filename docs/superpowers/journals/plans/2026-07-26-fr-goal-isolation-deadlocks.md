# Journal: 2026-07-26-fr-goal-isolation-deadlocks

<!-- fr:journal kind=discovery scope=plan id=p1-d1 created=2026-07-26T15:37:40 phase=1 -->
### p1-d1 · discovery · decision() must assert exit 0 or every allow-test passes vacuously (phase 1)

First cut of test_hooks_phase_executor_guard.py returned None from decision() whenever stdout was empty. An ABSENT hook also produces empty stdout, so 7 of 13 tests 'passed' during the RED run against a file that did not exist. decision() now asserts returncode == 0 first; the RED run then failed all 13. Worth carrying to any future hook test in this repo.
