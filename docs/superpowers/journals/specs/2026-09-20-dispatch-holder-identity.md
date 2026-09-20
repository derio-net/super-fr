# Journal: 2026-09-20-dispatch-holder-identity

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-09-20T13:30:46 -->
### d1 · decision · advance REFUSES a re-dispatch of a held unit; --redispatch is the escape

Operator chose the strongest of three options for the #499 overlap. With an open dispatch record (dispatched, not returned) the refusal is a lookup, not a heuristic, so `fr run advance` exits non-zero naming the holder and the timestamp, and `--redispatch` is the deliberate escape for a genuinely lost agent. Rationale: the double-dispatch exposure is worst exactly here, because #420 forbids `isolation: "worktree"` for fr-phase-executor, so the usual two-agents-one-tree protection is unavailable by design. #499 is closed by this PR.

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-09-20T13:30:47 -->
### d2 · decision · New verb `fr run claim`, with `resolve --agent` as a late fallback

fr cannot learn a harness agent id at brief time — the agent does not exist when advance prints the brief. So the reported identity enters through a new `fr run claim <run> --step <s> [--item <i>] --agent <id> [--harness <h>]`, which fr-goal section 5 calls immediately after each dispatch; that is the only way `fr run status` can answer who holds a phase WHILE it is held. `fr run resolve --agent` accepts a late id so a skipped claim degrades to partial data rather than none. Operator rejected the resolve-only shape precisely because it answers the question only after it stops mattering.

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-09-20T13:30:47 -->
### d3 · decision · The executor-prose contributing cause is fixed in this PR, without a tripwire

The 11.5-hour poll loop that kept one executor non-terminal is the one part of the incident super-fr controls: the executor ran a long suite in the foreground, the harness auto-promoted it at the 120s Bash timeout, and the executor then left an unbounded `until grep ... sleep 3; done` loop behind at handback. plugins/super-fr/agents/fr-phase-executor.md gains an explicit clause. Operator declined the tripwire variant: there is no hook point for 'an agent left a poll loop running', so a tripwire could only guard the wording, and the repo does not want enforcement theatre.

<!-- fr:journal kind=decision scope=spec id=d4 created=2026-09-20T13:30:47 -->
### d4 · decision · Post-merge Test Plan: live /fr-goal on BOTH Claude Code and OpenCode, plus CI and unit tests

Operator answered option 2 plus CI and unit tests — so both, not either. Unit and CI coverage gates the PR; post-merge, two operator-driven live runs (Claude Code and OpenCode) prove the record is harness-neutral and that --harness is recorded correctly from each. A mocked test cannot show that a dispatch identity was recorded for a real subagent, which is the whole claim (the #486 live-evidence precedent).

<!-- fr:journal kind=discovery scope=spec id=x1 created=2026-09-20T13:31:12 -->
### x1 · discovery · All eight executors are fully recorded on disk; only the LIVE listing differed

Checked ~/.claude/projects/<project>/<session>/subagents/ for the session named in #503. All eight fr-phase-executor dispatches are present: eight `agent-*.meta.json`, eight transcripts, and eight `<id>.output` symlinks in the session's tasks/ directory. Every meta.json is identical in dispatch shape — `spawnDepth: 1`, `requestShape: background`, `requestNonInteractive: true`, `agentType: super-fr:fr-phase-executor` — differing only in `model` (the tier binding). Every transcript ends `stop_reason: end_turn` with a normal handback. So 'six reaped, one persisting' is NOT a difference in what was dispatched or what the agents did: the harness listing is a view over agents that are still non-terminal, and the durable record never lost anything.

<!-- fr:journal kind=discovery scope=spec id=x2 created=2026-09-20T13:31:12 -->
### x2 · discovery · The discriminator is a 120s-timeout-promoted background child that outlived its agent

Five of eight executors had a FOREGROUND Bash command auto-promoted by the harness: 'Command did not complete within its 120s timeout and was moved to the background (ID: <id>)'. None chose to background anything. Two stopped while a promoted child was still live and got the note 'This agent stopped with background work of its own still running' instead of the terminal note. One of those two, ad944a88 (phase 3), settled 16s later when its child finished and re-notified cleanly. add889a (phase 2) never settled: its second promoted child was an `until grep -qE "passed in|failed in|error(s)? in" <other>.output; do sleep 3; done` poll loop whose pattern never matched. It ran 11.5 hours and was reported `killed` at 10:14:40Z. That single live child is why exactly one executor stayed listed and resumable.

<!-- fr:journal kind=discovery scope=spec id=x3 created=2026-09-20T13:31:12 -->
### x3 · discovery · Killing the orphan child did not settle the agent — no terminal notification followed

After `brgvv3xnw` was reported `killed` at 2026-09-20T10:14:40Z, the parent session recorded NO subsequent clean notification for add889a, though every other executor received one within ~20s of finishing. So reaping the background child does not retroactively move the agent to terminal. This matters for the fix's framing: there is no orchestrator-side action that reliably retires such an agent (it is not `running`, so a stop does not apply), which is precisely why the holder record needs its own explicit close.

<!-- fr:journal kind=discovery scope=spec id=x4 created=2026-09-20T13:31:13 -->
### x4 · discovery · #503's and #499's remaining container hypothesis is now fully ruled out

#503 already corrected the 'long-lived docker run from fr isolation exec' hypothesis it had floated on #499, on the grounds that the worktree and container were gone while the agent stayed resumable. The transcripts close the remaining variant: the background work was a plain host shell promoted by the Bash timeout, named in the executor's own tool_result, with no container involved. Neither the devcontainer nor fr isolation is implicated anywhere in this incident.
