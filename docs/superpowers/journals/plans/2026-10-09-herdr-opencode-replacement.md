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

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-10T00:04:22+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · OpenCode stalled prompt retries Enter without safe-input proof (phase 1)

runner.py:430-442: new OpenCode dispatch inherited a Claude retry assumption contradicted by the live Commands overlay. A stalled submission cannot prove the expected brief remains in a focused textarea.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-10T00:04:22+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Ordinary messaging bypasses exclusive managed restart ownership (phase 1)

runner.py:215-231 and opencode.py:170-189: only conflict handbacks acquired the pane lock. An ordinary message could start work between restart eligibility and exit.

<!-- fr:journal kind=review scope=plan id=phase1-independent-review created=2026-10-10T00:04:22+00:00 phase=1 -->
### phase1-independent-review · review · Independent lifecycle review and verified findings (phase 1)

Separate reviewer inspected spec, phase1 plan/journal and code; 162 targeted checks passed in its context. Two in-scope safety findings independently reproduced. Orchestrator verified both, fixed them and ran 122 targeted managed/runner/restart checks, ruff and mypy green. No live pane mutation or full-suite green is claimed.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-10T00:04:22+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: OpenCode stalled prompt retries Enter without safe-input proof (phase 1)

Submission is harness-aware. OpenCode refuses an unverified Enter retry on stalled uptake, preserving the ambiguous error rather than sending keys into overlays; Claude keeps its existing retry. Regression proves no Enter is sent for the grounded overlay case.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-10T00:04:22+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Ordinary messaging bypasses exclusive managed restart ownership (phase 1)

Every managed message acquires the shared server/pane lock, rechecks checkpoint and live name/kind identity under it, and only then sends. Lock-contention and unresolved-checkpoint tests prove the losing caller sends no prompt.

<!-- fr:journal kind=decision scope=plan id=p2-targeted-ci created=2026-10-10T01:03:02+00:00 phase=2 -->
### p2-targeted-ci · decision · Phase 2 uses bounded local checks and CI full-suite evidence (phase 2)

Operator explicitly forbids another local full suite after phase-1 storage and installer I/O failures. Targeted tests use this attempt's host-mounted sandboxes; the existing draft PR's ci-ok gate owns full verification. No client-live walk is claimed.

<!-- fr:journal kind=discovery scope=plan id=p2-audit-and-repair-contract created=2026-10-10T01:03:02+00:00 phase=2 -->
### p2-audit-and-repair-contract · discovery · Replacement audit is separate from dispatch and runner uptake (phase 2)

Schema-7 events retain the original dispatch; lifecycle selectors ignore audit rows, including dispatch repair and cancellation/collection. Scope then independently verified pane ownership spans descriptor preparation, compare-write attempt, fresh source checks, uptake, batch launch/success and activation. Prepared-before-attempt and committed-before-activation windows have explicit input-free repair. Pre-submission/uncertain target kind/model never certifies uptake. Installed synthetic scenario passed both directions/model-only, startup failure and shell repair.

<!-- fr:journal kind=decision scope=plan id=p2-explainers-unaffected created=2026-10-10T01:03:02+00:00 phase=2 -->
### p2-explainers-unaffected · decision · Published explainers do not describe herdr replacement (phase 2)

As established in the phase-1 handoff, published explainers describe neither herdr lifecycle nor restart-idle; the new operator verb does not change their pipeline or named CLI surfaces. Runner README, control-session operator notes, AGENTS schema/runner notes and canonical fr-triage with both generated mirrors document replacement and the owed client-live walk instead.

<!-- fr:journal kind=finding scope=plan id=p2-live-instructions-not-evidence created=2026-10-10T01:03:02+00:00 phase=2 state=fixed review_scope=in -->
### p2-live-instructions-not-evidence · finding [fixed] (reviewer: in scope) · Printed client-live instructions must not certify a walk (phase 2)

The operator script now exits 3 while the walk is owed; only an interactive explicit verdict backed by a nonempty redacted observation log can report PASS. The instruction-contract test asserts owed/nonpassing output. No client-live walk or Ready completion is claimed.

<!-- fr:journal kind=discovery scope=plan id=p2-verification-scope created=2026-10-10T01:03:02+00:00 phase=2 -->
### p2-verification-scope · discovery · Bounded local checks cover replacement and neighbouring lifecycle contracts (phase 2)

The broad targeted group ran 1228 tests; 1224 passed and four stale schema-number assertions failed, then those expectations were upgraded to schema 7 (future schema 8) without weakening backwards reads. Final affected checks passed 324 tests with 104 intentional skill skips; ruff passed and mypy passed 305 source files. The installed replacement/instruction/scenario-registration group passed three checks. Acceptance check passed 457 rows with existing debt warnings; replacement is CI-wired, live walk remains skipped with issue 1089. CI alone owns the full-suite gate.

<!-- fr:journal kind=discovery scope=plan id=p2-postcommit-ci-evidence created=2026-10-10T01:03:02+00:00 phase=2 -->
### p2-postcommit-ci-evidence · discovery · Final committed tree passes bounded targeted checks; full suite remains CI-owned (phase 2)

Code b6f757de was committed and pushed to the existing draft before final checks; no code changed afterwards.
Host scratch logs: 1089-phase2-targeted-final.log (861 passed, 104 skipped; ruff/format check and mypy over 305 source files passed; exit=0) and 1089-phase2-candidate-fresh-final.log (5 installed launch/restart/replacement/instruction/registration checks passed; exit=0).
The earlier 1089-phase2-candidate-final.log is failed evidence (one import failure, four passed; exit=1): this executor reused its own uv wheel cache after adding ReplacementInspection. A new owned unique cache rebuilt all packages and the installed candidate passed. No shared cache or unowned data was removed.
Logs are in the approved host opencode temp directory, outside the repository and step records. Own isolated host-mounted test/runtime directories remain; no test, installer or polling process is still running. No local full suite was attempted. evidence.tests is ci; the orchestrator owns ci-ok and the operator owns the still-skipped client-live Ready walk. Acceptance transitions were committed with CLI verbs, not record sections.

<!-- fr:journal kind=finding scope=plan id=p2-ci-38010048095-regressions created=2026-10-10T01:03:02+00:00 phase=2 state=fixed review_scope=in -->
### p2-ci-38010048095-regressions · finding [fixed] (reviewer: in scope) · CI exposed omitted skill/schema and triage architecture guards (phase 2)

All four unique CI failures were reproduced RED locally with their exact test nodes, without a full-suite attempt. Canonical skill compression had removed the literal batch cancel command; it now spells out dispatch/merge/cancel and both mirrors were regenerated, retaining the 120-line limit.
The skill example test now checks the actual current writer schema and matching documentation, parses real batches and rejects authored events. A separate historical schema-3 example test verifies unchanged batch/issue compatibility. The CLI refusal fixture uses a schema above every supported reader stamp and still asserts exit 2, judgements.yaml and the unsupported schema diagnostic.
The real architectural defect was subprocess enforcement probing inside triage/operation_lock.py. The unchanged forge/subprocess guard now passes because verified nonblocking flock ownership and its bounded independent Python probe live in fr/file_lock.py, a shared infrastructure helper with no triage or forge imports. The scope adapter only derives its key/cache path and translates FileLockError. Native independent-process scope exclusion, nested ownership and unenforced-filesystem refusal remain tested; no guard allowlist was weakened. Acceptance CLI added the two new infrastructure test refs to the existing replacement row.

<!-- fr:journal kind=discovery scope=plan id=p2-ci-fixes-red-green created=2026-10-10T01:03:02+00:00 phase=2 -->
### p2-ci-fixes-red-green · discovery · CI regression follow-up is bounded and leaves full verification to ci-ok (phase 2)

All four exact CI failures reproduced locally; the new shared-helper tests also failed RED before implementation. After fixes, affected skill/CLI/collector/lock/replacement/schema/managed/mirror checks passed 350 tests with 104 intentional skips. No local full suite, second worktree, cursor resolve, Ready transition or CI wait was attempted; evidence.tests remains ci for the existing draft PR 1115.

<!-- fr:journal kind=discovery scope=plan id=p2-ci-fixes-postcommit-evidence created=2026-10-10T01:03:02+00:00 phase=2 -->
### p2-ci-fixes-postcommit-evidence · discovery · Final CI-fix code tree passes targeted regressions and unchanged architecture guards (phase 2)

Code 40f5f300 was committed and pushed to the same draft before final checks; no code changed afterwards. Host log 1089-phase2-ci-fixes-final.log in the approved opencode temp directory ends exit=0: 369 passed, 104 intentional skips; ruff and format checks passed, mypy passed 306 source files. Coverage includes all four reported regression surfaces (the skill schema test now names current-schema semantics), separate schema-3 compatibility, native independent-process scope exclusion, nested/unverified shared locks, replacement checkpoints/repair, both mirror tripwires, skill line budgets, import direction and forge/subprocess guards. The original collector guard and its forbidden-import non-vacuity cases are unchanged. No local full suite was run, no subprocess/polling job remains, and the ci-ok full gate remains orchestrator-owned with evidence.tests ci.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-10-10T01:03:02+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

Reused reviewed restart prompt/background classifiers, shell observation, bounded polling and shared agent-start seam; ownership/checkpoints live in one operation object. Further rewriting phase-1 retry paths would add risk without reducing a second decision owner.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-10-10T01:03:02+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

Installed scenarios share the existing candidate-interpreter helper and captured screens. The replacement helper deliberately owns separate labelled synthetic transaction state; a broader fake-client abstraction would obscure its failure/repair evidence.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-10T01:24:16+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · Validate target OpenCode model before source exit (phase 2)

CLI and replacement prepare accepted any nonempty model; malformed target requests could exit the source before startup rejected the model. New path lacked dispatch provider/model validation.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-10T01:24:16+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · Failed descriptor activation can conceal unfinished repair (phase 2)

CLI saved reconciled failure before restoring source/aborted descriptor. A failed descriptor write followed by another repair returned already reconciled, leaving pending state.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-10-10T01:24:16+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · Preview used mutating state loader (phase 2)

State loading performed synchronization, exclusion updates or legacy import before ownership/no-write guards, contradicting write-free preview.

<!-- fr:journal kind=review scope=plan id=phase2-independent-review created=2026-10-10T01:24:16+00:00 phase=2 -->
### phase2-independent-review · review · Independent replacement review and correction verification (phase 2)

Separate read-only reviewer checked spec, phase2 plan/journal, source and tests. Three in-scope findings verified, then independently checked corrected code at 6c0fd51d and confirmed all three fixed with no new actionable finding. Implementer ran 441 targeted checks and installed replacement scenario, ruff/format/mypy green. CI owns full-suite proof; operator client-live remains owed.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-10T01:24:16+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: Validate target OpenCode model before source exit (phase 2)

Shared launch validation in fr_dispatch/launch.py is enforced by CLI before operation construction and runner prepare independently. Preview/act and direct runner regressions assert no descriptor/attempt/source input for malformed target models.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-10T01:24:16+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: Failed descriptor activation can conceal unfinished repair (phase 2)

Repair rechecks both stores and retries unfinished failure activation without appending another audit event, launching or prompting. Already-restored source is validated idempotently; injected descriptor-write failure/retry tests preserve audit bytes and forbid replay.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-10-10T01:24:16+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: Preview used mutating state loader (phase 2)

Preview resolves/loads state read-only with sync/preparation disabled; act acquires scope ownership before preparation/fetch and performs final push before unlocking. Tests cover unchanged files, synchronization metadata, exclusions, legacy state and lock-loser behavior.

<!-- fr:journal kind=finding scope=plan id=p2-client-live-tty created=2026-10-10T01:35:34+00:00 phase=2 state=open review_scope=in -->
### p2-client-live-tty · finding [open] (reviewer: in scope) · Documented client-live walk could not invoke its verdict flow (phase 2)

Generated operator walk invoked scenario without arguments, making default exit3 an impossible success path; captured stdout/stderr also hid verdict prompts. Corrected no-argument interactive invocation uses /dev/tty, requires actual observations and evidence, preserves noninteractive exit3. Targeted PTY checks passed, actual operator-authorized walk now being performed.

<!-- fr:journal kind=finding scope=plan id=p2-client-live-tty-resolved created=2026-10-10T01:36:09+00:00 state=fixed resolves=p2-client-live-tty -->
### p2-client-live-tty-resolved · finding [fixed] · resolves p2-client-live-tty: Documented client-live walk could not invoke its verdict flow

Fixed at 045ab9f0 with PTY and negative-evidence regressions; actual observed client-live verdict is separate from this code fix.

<!-- fr:journal kind=finding scope=plan id=live-r1 created=2026-10-10T04:30:18+00:00 phase=2 state=open review_scope=out -->
### live-r1 · finding [open] (reviewer: out of scope) · Native unsupported-provider request can display a fallback UI model (phase 2)

Observed real OpenCode retaining syntactically valid missing-provider request in process argv while displaying another default model. Independent reviewer verified current spec/model contract checks native requested argv, not provider availability/effective selected UI model. This native limitation predates changes; intentional bad-model failure test did not pass. Keep explicit in PR and follow-up list.

<!-- fr:journal kind=finding scope=plan id=live-r1-resolved created=2026-10-10T04:30:21+00:00 state=open resolves=live-r1 out_of_scope=true -->
### live-r1-resolved · finding [out-of-scope] · resolves live-r1: Native unsupported-provider request can display a fallback UI model

Pre-existing native provider resolution/fallback outside the explicit process-argv verification boundary, independently reviewed; preserve evidence, do not claim fixed.

<!-- fr:journal kind=finding scope=plan id=live-r2 created=2026-10-10T04:30:48+00:00 phase=2 state=open review_scope=in -->
### live-r2 · finding [open] (reviewer: in scope) · Draft delivery must disclose incomplete live evidence (phase 2)

Independent final review found draft provisional wording insufficient: positive conflict/closeout prerequisites and intended bad-model failure case are not all-live proven. Record observed subset, native model boundary and unchecked client-live/Ready requirement; do not certify a PASS.

<!-- fr:journal kind=finding scope=plan id=live-r2-resolved created=2026-10-10T04:30:52+00:00 state=fixed resolves=live-r2 -->
### live-r2-resolved · finding [fixed] · resolves live-r2: Draft delivery must disclose incomplete live evidence

Acceptance notes now enumerate actual observed subset, unproven cases, native model limitation, cleanup and no-PASS verdict. Delivery body includes the same disclosure and operator checklist stays unchecked; this resolution closes disclosure, not the live walk.

<!-- fr:journal kind=finding scope=plan id=live-r1-resolved-2 created=2026-10-10T04:39:55+00:00 state=open resolves=live-r1 tracked_by=https://github.com/derio-net/super-fr/issues/1116 -->
### live-r1-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1116] · resolves live-r1: Native unsupported-provider request can display a fallback UI model

External native effective-model boundary is explicitly tracked in #1116; investigate supported-model preflight/effective-model observation in that follow-up, no false fixed claim.
