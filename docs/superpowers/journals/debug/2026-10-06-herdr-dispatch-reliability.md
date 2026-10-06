# Journal: 2026-10-06-herdr-dispatch-reliability

<!-- fr:journal kind=repro scope=debug id=aafef39351a9 created=2026-10-06T15:32:28+00:00 -->
### aafef39351a9 · repro · herdr dispatch: unsubmitted brief (#956), agent_pane_busy ends the drive (#931)

Both seen live 2026-10-04/05 driving waves. #956: close-out sessions sat idle >2h with the brief in Claude Code's input box (paste placeholder), never submitted; the dispatch returned success. #931: `herdr agent start` refused with `agent_pane_busy` ('target pane is not an available shell') right after `tab create`; the dispatch failed and `fr triage batch drive` exited. Not reproducible on demand (timing-dependent): reproduced by reading the code paths, HerdrRunner.dispatch and _Driver._close_out / dispatch_batch.

<!-- fr:journal kind=hypothesis scope=debug id=8012f1b4a9d0 created=2026-10-06T15:32:52+00:00 -->
### 8012f1b4a9d0 · hypothesis · Runner: dispatch confirms no handoff, so each herdr step races the one before

HerdrRunner.dispatch runs tab create -> agent start -> agent prompt back-to-back. herdr 0.9.1 requires 'agent start --pane' to be at an interactive shell prompt and fails fast (agent_pane_busy) instead of waiting; and 'agent prompt' without --wait returns once text is sent, never checking that the agent left idle. herdr has the confirmation built in: 'agent prompt --wait' fails with agent_prompt_stalled when no working/blocked state follows within 5s. Covers #956 and #931 defect 1.

<!-- fr:journal kind=hypothesis scope=debug id=eb173c9d1fc7 created=2026-10-06T15:33:03+00:00 -->
### eb173c9d1fc7 · hypothesis · Driver: a runner dispatch failure is a typer.Exit that escapes the drive loop

_Driver._close_out and dispatch_batch call _fail(..., code=1) on a runner exception, which raises typer.Exit. run_pass has no handler and batch_drive_command's loop catches only ForgeReadError, so one failed dispatch ends loop mode (unlike forge reads gh#910 and refused merges rg-4, which are reported once and retried). Covers #931 defect 2. This is a second, independent defect in fr, not fr_herdr.

<!-- fr:journal kind=repro scope=debug id=7abbf2338d65 created=2026-10-06T15:40:59+00:00 -->
### 7abbf2338d65 · repro · Live: agent_pane_busy reproduced 1 in 6 fresh workspaces; a retry on the same pane succeeds

Scratch herdr workspaces (herdr 0.9.1, cwd a trusted checkout, closed afterwards), 'agent start' run right after 'workspace create': trial 5 of 6 failed with {"error":{"code":"agent_pane_busy","message":"agent target pane <pane> is not an available shell"}}; 'agent start' on the same pane moments later succeeded. Confirms #931 defect 1 and that a bounded retry is the remedy. #956 (silent unsubmitted brief) did NOT reproduce in 6 trials (3 with 'agent prompt --wait', 3 without, ~4.9k-char brief) — timing-dependent. Without --wait, 'agent prompt' returned agent_status=idle: it confirms nothing, so a missed submit is silent by construction. With --wait it returned 'working', and herdr documents agent_prompt_stalled when no working/blocked follows within 5s.

<!-- fr:journal kind=root-cause scope=debug id=bae2531e02ad created=2026-10-06T15:41:19+00:00 -->
### bae2531e02ad · root-cause · Runner: HerdrRunner.dispatch confirms neither the pane nor the submit

agent start is attempted once against a pane whose shell may not be up (herdr fails fast with agent_pane_busy), and agent prompt is fire-and-forget (no --wait), so a brief that lands unsubmitted reads as a successful dispatch. Fix: retry agent_pane_busy (bounded), submit with --wait --until working --until blocked, and on agent_prompt_stalled press Enter once and wait again before failing loudly.

<!-- fr:journal kind=root-cause scope=debug id=1567b0469681 created=2026-10-06T15:41:28+00:00 -->
### 1567b0469681 · root-cause · Driver: a failed runner dispatch is a typer.Exit that ends loop mode

Operator decision 2026-10-06: fix both causes in the one PR. _Driver._close_out and dispatch_batch _fail(code=1) on a runner exception; nothing in run_pass or the loop catches it. Fix: a typed failure the driver reports once per cause and retries on a later pass (failed_write set, so --once still exits 1); 'batch dispatch' keeps exiting 1.

<!-- fr:journal kind=finding scope=debug id=runner-handoffs created=2026-10-06T15:54:41+00:00 state=fixed -->
### runner-handoffs · finding [fixed] · Runner confirms the pane and the submit

fr_herdr/runner.py: _start_agent retries agent_pane_busy (PANE_BUSY_TRIES=15, 2s apart), any other refusal raised as is; _submit uses agent prompt --wait --until working --until blocked --timeout 30000, and on agent_prompt_stalled sends one Enter and waits again (10s) before raising 'was not submitted'. HerdrError.code parsed from herdr's envelope. Pinned first by test_fr_herdr_runner.py (pane busy retried / bounded / other refusals not retried; stalled brief Enter-recovered / still stalled fails and closes the tab; error code parsed). Live-walked 2026-10-06: 3 real dispatches, one hit agent_pane_busy and recovered; every agent was working when dispatch returned; 'enter' accepted by send-keys (a bogus key is invalid_key).

<!-- fr:journal kind=finding scope=debug id=drive-survives-dispatch created=2026-10-06T15:54:43+00:00 state=fixed -->
### drive-survives-dispatch · finding [fixed] · A failed dispatch no longer ends the drive

triage_batch_cmd.py: RunnerDispatchError raised by dispatch_batch (batch dispatch maps it to exit 1); _Driver._dispatch_failed reports once per batch and cause, keyed on the runner error's code when present (a retry names a new pane, so the words change), sets failed_write so --once exits 1, and the pass goes on to the next action. Pinned first by test_triage_batch_drive_disruption.py (close-out and batch survive the loop and report once; one cause on a different pane each pass reported once; --once exits 1 and the next batch still dispatches).

<!-- fr:journal kind=review scope=debug id=c7b41c671fa2 created=2026-10-06T15:56:32+00:00 -->
### c7b41c671fa2 · review · Independent review: no high-severity findings; one comment added

A separate-context reviewer read runner.py, triage_batch_cmd.py and the tests. Verified correct: exception chaining (__cause__ carries .code), only RunnerDispatchError caught, in_flight and failed_write accounting, close-out take-back keeps post_merge, retry bound (15 tries/28s; only agent_pane_busy). Low findings: r1 a blind Enter could answer a dialog: mitigated (start returns only when ready; a dialog reads blocked, which the wait accepts); comment added. r2 a turn starting after the 10s Enter window is closed and retried: intended fail-loud. r3 if the close-out take-back write is itself refused, the driver exits and the event stays recorded: pre-existing shape (the old code failed there too), rare, left as is. r4 report key is batch+code, so two causes sharing a code are reported once: accepted, the line still says stopped. r5 a pane that never comes up costs ~28s per batch per pass: bounded, accepted. r6 'timeout' and 'enter' called unverified: refuted, both observed live 2026-10-06 (agent wait returned code timeout; send-keys enter ok, a bogus key invalid_key); only agent_prompt_stalled's envelope is doc-derived, as the fixture README says.
