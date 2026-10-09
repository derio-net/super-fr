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

<!-- fr:journal kind=decision scope=plan id=p1-operator-targeted-ci created=2026-10-09T23:22:03+00:00 phase=1 -->
### p1-operator-targeted-ci · decision · Operator directed termination and targeted local verification with CI full-suite evidence (phase 1)

Operator explicitly requested treating the nonproductive host-backed full-suite run as hung, identifying the worker/test, terminating the orphan, recording infrastructure failure and continuing through PR delivery with targeted verification. Observed gw0 worker PID 70459 parent 70455 in verified pytest PGID 70446, installer tests TestOrphanedPluginEntryReport.test_does_not_delete_the_orphaned_entry then test_silent_when_only_our_own_plugins_are_registered; rsync child waited in request_wait_answer on host mount I/O. Overlay remained 100% full. Terminated verified PGID with SIGTERM; after five seconds no members remained, no SIGKILL needed; subsequent ps confirmed all pytest/installer children and host wrapper gone. Preserve mounted log as failed/interrupted infrastructure evidence. No further local full suite; bounded targeted checks and existing .fr/ci.yaml ci-ok gate via tests: ci on draft PR.

<!-- fr:journal kind=discovery scope=plan id=p1-grounded-input-contract created=2026-10-09T23:58:14+00:00 phase=1 -->
### p1-grounded-input-contract · discovery · OpenCode input safety is separate from idle status (phase 1)

Redacted capture excerpts now live in tests/fixtures/herdr/opencode with
provenance, original final-border ANSI and the original placeholder ANSI
line. Border lines were checked byte-for-byte against the supplied captures.
The final focused bounded textarea, muted placeholder styling, current
version/footer and single foreground model-selected process establish known
eligibility. Drafts, overlays, blank startup, unknown versions/themes,
active tool/subagent observations and unrecognized layouts fail closed.
Completed task history is not active background work. Plain exit returns to
a shell only when foreground pid matches shell_pid and cwd is observed.
Synthetic refusal/failure tests are labelled; no live Ready walk is claimed.

<!-- fr:journal kind=decision scope=plan id=p1-recovery-state-ownership created=2026-10-09T23:58:14+00:00 phase=1 -->
### p1-recovery-state-ownership · decision · Recovery checkpoints stay local and unfinished work is not redispatched blindly (phase 1)

managed.py is host-local runner state, not a registered repo artifact or a
triage import. Atomic descriptors and OS-backed socket/pane locks support
both restart and the later replacement seam. Non-active checkpoints skip
automatic restart, including uptake-confirmed after a final metadata failure.
Recovery reads the existing branch workspace and durable cursor; unfinished
units require explicit dead-holder reconciliation before redispatch. Delivered
cursors HOLD. Current original-batch handbacks retain batch identity and
precede HOLD only with matching branch head and live conflicting PR; obsolete
handbacks are suppressed. Close-out reuses pickup and its delivery/merge gates.

<!-- fr:journal kind=discovery scope=plan id=p1-candidate-evidence created=2026-10-09T23:58:14+00:00 phase=1 -->
### p1-candidate-evidence · discovery · Installed candidate scenarios and existing Claude regressions pass (phase 1)

Both installed OpenCode scenarios passed after RED missing-helper failures.
The targeted lifecycle/restart/dispatch/driver regression group passed 431
tests. Ruff passed across packages/tests; mypy passed 284 source files.
Acceptance launch/restart rows were transitioned with the acceptance CLI,
named unit/integration refs and their declared scenarios, not record sections.
Published explainers do not describe herdr/restart-idle/post_merge_restart;
their pipeline/CLI wording is unaffected. Runner/operator/skill docs and both
generated skill mirrors were updated. The separate replacement phase and
operator-owned client-live Ready obligation remain untouched.

<!-- fr:journal kind=discovery scope=plan id=p1-full-suite-followup-fixes created=2026-10-09T23:58:14+00:00 phase=1 -->
### p1-full-suite-followup-fixes · discovery · Full-suite-only guards fixed before the final code commit (phase 1)

The first full-suite run exposed missing scenario allowlist entries, a
skill line-budget overrun, the legacy scenario's newly reported unrelated
OpenCode skip, and a direct forge read outside the adapter. c05b8243 fixes
all four: conflict recovery uses hostclient/GhClient, both new scenarios
are pinned, the skill remains within 120 lines with both mirrors regenerated,
and the legacy scenario counts the explicit skip. Relevant guards and
installed scenarios passed (168 passed, 104 skipped); forge/managed tests
then passed 14 tests. Ruff and mypy remained green. The first run also
exhausted storage; its log is preserved as 1089-phase1-suite.log beside
the final log. Pytest cleared this executor's own prior pytest-13 sandbox
via --basetemp before the targeted retry; no unowned storage was removed.

<!-- fr:journal kind=finding scope=plan id=p1-full-suite-storage created=2026-10-09T23:58:14+00:00 phase=1 state=open review_scope=out -->
### p1-full-suite-storage · finding [open] (reviewer: out of scope) · Container overlay storage blocks a green final full suite (phase 1)

Final code commit c05b8243 was clean before the required full exec-bridge
suite. The host-visible final log ends exit=1: 6 failed, 10041 passed,
122 skipped, 1018 errors in 612.71 seconds. Failures/errors show ENOSPC
creating sandbox git objects, rsync files and pytest home directories;
this is not a green gate despite the targeted implementation tests passing.
Five failures explicitly show exhausted storage; the record-review
tree-equals-HEAD assertion also failed during this run but its exact cause
is not established. Do not assume it is fixed: rerun it with adequate
capacity and investigate if it persists.
Before retry, clearing this executor's earlier pytest sandbox recovered
only 2.8 GiB on the 59 GiB container overlay (53 GiB already used). The
full suite's own sandbox growth exhausted it again. No repo-under-test
mutation or unowned-storage cleanup is claimed. Provide more container
overlay capacity or a genuinely external, container-visible test temp
filesystem, then rerun the complete suite on the committed code tree.
P1.T4.S3 remains unticked and phase completion is not claimed. The detached
suite finished; polling was bounded and no process remains running.

<!-- fr:journal kind=discovery scope=plan id=p1-targeted-environment-recovery created=2026-10-09T23:58:14+00:00 phase=1 -->
### p1-targeted-environment-recovery · discovery · Targeted verification recovered outside overlay; full suite remains CI-owned (phase 1)

The host-backed .git/fr/pytest-1089-p1 mount has capacity for isolated temp
repos. The previously unclassified record-review assertion passed there,
first alone and again in the final regression group; no source change to
record review was needed. The mounted full-suite log
1089-phase1-suite-mounted.log is INTERRUPTED infrastructure evidence, not
passing evidence: the orchestrator identified installer gw0/rsync blocked
on host I/O after over an hour and verified termination of its process group
and host wrapper. Per operator decision p1-operator-targeted-ci, no further
local full suite or heavyweight installer suite was run. The ci-ok gate
on the existing draft PR owns full-suite verification; this executor does
not claim it passed and does not wait on CI.

Final bounded checks: 333 passed, 104 skipped in the runner/changed-tripwire/
record-review group; 278 passed in close-out/dispatch/conflict/driver regressions;
3 passed for installed OpenCode scenarios and scenario registration. Ruff
across packages/tests and mypy over 284 source files passed. Host logs:
1089-phase1-targeted-ci-runner-final.log, 1089-phase1-targeted-ci-driver.log,
and 1089-phase1-targeted-ci-candidate-final.log, beside prior suite logs.
TMPDIR/basetemp used only this attempt's isolated host-backed runtime path;
candidate UV_CACHE_DIR also needed relocation because the overlay build
cache was full. No global Docker cache, git objects/refs or unowned temp
were removed. The targeted-ci-8e2a6ab0 runtime was removed after tests.
Cleanup of the older owned recovery-8e2a6ab0 runtime hit the explicit
600-second timeout; that directory remains partially cleaned. The cleanup
process was verified gone; no cleanup, test or polling process remains.
Do not confuse this leftover disposable test data with source changes or
a reason to rerun the local full suite. Logs remain outside both temp roots.

<!-- fr:journal kind=discovery scope=plan id=p1-lock-filesystem-and-entrypoint-fixes created=2026-10-09T23:58:14+00:00 phase=1 -->
### p1-lock-filesystem-and-entrypoint-fixes · discovery · Targeted mounted tests exposed real safety and scenario portability defects (phase 1)

RED tests demonstrated that the virtual host-share filesystem acknowledged
flock while admitting both a nested caller AND an independent process.
The runner now verifies exclusion with an independent bounded OS probe
before yielding ownership; an unenforced or unverifiable lock never permits
input. Independent-process and synthetic unsupported-filesystem tests pin
that contract. Isolated lock-positive fixtures use native advisory-lock
storage (/dev/shm on Linux) and clean it automatically, rather than claiming
the shared filesystem is safe. The installed restart scenario follows the
same native cache convention; descriptors and tests remain sandboxed.

Long candidate prefixes made uv generate a /bin/sh entrypoint trampoline;
reading its shebang as a Python interpreter incorrectly ran the scenario
helper through sh. Both scenarios now share a bounded symlink resolver
selecting the installed tool's sibling Python, not the operator interpreter.
The actual failed candidate runs were followed by green installed scenarios.

<!-- fr:journal kind=finding scope=plan id=p1-opencode-input-grounding-resolved created=2026-10-09T23:58:14+00:00 phase=1 state=fixed resolves=p1-opencode-input-grounding -->
### p1-opencode-input-grounding-resolved · finding [fixed] · resolves p1-opencode-input-grounding: Safe OpenCode input observation needs grounded layout evidence (phase 1)

Captured OpenCode input/process/shell contract is implemented and pinned by named tests; unknown observations fail closed without sending input.

<!-- fr:journal kind=finding scope=plan id=p1-full-suite-storage-resolved created=2026-10-09T23:58:14+00:00 phase=1 state=open resolves=p1-full-suite-storage out_of_scope=true -->
### p1-full-suite-storage-resolved · finding [out-of-scope] · resolves p1-full-suite-storage: Container overlay storage blocks a green final full suite (phase 1)

Infrastructure limitations are not a change-caused failing acceptance.
The isolated record-review assertion is green with adequate temp storage.
Operator decision p1-operator-targeted-ci supersedes the local full-suite
requirement: preserve failed/interrupted local logs, complete bounded
targeted verification and rely on the existing draft PR's ci-ok gate for
full-suite evidence. No local infrastructure false green is claimed.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-10-09T23:58:14+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

Shared stable checkout validation uses fr's existing isolation seam.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-10-09T23:58:14+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

One role-discriminated descriptor and reconstruction path; no initial-goal replay.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-09T23:58:14+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

Shared bounded polling preserves Claude clock/sleep seams and resume behavior.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-09T23:58:14+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

Scenarios reuse the common harness and one explicitly synthetic response helper.
