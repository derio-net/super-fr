# Journal: 2026-10-09-herdr-opencode-replacement

<!-- fr:journal kind=decision scope=plan id=implementation-structure created=2026-10-09T20:34:09+00:00 -->
### implementation-structure · decision · Two independently reviewable asks

Phase 1 OpenCode lifecycle/restart; phase 2 audited replacement CLI. Spec journal records ask split and both hard-tier reasons. Operator client-live verification is a Ready obligation, not an implementation phase.

<!-- fr:journal kind=discovery scope=plan id=p1-resume-baseline created=2026-10-09T20:57:08+00:00 phase=1 -->
### p1-resume-baseline · discovery · Resumed executor found no implementation changes (phase 1)

The shared feat/1089 worktree was clean on resume; no phase record existed.
The exec-bridge smoke command passed: tests/unit/test_fr_herdr_runner.py,
70 passed. Container dependency setup succeeded. No source, acceptance,
scenario or release-fragment changes have been made.

<!-- fr:journal kind=finding scope=plan id=p1-opencode-input-grounding created=2026-10-09T20:57:08+00:00 phase=1 state=open review_scope=in -->
### p1-opencode-input-grounding · finding [open] (reviewer: in scope) · Safe OpenCode input observation needs grounded layout evidence (phase 1)

R10 and spec lines 162–168 require harness-specific observation grounded
in actual OpenCode surfaces, including unsent input and background work;
P1.T3.S2 must not invent a safe input layout. The supplied handoff gives
the phase split but no OpenCode idle/draft/background/dialog observation
contract. Existing tests/fixtures/herdr/restart captures describe Claude,
not OpenCode. Read-only installed CLI help confirms OpenCode --model
provider/model and herdr's ready-start semantics, but does not expose
a structured draft/background-work safety observation.

Read-only inspection of the inherited caller pane found OpenCode 1.18.35
working while the orchestrator awaited this executor. That is not an
idle safety capture and cannot establish the empty-input, draft,
background-work or dialog distinctions. No keys were sent and no agent
was started. This leaf cannot dispatch a disposable observation agent or
interrupt the caller to obtain those states.

Supply a curated grounding handoff: real redacted captures of the
supported idle/draft/background/dialog layouts (with version), or a
reviewed authoritative source/API observation contract distinguishing
those states and the graceful-exit behavior. Synthetic tests can then
be explicitly labelled and unknown layouts skipped. This is separate
from the operator-owned client-live Ready obligation: no full live
acceptance walk is requested here. Remaining steps are unticked, and
neither the phase nor the orchestrator cursor has been resolved.

<!-- fr:journal kind=discovery scope=plan id=p1-opencode-live-grounding created=2026-10-09T21:06:45+00:00 phase=1 -->
### p1-opencode-live-grounding · discovery · Operator-authorized disposable OpenCode grounding captured (phase 1)

Operator answered yes to a narrow disposable-session capture. OpenCode 1.18.35/herdr 0.9.0 protocol 22 captured home/session empty prompt, unsent draft, Commands overlay, active shell/subagent, completed task history and plain exit back to shell. Redacted artifacts and capture provenance are in approved host scratch, 1089-capture-provenance.md. Scratch workspace closed. Implementer must copy redacted evidence through edit tools and close p1-opencode-input-grounding once its safe observer is implemented; full client-live walk remains owed.
