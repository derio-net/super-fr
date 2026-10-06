# Journal: 2026-10-06-herdr-dispatch-reliability

<!-- fr:journal kind=repro scope=debug id=aafef39351a9 created=2026-10-06T15:32:28+00:00 -->
### aafef39351a9 · repro · herdr dispatch: unsubmitted brief (#956), agent_pane_busy ends the drive (#931)

Both seen live 2026-10-04/05 driving waves. #956: close-out sessions sat idle >2h with the brief in Claude Code's input box (paste placeholder), never submitted; the dispatch returned success. #931: `herdr agent start` refused with `agent_pane_busy` ('target pane is not an available shell') right after `tab create`; the dispatch failed and `fr triage batch drive` exited. Not reproducible on demand (timing-dependent): reproduced by reading the code paths, HerdrRunner.dispatch and _Driver._close_out / dispatch_batch.

<!-- fr:journal kind=hypothesis scope=debug id=8012f1b4a9d0 created=2026-10-06T15:32:52+00:00 -->
### 8012f1b4a9d0 · hypothesis · Runner: dispatch confirms no handoff, so each herdr step races the one before

HerdrRunner.dispatch runs tab create -> agent start -> agent prompt back-to-back. herdr 0.9.1 requires 'agent start --pane' to be at an interactive shell prompt and fails fast (agent_pane_busy) instead of waiting; and 'agent prompt' without --wait returns once text is sent, never checking that the agent left idle. herdr has the confirmation built in: 'agent prompt --wait' fails with agent_prompt_stalled when no working/blocked state follows within 5s. Covers #956 and #931 defect 1.
