# Journal: 2026-10-06-triage-batch-adopt

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-06T17:32:20+00:00 input=true -->
### operator-brief · discovery · Operator brief, verbatim

"can you do a sweep of the running sessions on this host and adopt them via Wave Driver?"
Then, after being told the driver cannot adopt hand-started sessions and offered a
`fr triage batch adopt <batch> --tab <herdr-tab-id>` verb built via /fr-goal:
"yes, do that, can we do it with fr-goal-light?"

<!-- fr:journal kind=decision scope=spec id=d1-verb-shape created=2026-10-06T17:32:20+00:00 -->
### d1-verb-shape · decision · New `batch adopt` verb, reusing the --repair recording path

Operator chose a new verb over extending `batch dispatch --repair`. It is kept distinct from the driver's close-out `adopt` action kind.

<!-- fr:journal kind=decision scope=spec id=d2-branch-renamed created=2026-10-06T17:32:20+00:00 -->
### d2-branch-renamed · decision · Adopt renames the session's branch to the batch branch

Operator answer (free text): the adopt option makes sure the branch is renamed to feat/batch-<id> as part of the adoption. Because five of the six target sessions are /fr-goal runs, the rename covers every place fr keys on the branch: local branch and upstream, remote branch (and so its PR), the isolation record, the .fr-isolation marker and a live run cursor (spec R4, §B).

<!-- fr:journal kind=decision scope=spec id=d3-batch-must-exist created=2026-10-06T17:32:20+00:00 -->
### d3-batch-must-exist · decision · The batch must already exist; adopt never creates one

Operator chose create-then-adopt: each verb does one job.

<!-- fr:journal kind=decision scope=spec id=d4-list created=2026-10-06T17:32:20+00:00 -->
### d4-list · decision · `batch adopt --list` is a read-only sweep aid

Operator chose to add it: every herdr tab with its issue refs, writes nothing.

<!-- fr:journal kind=decision scope=spec id=d5-test-plan created=2026-10-06T17:32:20+00:00 -->
### d5-test-plan · decision · Post-merge Test Plan sweeps all six issue-backed sessions

Operator chose the full sweep over a single-session walk.

<!-- fr:journal kind=decision scope=spec id=d6-models created=2026-10-06T17:32:20+00:00 -->
### d6-models · decision · Tier models left unbound

Executors and reviewers inherit the session model; nothing written to models.yaml.

<!-- fr:journal kind=decision scope=spec id=d7-refuse-working-agent created=2026-10-06T17:32:20+00:00 -->
### d7-refuse-working-agent · decision · Adopt refuses a `working` agent

Orchestrator call, not asked: renaming a branch under a working agent races its next push. Operator adopts once the session is idle. Revisit at PR review if wrong.

<!-- fr:journal kind=decision scope=spec id=d8-event-time created=2026-10-06T17:32:20+00:00 -->
### d8-event-time · decision · Event time is clamped back to an existing PR's creation

Orchestrator call from code (batch.of_dispatch drops PRs older than event.at): at = min(now, open PR createdAt), strictly after the last event, else refuse.
