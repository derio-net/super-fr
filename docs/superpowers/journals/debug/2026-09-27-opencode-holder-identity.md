# Journal: 2026-09-27-opencode-holder-identity

<!-- fr:journal kind=repro scope=debug id=be650f4db6df created=2026-09-27T09:32:31+00:00 -->
### be650f4db6df · repro · An OpenCode process launched from a Claude Code shell records claude-code and a Claude session as the unit holder

Reproduced from code plus the installed OpenCode 1.18.32 binary. OpenCode sets `OPENCODE=1` and `OPENCODE_PID` at startup; a Claude Code bash tool exports `CLAUDECODE=1`, `CLAUDE_PID` and `CLAUDE_CODE_SESSION_ID`. An OpenCode started from a Claude Code shell inherits all of them. Under that env:
- `detect_harness` (fr/harness/detect.py:37) checks the claude-code markers FIRST and returns `claude-code`;
- `fr run advance` stamps `Attempt.harness` from `detect_harness` and `Attempt.session` from `telemetry.current_session` (run_cmd.py `_open_dispatch`), which reads `CLAUDE_CODE_SESSION_ID` whatever the harness;
- `Attempt.agent_type` is the manifest id (`super-fr:fr-phase-executor`), never the OpenCode tier agent `fr-phase-executor-<tier>` that actually ran;
- `fr run claim` needs `--step`/`--item`, which the OpenCode plugin (the only party that sees the child session id while it holds the unit) does not know (gh#530).

<!-- fr:journal kind=root-cause scope=debug id=17cef48d7094 created=2026-09-27T09:32:34+00:00 -->
### 17cef48d7094 · root-cause · fr names a holder from inherited ambient env, never from the process that holds the unit

One cause, two faces. (1) #537: the holder identity is inferred from environment variables that cross process boundaries; detection gives claude-code a fixed precedence and the session key is Claude-only, so the outer harness is named instead of the one fr runs under. (2) #530: the one source that DOES know the holder, the child session itself (seen by fr-opencode-plugin on its first tool call), has no way to report it, because `fr run claim` requires the unit named. Fix: detection resolves a multi-harness env by the NEAREST ancestor harness pid (`CLAUDE_PID`/`OPENCODE_PID`), with explicit `FR_HARNESS` still winning; the session is recorded only when the detected harness owns that key; and `fr run claim --open-unit` lets the plugin claim the sole open unclaimed attempt from the child, carrying the agent that ran.

<!-- fr:journal kind=finding scope=debug id=f-holder-identity created=2026-09-27T09:56:44+00:00 state=fixed -->
### f-holder-identity · finding [fixed] · Holder identity comes from the nearest harness and from the child itself

Source: fr/harness/detect.py resolves a multi-harness env by the nearest ancestor pid (CLAUDE_PID/OPENCODE_PID), None when neither is placeable; run_cmd `_open_dispatch` records `session` only under claude-code; `fr run claim --open-unit --agent-type` claims the sole open unit dispatched to that agent (or a -<tier> variant) and records the agent that ran; fr-opencode-plugin/src/claim.ts calls it once on a child session`s first tool call, fail-open. Failing tests first (commit "test: pin the OpenCode holder identity"): advance under OpenCode-inside-Claude recorded claude-code (red), claim had no --open-unit (red). Now green, plus plugin claim.test.ts. Live-verified facts: OpenCode 1.18.32 sets OPENCODE/OPENCODE_PID; Claude Code exports CLAUDE_PID; GET /session returns parentID, agent, model. Not live-verified: the plugin claim landing in a real OpenCode session (parity stays partial).

<!-- fr:journal kind=review scope=debug id=88b466741f39 created=2026-09-27T10:04:23+00:00 -->
### 88b466741f39 · review · Independent adversarial review: no defects at the reporting bar

A separate-context code reviewer read the full diff against gh#537/#530. No findings >=80 confidence. Checked and ruled out: nearest-ancestor logic and its fail-closed paths, session gating, _ran_as vs sync-opencode tier naming, the host-side run gate (the plugin runs on the host), the claim_cmd signature change against every existing call site, claim.ts dedupe-before-await and no shell injection (execFile argv). Noted below the bar, carried to the PR as known limits: (1) every child session`s first tool call now spawns one fr process, refused silently for unrelated agents; (2) if two same-tier executors were ever open at once, --open-unit refuses both rather than guess; (3) pid reuse could in theory mis-place a harness; (4) the advance-level tests read the real process table.

<!-- fr:journal kind=finding scope=debug id=f-live-opencode created=2026-09-27T16:43:36+00:00 state=fixed -->
### f-live-opencode · finding [fixed] · Live on OpenCode 1.18.32: both halves observed; the old fr reproduced #537 first

Evidence: docs/acceptance/evidence/2026-09-27-opencode-holder-identity-live.md. Driven through a herdr pane with Claude Code markers exported (CLAUDE_PID = a real ancestor outside OpenCode). The old global fr, which OpenCode`s shell resolved ahead of the branch wrapper, recorded harness claude-code, a borrowed session and the claude-code tier model (the defect, live). The branch fr in the same shell detected opencode; advance through it recorded harness opencode, session None, the OpenCode tier model. The plugin`s child claim landed 3-6 s after dispatch on both attempts, and the child`s own first status read HELD BY agent ses_...; opencode.db agrees on session, agent and model. Parity stays partial: the claim is fail-open against an fr too old for --open-unit.
