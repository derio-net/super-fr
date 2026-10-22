<!-- fr:journal-schema=3 -->
# Journal: 2026-10-14-closed-session-batch-recovery

<!-- fr:journal kind=decision scope=plan id=one-coherent-recovery-phase created=2026-10-14T18:03:10+00:00 -->
### one-coherent-recovery-phase · decision · One independently reviewable recovery ask

One hard-tier agentic phase implements explicit absent-source recovery, durable allocation/repair and HOLD as a coherent transaction, then fake-backed scenarios/docs and committed-tree suite. Actual client walk is operator-owned post-merge Tester verification. #1216 and real batch takeover are excluded.

<!-- fr:journal kind=discovery scope=plan id=recovery-python314-ready created=2026-10-14T20:13:05+00:00 phase=1 -->
### recovery-python314-ready · discovery · Supported Python 3.14 repairs the isolated test environment (phase 1)

uv run --python 3.14 inside the existing isolation installed CPython 3.14.8
and the workspace dependencies successfully. The existing replacement CLI
tests passed (37 passed). No isolation marker/config/version was changed.
Real executor session: ses_ec4699655ffeL3SP68hI3rHTR8; model openai/gpt-6.1-sol.

<!-- fr:journal kind=finding scope=plan id=recovery-pane-roster-capture-required created=2026-10-14T20:13:05+00:00 phase=1 state=open review_scope=in -->
### recovery-pane-roster-capture-required · finding [open] (reviewer: in scope) · Missing captured pane discovery contract blocks safe recovery (phase 1)

R3 and R7 require proving that the recorded pane has no unrelated occupant
and discovering an allocated shell pane after a lost allocation response.
Existing captured tab-list-all.json exposes tab_id/label/pane_count but no
pane ids; agent-list.json only observes agents, not newly allocated shell
panes. The fixture README says tab-create.json is constructed rather than
captured and references pane-list/tab-get observations not supplied as
fixtures. No pane discovery wire format may be invented alongside its parser.

Attempting a read-only CLI availability check through the mandated bridge,
fr isolation exec --branch feat/closed-session-batch-recovery -- herdr --help,
failed: OCI runtime exec failed: exec failed: unable to start container
process: exec: "herdr": executable file not found in $PATH: unknown.

Please supply redacted real captures of the complete pane roster and the
labelled tab-to-pane discovery response (including an allocated shell), or
provide an authorized read-only capture route accessible through isolation.
This is not a request to run the live client walk or take over any real batch.
Implementation stopped rather than constructing fixtures or degrading isolation.
Provisional source/schema/API edits and red tests were removed so no incomplete
--recover surface remains. No step is ticked; all six tasks remain owed.
No acceptance status, real batch, driver, pane, or PR state was changed.

<!-- fr:journal kind=discovery scope=plan id=recovery-transaction-and-explainers created=2026-10-14T20:13:05+00:00 phase=1 -->
### recovery-transaction-and-explainers · discovery · Recovery is an optional replacement mode, with one submission primitive and HOLD policy (phase 1)

Recovery shares replacement's target launch/single submission checkpoint primitive,
not runner.dispatch. Strict global pane/tab/agent joins include allocated shells;
source-keyed intent precedes allocation and repairs never replay inputs. Scope,
local driver admission and both pane locks span the durable transaction. Schema 12
writes recovery ownership/session metadata while reading judgements 1–12.
Successful effective ownership is folded only after the latest original dispatch.
Managed HOLD reconstruction precedes conflict/delivered/unfinished continuation.
Fake-backed candidate tests are not a client-live pass; the disposable live walk
remains owed post-merge at Tester. No real org batches or loops were touched.
Published docs/explainers/*.md contain no batch replace/herdr/closed-session
surface; their generic goal/review explanations are unchanged. No explainer
regeneration is needed. Operator guide, package README, AGENTS and canonical
fr-triage guidance were updated; both mirrors regenerated. #1216 stays out of scope.

<!-- fr:journal kind=discovery scope=plan id=recovery-quality-gates created=2026-10-14T20:13:05+00:00 phase=1 -->
### recovery-quality-gates · discovery · Targeted committed-tree preparation gates pass (phase 1)

Ruff format/check passed. Mypy passed for fr, fr-dispatch and fr-herdr (322
source files). Recovery/replacement/managed/restart/import tests passed (254).
Installed scenarios, schema neighbours and both mirror/tool-neutrality guards
passed together (674). Acceptance check passed (535 rows); the phase's status
transitions and named test evidence are carried in this record for the parent
resolve, not hand-edited into the matrix. Original schema-11 writer/future-schema
expectations were updated coherently to writer 12 and unsupported 13.

<!-- fr:journal kind=discovery scope=plan id=recovery-full-suite-environment-and-guidance created=2026-10-14T20:13:05+00:00 phase=1 -->
### recovery-full-suite-environment-and-guidance · discovery · Full-suite resource bound and canonical skill guards (phase 1)

The first full-suite foreground bridge exceeded 600 seconds and lost workers;
its orphaned container process group was explicitly terminated and checked.
Full evidence therefore uses a detached, bounded-wait host coordinator command
and PYTEST_XDIST_AUTO_NUM_WORKERS=4 while retaining pytest -q --no-cov -n auto.
No isolation marker/config/version was changed. The first completed full run
reported 12907 passed, 125 skipped and three in-scope canonical skill failures:
its example still stamped 11 and the new separate paragraph exceeded the
120-line budget. The example now stamps 12; guidance is consolidated within
the original line budget, with both mirrors regenerated. Final evidence is a
fresh full run on the subsequent committed-clean code tree, not that red run.

<!-- fr:journal kind=discovery scope=plan id=recovery-final-suite created=2026-10-14T20:13:05+00:00 phase=1 -->
### recovery-final-suite · discovery · Full suite passes on the final committed-clean implementation tree (phase 1)

Final code commit 84eeab81 was clean before the coordinator/isolation full
pytest -q --no-cov -n auto run (Python 3.14, bounded to four auto workers).
Result: 12910 passed, 125 skipped, 9 warnings in 1428.80 seconds; exit=0.
The host-visible raw log is named in evidence.tests. Only this step record
was edited after the suite; no code was touched. All detached suite/polling
processes finished; the earlier timed-out process groups were terminated.
A targeted skill check also printed its pass summary but hung at process
shutdown and was explicitly terminated; it is not used as passing evidence.
The final full suite is the passing authority. Parent cursor remains unresolved;
no PR/push/live client walk or real batch/driver action was performed.

<!-- fr:journal kind=discovery scope=plan id=recovery-acceptance-record-emissions-corrected created=2026-10-14T20:13:05+00:00 phase=1 -->
### recovery-acceptance-record-emissions-corrected · discovery · Acceptance transitions applied separately through their supported CLI (phase 1)

Parent resolve correctly refused the disallowed acceptance section without
applying anything: implement-phase emits only journal:plan and plan:ticks.
The three automated recovery rows were moved to ci and the actual-client row
to walk-owed using fr acceptance set-status, with named unit/int refs and
regenerated reports. The live strategy and concrete scenario remain intact.
Evidence uses repo:path#test_name anchors, not pytest's path::test_name
invocation syntax. Acceptance check passes with the corrected anchors.
The rejected section is removed from this record; no cursor was resolved.
Changes are acceptance/report and record metadata only, so the existing
passing full-suite log still covers the unchanged implementation code tree.

<!-- fr:journal kind=finding scope=plan id=recovery-pane-roster-capture-required-resolved created=2026-10-14T20:13:05+00:00 phase=1 state=fixed resolves=recovery-pane-roster-capture-required -->
### recovery-pane-roster-capture-required-resolved · finding [fixed] · resolves recovery-pane-roster-capture-required: Missing captured pane discovery contract blocks safe recovery (phase 1)

Parent supplied read-only real captured global pane/tab rosters and shell observations. Discovery uses the pane-list/tab-list join, never an invented tab-get pane field. Container tests need no real herdr installation.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-10-14T20:13:05+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

Verification-only task; no new implementation to refactor. Shared roster, submission and HOLD policies were factored in tasks 1–5.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-14T20:43:26+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Pending recovery activation permits managed restart (phase 1)

In scope: recovery.py:413-425 saves the target descriptor active before final intent save. Failure leaves descriptor active while pending recovery remains; opencode.py restart eligibility checks only descriptor. Add unresolved/unreadable recovery-intent admission guard and regression that no restart input occurs after activation-write failure.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-14T20:43:26+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Recovery accepts cursors that fr cannot read (phase 1)

In scope: managed.py:268-297 validates only selected fields and accepts missing workflow/started or future schema. Installed fixture triage-closed-recovery.py:125-128 uses such a cursor. Validate with supported read-only parse_run_state, without migration/writes; use valid fixtures and test zero allocation on malformed/future schemas.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-14T20:43:26+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · Malformed agent names can certify source absence (phase 1)

In scope: recovery.py:42-45 validates pane/tab identities but not optional name used by absent/discovery comparisons. Reject present non-string names as unknown observation, preserve valid unnamed rows, and test preview/act/repair perform no input/allocation.

<!-- fr:journal kind=review scope=plan id=phase1-review created=2026-10-14T20:43:26+00:00 phase=1 -->
### phase1-review · review · Independent phase-1 code review (phase 1)

Reviewed origin/main...HEAD against spec, phase plan and journal. Initial review raised three in-scope findings; re-review raised one regression, all four now independently verified fixed. Final review of 04b8acab confirms usable run/cursor/steps admission after supported schema parsing, unknown cursor-step refusal, and finished final-step compatibility. Pending-intent restart admission and malformed-name refusal remain present. No new directly introduced defects. Executor suite claims were not used as substitute for review. Actual-client walk remains operator-owned post-merge Tester evidence. #1216 excluded.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-14T20:43:26+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · Parser substitution removed nonempty recovery cursor guards (phase 1)

In scope: cc7386fd removed explicit usable run/cursor/steps checks while parse_run_state permits blank strings and empty steps. Restore recovery-specific usability guards after supported parsing, with preview/act zero-allocation regressions and finished-final-step compatibility.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-14T20:43:26+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Pending recovery activation permits managed restart (phase 1)

cc7386fd adds managed.restart_admission checking source/item pending or unreadable intent before restart input; startup readiness bypass is explicit. Reviewer verified managed.py:303–319 and regression cases for failed activation and unreadable intent.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-14T20:43:26+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Recovery accepts cursors that fr cannot read (phase 1)

cc7386fd uses parse_run_state without migration/writes and valid RunState installed fixtures. Missing fields, invalid metadata and future-schema cursor tests refuse allocation and preserve bytes; independently verified.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-14T20:43:26+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: Malformed agent names can certify source absence (phase 1)

cc7386fd rejects present non-string agent names before absence/discovery, keeps legitimate unnamed rows, and tests preview/act/repair without effects; independently verified.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-14T20:43:26+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: Parser substitution removed nonempty recovery cursor guards (phase 1)

04b8acab adds validate_run_id plus nonblank/unpadded cursor, nonempty steps and cursor membership checks after parse_run_state; tests reject invalid identities and retain finished deliver cursor HOLD. Reviewer independently verified managed.py:282–292 and tests:594–646.
