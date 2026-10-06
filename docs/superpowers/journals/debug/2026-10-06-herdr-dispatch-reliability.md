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
