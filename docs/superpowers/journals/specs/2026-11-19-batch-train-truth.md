<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-batch-train-truth

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-19T10:51:15+00:00 input=true -->
### brief · discovery · Operator brief — batch train-truth (as dispatched)

/fr-goal batch train-truth

Batch `train-truth` of derio-net/super-fr: 6 issues, delivered as ONE pull request.
Members: #1491 (a transient refused state-ref push ends the drive loop, and nothing restarts the driver),
#1492 (red CI on an unapproved draft batch PR is never handed back), #1493 (merge conflicts are found only
when a PR heads the train, after it was approved), #1540 (_fetched_reader lets GitError escape and does not
record the failed fetch), #1541 (the swap_issue_labels retry assumes gh resolves all labels before mutating),
#1543 (batch cancel of a never-dispatched batch still needs --checkout).
Why together: all in the driver loop (batch_drive.py, triage_batch_cmd.py); #1492 and #1493 share the draft
non-member filter.
Delivery rules: branch feat/batch-train-truth; a draft PR as soon as the spec is committed whose body closes
each member with its own `Closes derio-net/super-fr#<n>` line; no member issue as a phase tracking_issue;
never add the approved-fr label.
Mid-brainstorm operator ask: "btw, I would like to watch the driver's actions. Is there a way to make this
event log easily visible?"

<!-- fr:journal kind=decision scope=spec id=d-resident-orchestrator created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-resident-orchestrator · decision · The driver is owned by a resident orchestrator session

Operator (round 1 clarification): the Wave Driver will eventually be manned by a resident orchestrator agent,
like the gates. The driver runs beside a persistent agent session that is responsible for it; the agent must
always know the driver is running; the driver keeps itself alive (itself or via a supervisor) without
consuming tokens wherever it breaks down; if the agent session is killed, the driver and its supervisor go
with it.

<!-- fr:journal kind=decision scope=spec id=d-1491-shape created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-1491-shape · decision · #1491: a session-bound supervisor (drive --supervise), not detached

Operator chose option 1 (round 1 Q1). The supervisor restarts the driver after a crash with bounded backoff and a crash-loop limit, stays in its caller's session, and dies with it; the background-exit notice is the agent's one wake.

<!-- fr:journal kind=decision scope=spec id=d-red-delivered created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-red-delivered · decision · #1492/#1493: the existing session-status rule decides when a draft is handed back

Operator chose the recommended option (round 1 Q2). Only an idle session is handed a red or conflicting draft; a working one is waited on; absent/done is a Needs you now entry. Caps count draft and ready hand-backs together.

<!-- fr:journal kind=decision scope=spec id=d-1541 created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-1541 · decision · #1541: make the retry assumption-free (docstring + unit test), no live walk

Operator chose the recommended option (round 1 Q3).

<!-- fr:journal kind=decision scope=spec id=d-1543 created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-1543 · decision · #1543: a never-dispatched cancel has no tracking gate and still releases claims

Operator chose the recommended option (round 1 Q4).

<!-- fr:journal kind=decision scope=spec id=d-verify created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-verify · decision · Verification: CI tests with fakes, strategy none, gate developer, no Test Plan

Operator chose the recommended option (round 1 Q5).

<!-- fr:journal kind=decision scope=spec id=d-root-fix created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-root-fix · decision · Fix the crash class at its root with a typed pass boundary

Operator chose the recommended option (round 2 Q1). Inside a pass, failures are a DriverRefusal (operator must act) or transient (reported once, capped exponential backoff, next pass re-reads); 10 failed passes in a row stop as a refusal; a tripwire forbids _fail/typer.Exit in the pass.

<!-- fr:journal kind=decision scope=spec id=d-refusal-loop created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-refusal-loop · decision · On a refusal the driver exits (the agent wakes), tied to a self-improvement loop

Operator (round 2 Q2): "1. but only if this is tied to a self-improvement loop, in order to driver the real
refusals to zero". Interpreted as R8-R9: every refusal, transient failure and crash is counted per stable
cause in a durable ledger, and `fr triage batch drive failures --file --yes` turns each recurring cause into
a tracked forge issue (commented as it recurs, re-filed if it recurs after closing), named by every refusal's
exit line and board need. Interpretation recorded for the operator to correct at PR review.

<!-- fr:journal kind=decision scope=spec id=d-activity-log created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-activity-log · decision · The driver's actions are visible as a persistent activity log (drive.log, drive log -f, board Activity panel)

Operator's mid-brainstorm ask ("I would like to watch the driver's actions"), folded in as R22-R23 before the brainstorm resolved; the operator may veto it at PR review.

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-19T10:51:15+00:00 lens=errors step=brainstorm -->
### lens-errors-1 · lens · The pass boundary reclassifies every failure path of the driver; each must land in the right class

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-19T10:51:15+00:00 lens=tests step=brainstorm -->
### lens-tests-1 · lens · Process-lifetime and backoff behaviour is easy to test vacuously (sleeps, signals, orphaned children)

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-11-19T10:51:17+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: operator-request. the operator's round-1 answer on #1491 asked a question back (why does the driver keep crashing, is there a design defect); answering it from the code (31 _fail sites inside the pass, one ForgeReadError boundary) needed the root-fix and refusal-handling decisions
