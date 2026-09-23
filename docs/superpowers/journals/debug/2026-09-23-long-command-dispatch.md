# Journal: 2026-09-23-long-command-dispatch

<!-- fr:journal kind=repro scope=debug id=f98f801da3c4 created=2026-09-23T12:20:10 -->
### f98f801da3c4 · repro · OpenCode executor ran the full suite without timeout twice (killed at 120 s) despite the long-commands clause

#564's Test Plan step 2 smoke (fr 4.17.1, OpenCode 1.18.32; throwaway repo whose suite includes a 150 s test; one mechanical phase; executor `fr-phase-executor-mechanical` on `claude-haiku-4.5`). From `opencode.db`, the executor's full-suite bash calls were: `python -m pytest -q` with no timeout, killed at 120.1 s; then `(python -m pytest -q > file; …)` with no timeout, killed at 120.1 s; then `timeout: 600000`, which passed in 150 s. The orchestrator (`build`, gpt-5.6-luna) passed `timeout: 240000` on both of its own suite runs. The agent file does carry `**Harness — long commands:**` (installed agent, line 119 of the body). gh#582.

<!-- fr:journal kind=hypothesis scope=debug id=3edbef2b02b6 created=2026-09-23T12:20:11 -->
### 3edbef2b02b6 · hypothesis · The dispatch prompt names the exact suite command and says nothing about its duration

The executor's first user message, composed by the orchestrator from the dispatch brief, said: 'run the FULL suite exactly with `python -m pytest -q`'. That is a concrete command with no timeout or duration, so the executor followed the specific instruction literally over a general clause near the end of its system prompt. The brief (`_build_member_brief`) is structural JSON that carries nothing about long commands, so an orchestrator has nothing to relay. To verify: what fr-goal §5 tells the orchestrator to put in that prompt.

<!-- fr:journal kind=root-cause scope=debug id=4a5ede29e59e created=2026-09-23T12:20:49 -->
### 4a5ede29e59e · root-cause · The long-command rule never reaches the executor at the moment it acts

The rule lives only in the agent file (`**Harness — long commands:**`, near the end of the body). The per-phase brief that `fr run advance` prints (`run_cmd._build_member_brief`) is structural JSON with no execution guidance, and fr-goal §5 says only that the orchestrator 'dispatches the same brief'. So the orchestrator writes its own task prompt, and in the smoke that prompt named the exact suite command. A small model followed that concrete instruction and ignored a general clause far away in its system prompt. The orchestrator itself, which is the reader of the brief, applied timeouts correctly. The fix is to carry the rule in the brief, resolved for the harness `advance` detects, and have §5 relay it verbatim.

<!-- fr:journal kind=finding scope=debug id=f-brief-rule created=2026-09-23T12:24:31 state=fixed -->
### f-brief-rule · finding [fixed] · Every phase-member brief carries the harness's long-command rule, relayed verbatim by fr-goal

New `fr.harness.long_commands` holds one rule per harness plus a neutral fallback. `_build_member_brief` emits it as `long_commands`, for the harness `advance` detects, and fr-goal §5 tells the orchestrator to copy it into the task prompt verbatim, beside any suite command. Pinned red-first in `test_run_cli.py` (KeyError, then per-harness content, with the neutral fallback when the harness is unknown). `test_long_command_rule.py` guards drift: each harness's load-bearing token (run_in_background / 600000 / background=true) must appear in both the rule and the agent clause, and fr-goal must name `long_commands`.

<!-- fr:journal kind=review scope=debug id=231e8834e0f5 created=2026-09-23T12:34:36 -->
### 231e8834e0f5 · review · Independent review of 6672ff3c: two findings, one refuted with a probe, one declined in scope

A separately dispatched reviewer read the fix statically (it had no shell). **(1) Refuted:** the claim that a bad `FR_HARNESS` would crash `advance` after the unit was persisted `running` with no brief. `_open_dispatch` (called before `save_run_state`) already calls `detect_harness` unguarded, so the error fires first. A probe (grouped advance with `FR_HARNESS=bogus`) exits 1 on `HarnessError` with the run file byte-identical and no brief printed. The raw traceback on a mistyped `FR_HARNESS` predates this change and is reported separately. **(2) Declined in scope:** `deliver`'s flat brief carries no `long_commands`. The orchestrator reads fr-goal itself, and in the smoke it passed timeouts on both of its suite runs; the actor that lacked the rule at the moment of acting was the dispatched executor, which is what this fixes. Everything else it checked held: dispatch is intra-harness, so detection at advance time is the executor's harness; no brief consumer parses keys strictly; the rule texts match the agent clause; and the fr-goal cap and neutrality are fine.
