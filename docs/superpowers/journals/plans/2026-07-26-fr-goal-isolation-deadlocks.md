# Journal: 2026-07-26-fr-goal-isolation-deadlocks

<!-- fr:journal kind=discovery scope=plan id=p1-d1 created=2026-07-26T15:37:40 phase=1 -->
### p1-d1 · discovery · decision() must assert exit 0 or every allow-test passes vacuously (phase 1)

First cut of test_hooks_phase_executor_guard.py returned None from decision() whenever stdout was empty. An ABSENT hook also produces empty stdout, so 7 of 13 tests 'passed' during the RED run against a file that did not exist. decision() now asserts returncode == 0 first; the RED run then failed all 13. Worth carrying to any future hook test in this repo.

<!-- fr:journal kind=discovery scope=plan id=p2-d1 created=2026-07-26T15:43:34 phase=2 -->
### p2-d1 · discovery · fr-goal SKILL.md was already at the hard 120-line cap (phase 2)

test_skill_validation.py::test_under_120_lines is a hard cap with no exemption, and fr-goal/SKILL.md sat exactly at 120. The §6 addition had to be paid for. Reclaimed by reflowing §1, §3, §6, §7, §8 to the ~92-char width the file already used on its longest lines — no content dropped — and by folding the new constraint into §6's existing paragraph instead of adding a standalone block. Back to exactly 120. Any future addition to this skill must budget the same way.

<!-- fr:journal kind=discovery scope=plan id=p2-d2 created=2026-07-26T15:43:34 phase=2 -->
### p2-d2 · discovery · The allowlist script needed TWO independent probes, not one (phase 2)

The original script had a single early exit (grep -q QUALIFIED). Adding the message repair under it would have reproduced the exact bug the file already documents: a probe satisfied by one surface reporting 'already done' for another. A hook whose case arm was already fixed would never get its message repaired. Restructured into two independently-probed repairs — case arm (fail-loud on anchor drift) and the Exempt: message (silent no-op when absent, since the message is the org hook's prose, not super-fr's to require). test_message_repaired_even_when_case_already_correct pins it.
