# Journal: 2026-09-28-tests-gate-tmpdir-log

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-28T14:26:11+00:00 -->
### repro · repro · deliver tests= refused a $TMPDIR suite log that the orchestrator did write (#765)

Run 2026-09-28-feat-gh-759, session a913f2c8. One Bash call at 12:51:29Z ran `fr run advance …` (which opened step/deliver at 12:51:33Z) and then `uv run pytest … > $TMPDIR/full-suite.log 2>&1`, backgrounded; its task-notification reported completed at 12:55:48Z. `fr run resolve --record` at 12:56:02Z refused: 'no command of YOURS wrote it … since this unit opened at 12:51:33'. A rerun into a literal scratchpad path, as its own command at 12:56:10Z, passed.

<!-- fr:journal kind=ruled-out scope=debug id=h1-tmpdir-not-expanded created=2026-09-28T14:26:11+00:00 -->
### h1-tmpdir-not-expanded · ruled-out · Refuted: the gate does not expand an inherited $TMPDIR

The issue's diagnosis. `_resolve_target` drops an unresolved LEADING variable and matches the rest by trailing path segments, so `> $TMPDIR/full-suite.log`, its quoted form, the `fr isolation exec -- '…'` form and `| tee $TMPDIR/…` all match the resolved log (probed via `telemetry._writes`). Only `${TMPDIR}full-suite.log` (no slash) fails, and §8 does not spell it that way.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-09-28T14:26:12+00:00 -->
### root-cause · root-cause · The writing command was issued 4s before the unit it evidences opened — because it opened it

`orchestrator_wrote_since` keeps only tool_use records with timestamp >= `since` (the unit's `opened`). The suite shared a Bash call with `fr run advance`, and that advance is what opened step/deliver, so the call's timestamp (12:51:29) precedes `opened` (12:51:33) by construction and it is discarded, which yields `[]` and the 'no command of YOURS' message. The literal-path rerun passed only because it was a separate, later command. §8 never says the suite must run AFTER the advance that opens deliver, and the refusal cannot tell 'nobody wrote it' from 'you wrote it before this unit opened'.

<!-- fr:journal kind=finding scope=debug id=fix created=2026-09-28T14:33:05+00:00 state=fixed -->
### fix · finding [fixed] · Refusal names a pre-open writer; §8 says to run the suite as its own command after the advance

`run_cmd._wrote_before` re-reads the orchestrator's writers with no lower bound when the in-unit window list is empty; if one straddles `opened`, deliver refuses with 'issued before this unit opened … run the suite again as its own command' instead of 'no command of YOURS'. The gate is unchanged: it still refuses. fr-goal SKILL.md §8 (and both mirrors) now says to run the suite AFTER the `fr run advance` that opens deliver. Pinned by `test_a_suite_issued_before_the_unit_opened_is_refused_and_says_so` (red before: the old wording). Full suite: 6818 passed.
