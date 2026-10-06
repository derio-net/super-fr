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

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-06-triage-batch-adopt-p1 created=2026-10-06T17:34:17+00:00 -->
### tier-2026-10-06-triage-batch-adopt-p1 · decision · tier hard: the phase changes a branch-keyed gate path (isolation marker, record, run cursor) that the edit gate and close-out rely on

<!-- fr:journal kind=review scope=spec id=spr-r1 created=2026-10-06T18:02:30+00:00 -->
### spr-r1 · review · independent spec+plan review: 12 findings (spr-f1..spr-f12)

Findings raised: spr-f1..spr-f12, all review_scope in, all fixed in the spec and plan in this step. Reviewer verified ~30 file:line references (branch matching, of_dispatch, the three branch recomputes, _record_missing, _forge_writes, isolation state, herdr agent_name/tab rename, protocols, gitseam, matrix rows).

<!-- fr:journal kind=finding scope=spec id=spr-f1 created=2026-10-06T18:02:30+00:00 state=open review_scope=in -->
### spr-f1 · finding [open] (reviewer: in scope) · Branch rename misses the session index files under ~/.cache/fr/sessions

target: spec
Branch rename misses the session index files under ~/.cache/fr/sessions

<!-- fr:journal kind=finding scope=spec id=spr-f2 created=2026-10-06T18:02:30+00:00 state=open review_scope=in -->
### spr-f2 · finding [open] (reviewer: in scope) · GitHub branch-rename behaviour unverified before irreversible writes

target: spec
GitHub branch-rename behaviour unverified before irreversible writes

<!-- fr:journal kind=finding scope=spec id=spr-f3 created=2026-10-06T18:02:30+00:00 state=open review_scope=in -->
### spr-f3 · finding [open] (reviewer: in scope) · `adopted` field forces a judgements schema bump for nothing

target: spec
`adopted` field forces a judgements schema bump for nothing

<!-- fr:journal kind=finding scope=spec id=spr-f4 created=2026-10-06T18:02:30+00:00 state=open review_scope=in -->
### spr-f4 · finding [open] (reviewer: in scope) · No command can finish a failed adopt

target: spec
No command can finish a failed adopt

<!-- fr:journal kind=finding scope=spec id=spr-f5 created=2026-10-06T18:02:30+00:00 state=open review_scope=in -->
### spr-f5 · finding [open] (reviewer: in scope) · Reserved version not reserved, not told to the session

target: spec
Reserved version not reserved, not told to the session

<!-- fr:journal kind=finding scope=spec id=spr-f6 created=2026-10-06T18:02:30+00:00 state=open review_scope=in -->
### spr-f6 · finding [open] (reviewer: in scope) · git outside gitseam contradicts §A

target: spec
git outside gitseam contradicts §A

<!-- fr:journal kind=finding scope=spec id=spr-f7 created=2026-10-06T18:02:30+00:00 state=open review_scope=in -->
### spr-f7 · finding [open] (reviewer: in scope) · `herdr agent rename` on a hand-started agent never observed

target: plan
`herdr agent rename` on a hand-started agent never observed

<!-- fr:journal kind=finding scope=spec id=spr-f8 created=2026-10-06T18:02:30+00:00 state=open review_scope=in -->
### spr-f8 · finding [open] (reviewer: in scope) · Strict clamp can drop the PR without refusing

target: spec
Strict clamp can drop the PR without refusing

<!-- fr:journal kind=finding scope=spec id=spr-f9 created=2026-10-06T18:02:30+00:00 state=open review_scope=in -->
### spr-f9 · finding [open] (reviewer: in scope) · adopt_event_time has no RED test; R7 refusal untested

target: plan
adopt_event_time has no RED test; R7 refusal untested

<!-- fr:journal kind=finding scope=spec id=spr-f10 created=2026-10-06T18:02:30+00:00 state=open review_scope=in -->
### spr-f10 · finding [open] (reviewer: in scope) · Several R9 refusals untested

target: plan
Several R9 refusals untested

<!-- fr:journal kind=finding scope=spec id=spr-f11 created=2026-10-06T18:02:30+00:00 state=open review_scope=in -->
### spr-f11 · finding [open] (reviewer: in scope) · Plan names wrong file paths for fakes and tests

target: plan
Plan names wrong file paths for fakes and tests

<!-- fr:journal kind=finding scope=spec id=spr-f12 created=2026-10-06T18:02:30+00:00 state=open review_scope=in -->
### spr-f12 · finding [open] (reviewer: in scope) · `refs` on the runner-neutral AdoptTarget

target: plan
`refs` on the runner-neutral AdoptTarget

<!-- fr:journal kind=decision scope=spec id=d9-pr-supersede created=2026-10-06T18:02:30+00:00 -->
### d9-pr-supersede · decision · Always rename; supersede an open PR with a new one

GitHub closes a PR whose head branch is renamed. Operator chose, asked after the review: rename and reopen a PR (old title, body, draft state; old PR commented and closed) over keeping the branch or refusing.

<!-- fr:journal kind=finding scope=spec id=spr-f1-resolved created=2026-10-06T18:02:30+00:00 state=fixed resolves=spr-f1 -->
### spr-f1-resolved · finding [fixed] · resolves spr-f1: Branch rename misses the session index files under ~/.cache/fr/sessions

Fixed: R4 and §B now rewrite `branch` in every bound session's index; P1.T2.S1 asserts it.

<!-- fr:journal kind=finding scope=spec id=spr-f2-resolved created=2026-10-06T18:02:30+00:00 state=fixed resolves=spr-f2 -->
### spr-f2-resolved · finding [fixed] · resolves spr-f2: GitHub branch-rename behaviour unverified before irreversible writes

Fixed: GitHub docs confirm renaming a PR's head closes the PR. Operator decision d9: always rename, and reopen. §C no longer uses the rename API: it publishes the batch branch, opens a new PR (title, body, draft), comments and closes the old one, deletes the old branch. The upstream is set by `git push -u`, so there is no async rename or stale origin/<new>.

<!-- fr:journal kind=finding scope=spec id=spr-f3-resolved created=2026-10-06T18:02:30+00:00 state=fixed resolves=spr-f3 -->
### spr-f3-resolved · finding [fixed] · resolves spr-f3: `adopted` field forces a judgements schema bump for nothing

Fixed: the field is dropped (§F). A plain DispatchEvent, no schema change.

<!-- fr:journal kind=finding scope=spec id=spr-f4-resolved created=2026-10-06T18:02:30+00:00 state=fixed resolves=spr-f4 -->
### spr-f4-resolved · finding [fixed] · resolves spr-f4: No command can finish a failed adopt

Fixed: new R10, adopt is resumable; each §A.7 step is skipped when already done; P1.T5.S1 injects a failure at each step and re-runs.

<!-- fr:journal kind=finding scope=spec id=spr-f5-resolved created=2026-10-06T18:02:30+00:00 state=fixed resolves=spr-f5 -->
### spr-f5-resolved · finding [fixed] · resolves spr-f5: Reserved version not reserved, not told to the session

Fixed: R11 reserves through `_reservation` as dispatch does; R6's message names the version.

<!-- fr:journal kind=finding scope=spec id=spr-f6-resolved created=2026-10-06T18:02:30+00:00 state=fixed resolves=spr-f6 -->
### spr-f6-resolved · finding [fixed] · resolves spr-f6: git outside gitseam contradicts §A

Fixed: §A states the one exception (isolation.rename_branch) and adds two declared gitseam operations; the tripwire allowance is planned in P1.T3.S1.

<!-- fr:journal kind=finding scope=spec id=spr-f7-resolved created=2026-10-06T18:02:30+00:00 state=fixed resolves=spr-f7 -->
### spr-f7-resolved · finding [fixed] · resolves spr-f7: `herdr agent rename` on a hand-started agent never observed

Fixed: P1.T1.S1 captures it live first and stops the phase if herdr cannot do it; §E says so.

<!-- fr:journal kind=finding scope=spec id=spr-f8-resolved created=2026-10-06T18:02:30+00:00 state=fixed resolves=spr-f8 -->
### spr-f8-resolved · finding [fixed] · resolves spr-f8: Strict clamp can drop the PR without refusing

Fixed: obsolete. §D stamps the event before adopt opens the new PR; the old PR is closed and never the batch's, so no backdating or clamp exists.

<!-- fr:journal kind=finding scope=spec id=spr-f9-resolved created=2026-10-06T18:02:30+00:00 state=fixed resolves=spr-f9 -->
### spr-f9-resolved · finding [fixed] · resolves spr-f9: adopt_event_time has no RED test; R7 refusal untested

Fixed: adopt_event_time is gone (§D); P1.T5.S1 asserts the event's `at` is not after the new PR's creation.

<!-- fr:journal kind=finding scope=spec id=spr-f10-resolved created=2026-10-06T18:02:30+00:00 state=fixed resolves=spr-f10 -->
### spr-f10-resolved · finding [fixed] · resolves spr-f10: Several R9 refusals untested

Fixed: P1.T5.S1 lists several agents, mid-merge and modified cursor; R9 now names the SessionAdopter refusal.

<!-- fr:journal kind=finding scope=spec id=spr-f11-resolved created=2026-10-06T18:02:30+00:00 state=fixed resolves=spr-f11 -->
### spr-f11-resolved · finding [fixed] · resolves spr-f11: Plan names wrong file paths for fakes and tests

Fixed: files list uses tests/unit/fakes.py, test_real_ghclient.py, test_forge_adapter_batch_ops.py; glab/tea files dropped (UnsupportedBatchOps covers both).

<!-- fr:journal kind=finding scope=spec id=spr-f12-resolved created=2026-10-06T18:02:30+00:00 state=fixed resolves=spr-f12 -->
### spr-f12-resolved · finding [fixed] · resolves spr-f12: `refs` on the runner-neutral AdoptTarget

Fixed: AdoptTarget carries raw labels only (§E); the ref parser is a pure helper in fr.triage.batch (P1.T5.S2).
