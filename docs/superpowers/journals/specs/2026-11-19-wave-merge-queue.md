<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-wave-merge-queue

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-19T21:24:03+00:00 input=true -->
### brief · discovery · Operator brief: forge-independent wave merge queue (#1576)

Operator brief (verbatim):

derio-net/super-fr#1576 — design a forge-independent merge queue, exclusive to a wave, owned by the wave driver (fr triage batch drive). Read the issue in full; it lists the measured causes and the proposal. Operator decisions already made: the queue must NOT rely on GitHub's merge queue or any forge's queue; it is wave-exclusive. Settle the open questions in the issue in the question round. Start by reading packages/fr/src/fr/triage/batch_drive.py, batch_merge.py and commands/triage_batch_cmd.py end to end (the bridge audit rule in AGENTS.md applies), plus scripts/release.py and .github/workflows/release.yml. Related: #1577 (conflicts at planning), #1569, #1497, #1496, #1492, #1493. Output is a spec; stop for the operator's decision before planning.

Issue #1576, title: Wave driver: a forge-independent merge queue, exclusive to a wave (no update when main moves, approval pinned to content, one close-out and one release per wave)

## Problem

The wave driver's merge train does not flow. On 2026-11-19 (waves 21–23) the same actions repeated for hours: update a PR that is behind, wait for full CI, lose `approved-fr`, re-label, hit a stale artifact or a conflict, hand back, wait again. Each merge restarts that cycle for every PR behind it.

Measured causes:

1. **Main moves two or three times per merge.** `release.yml` runs on every push to main, so each batch merge is followed by a release commit (v8.3.0-rc.4, rc.5 and rc.6 came from three merges). Each close-out PR merge moves main again. The train updates every PR behind main, and each update means a full CI cycle (14 test shards, even for an archive-only close-out such as #1567), a new head and a new chance to conflict. The PRs are updated and tested one after another.
2. **Approval is pinned to a head SHA.** Any push the driver did not make voids `approved-fr`, including a pure merge of main and an empty "re-run checks" commit (#1567), though neither changed what the operator approved.
3. **Live run cursors sit on main between the feature merge and the close-out.** When a shape change lands (run kind v12), they read as stale until the next release migrates them, and `validate-artifacts` fails on every other PR (#1564 failed on triage-pages' cursor and its own). A stale artifact that a registered migration can move is not a defect on a PR.
4. **The two merges per feature multiply all of this.** The feature PR and the close-out PR each move main and each pay full CI.

## Proposal: a forge-independent merge queue, exclusive to a wave

The idea comes from merge queues (GitHub's merge queue, bors, GitLab merge trains): **a PR is never updated because main moved.** But fr must not depend on any forge's queue (GitHub's needs GraphQL, which the cloud driver cannot use; GitLab's is Premium-only; Gitea has none), so the driver owns the queue:

- **Wave-exclusive.** While a wave is merging, only that wave's batch PRs (and its close-out) enter the queue. Anything else merges between waves.
- **Speculative combinations.** For each approved green PR in queue order, the driver builds `main + PRs ahead + this PR` on a throwaway branch that fr owns, pushes it, and lets the repo's CI test it. When it is green, main moves to exactly the tested combination. When one fails, it leaves the queue and only the combinations behind it are rebuilt. Several combinations can be tested in parallel. The PR branch is never touched; it is reopened only for a real conflict or a red result of its own.
- **Approval pinned to content.** `approved-fr` records the PR's own diff (patch-id against the merge base), not the head SHA. A merge of main, an empty commit or a driver update keeps it; only a change to the PR's own diff voids it.
- **One close-out per wave.** In repos whose fr artifacts live on the default branch (not quiet or stealth), the collected close-out takes every batch of the wave and merges once, as the last entry of the wave's queue.
- **One release per wave.** No release from a push while a wave's queue is draining; the release runs once the queue is empty (and the daily cron stays as the backstop). The release's migration then follows the wave directly.
- **A stale artifact a registered migration can move does not fail a PR.** `validate-artifacts` on a PR migrates in place (no commit) and fails only on a migration that refuses.

Open questions for the spec: how main is moved to the tested combination on each forge (fast-forward push by a bypass actor, or the forge's merge of the PR at a pinned head, and what that means for the squash merge method and for "merged" state on the PR); where the queue state lives (the scope's state ref); how the release learns that a wave is draining; how a quiet or stealth repo, or a repo with no CI, takes part.

## Related

- #1555 (local suite cost), #1340 (CI wall clock): cheaper cycles, not fewer.
- #1569, #1497, #1496: close-out holds and re-recording.
- #1492, #1493: red and conflicting drafts in the train.

<!-- fr:journal kind=decision scope=spec id=d-forge-independent created=2026-11-19T21:24:03+00:00 decided_by=operator -->
### d-forge-independent · decision · No forge merge queue; wave-exclusive

Given in the brief: the queue must not rely on GitHub's or any forge's merge queue, and is exclusive to a wave.

<!-- fr:journal kind=decision scope=spec id=d-land created=2026-11-19T21:24:03+00:00 decided_by=operator -->
### d-land · decision · Landing: per repo, push by default, forge merge as option

Operator chose a per-repo choice (push | merge) plus, for squash repos, a squash-rebased chain main<A<B<C built from the PRs. Asked whether closing a,b,c would work, the analysis showed fr reads the batch PR's MERGED state everywhere (stage, gate ledger, Closes, release gating); operator chose: move each PR head to its squashed commit, then fast-forward main, so the lowercase PRs read MERGED.

<!-- fr:journal kind=decision scope=spec id=d-ci created=2026-11-19T21:24:03+00:00 decided_by=operator -->
### d-ci · decision · Queue CI: push trigger on fr-queue/**

Operator chose a push trigger on fr-queue/** declared in .fr/triage.yaml (queue.ci: push), over shadow draft PRs.

<!-- fr:journal kind=decision scope=spec id=d-release created=2026-11-19T21:24:03+00:00 decided_by=operator -->
### d-release · decision · Release: hold ref + dispatch

Operator chose a hold branch fr-hold/<scope-id> that fr release status / release.py read, deleted at drain with a release dispatch; daily cron as backstop.

<!-- fr:journal kind=decision scope=spec id=d-depth created=2026-11-19T21:24:03+00:00 decided_by=operator -->
### d-depth · decision · Speculation depth configurable, default 2

Operator chose queue.depth, default 2.

<!-- fr:journal kind=decision scope=spec id=d-replace created=2026-11-19T21:24:03+00:00 decided_by=operator -->
### d-replace · decision · Replace the train and the GitHub merge-queue mode

Operator chose: the wave queue is the only merge path; a repo whose base requires a forge merge queue is held with a reason; no-wave batches form one-batch queues between waves.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-19T21:24:03+00:00 lens=security step=brainstorm -->
### lens-security-1 · lens · The driver force-pushes PR heads (with leases) and fast-forwards main; approval semantics change from head SHA to patch-id.

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-19T21:24:03+00:00 lens=tests step=brainstorm -->
### lens-tests-1 · lens · The queue must be proven against real bare git remotes, crash windows and lease failures, not only fakes.

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-11-19T21:24:04+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: operator-request. the operator asked whether a squash-chain variant would work; one follow-up settled it and the queue CI trigger

<!-- fr:journal kind=decision scope=spec id=d-devops-barrier created=2026-11-19T21:44:18+00:00 decided_by=operator -->
### d-devops-barrier · decision · gate:devops PRs are queue barriers

Operator chose: the DevOps stage's stage-2 confirmation releases the PR to the queue instead of merging; the queue lands it alone and pauses until post-merge ops are recorded.

<!-- fr:journal kind=discovery scope=spec id=d-round3-answers created=2026-11-19T21:44:47+00:00 -->
### d-round3-answers · discovery · Operator answers from the same question round as d-devops-barrier

fr records one operator decision per answered question; these three answers came in the same round (4 questions) as d-devops-barrier, so they are recorded here verbatim rather than as separate operator decisions.

- RC counts: wave N+1's queue opens once wave N's release run finished (RC, final, or nothing installable) and cleared the hold. Tester-gated close-outs queue between waves after the gate passes.
- Channels: Needs you + board, PR marker comments, wave report. No notify command.
- Leaving a wave: the driver proposes deferral (spent budget, or stall_hours, default 4), and the operator decides with defer/requeue. The driver never defers on its own.
- Also from the operator's message: later waves wait as PRs and only build their queue once the previous wave's release is cut; a wave needs a way for PRs to leave it and later request the next queue.

<!-- fr:journal kind=finding scope=spec id=sr-r1 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r1 · finding [open] (reviewer: in scope) · Patch-id approval ignores whitespace and binary content

git patch-id --stable strips whitespace; plain git diff collapses binaries (approval.py:59-75 is exact-head today).

<!-- fr:journal kind=finding scope=spec id=sr-r2 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r2 · finding [open] (reviewer: in scope) · Under merge, the landing push leases no PR head

R10/§D left head refs out of the push under merge, so a session push could be silently dropped.

<!-- fr:journal kind=finding scope=spec id=sr-r3 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r3 · finding [open] (reviewer: in scope) · Non-atomic fallback can leave PR branches carrying other PRs' changes

Pushing heads first then main can strand stacked heads.

<!-- fr:journal kind=finding scope=spec id=sr-r4 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r4 · finding [open] (reviewer: in scope) · Patch-id 'survives the landing rewrite' is false

Against either base the landed head's diff differs.

<!-- fr:journal kind=finding scope=spec id=sr-r5 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r5 · finding [open] (reviewer: in scope) · Hold commit identity is contradictory; ls-remote cannot read state

A ref at main's sha has no own message; a commit on top is never contained by main.

<!-- fr:journal kind=finding scope=spec id=sr-r6 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r6 · finding [open] (reviewer: in scope) · A drain not carried by a main push starts no release

land: merge, deferral and quiet drains push only fr-hold/*.

<!-- fr:journal kind=finding scope=spec id=sr-r7 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r7 · finding [open] (reviewer: in scope) · Test Plan 11 contradicts R17

Item 11 said the final landing push deletes the hold.

<!-- fr:journal kind=finding scope=spec id=sr-r8 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r8 · finding [open] (reviewer: in scope) · R7 refuses ci none repos that R20 admits

No-CI repos cannot declare ci: push.

<!-- fr:journal kind=finding scope=spec id=sr-r9 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r9 · finding [open] (reviewer: in scope) · Queue branch has two names

R4 vs §C differed.

<!-- fr:journal kind=finding scope=spec id=sr-r10 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r10 · finding [open] (reviewer: in scope) · Two scopes on one repo would run two queues

Hold and leases were keyed by scope.

<!-- fr:journal kind=finding scope=spec id=sr-r11 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r11 · finding [open] (reviewer: in scope) · Repo-level queue events and non-batch entries have no home in judgements

Judgements events live on Batch (model.py:1209-1220).

<!-- fr:journal kind=finding scope=spec id=sr-r12 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r12 · finding [open] (reviewer: in scope) · DevOps stage 2 completion would let stage 3 run before the merge

_merged accepts a recorded stage 2 (ops/gate.py:1136).

<!-- fr:journal kind=finding scope=spec id=sr-r13 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r13 · finding [open] (reviewer: in scope) · _archive and _export_merge are other merge paths

triage_batch_cmd.py:6794-6807, :7099-7111 call pr_merge.

<!-- fr:journal kind=finding scope=spec id=sr-r14 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r14 · finding [open] (reviewer: in scope) · post_merge and post_merge_restart undefined for multi-batch landings

post_merge ran per merged batch.

<!-- fr:journal kind=finding scope=spec id=sr-r15 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r15 · finding [open] (reviewer: in scope) · Wave selection and the in-flight cap can deadlock; a later wave could open first

Lowest-ready selection and IN_FLIGHT counting pr-open (batch_drive.py:74, :2012).

<!-- fr:journal kind=finding scope=spec id=sr-r16 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r16 · finding [open] (reviewer: in scope) · Combinations do not run the acceptance gate

acceptance-report.yml runs on PRs and main only.

<!-- fr:journal kind=finding scope=spec id=sr-r17 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r17 · finding [open] (reviewer: in scope) · Nothing cleans fr-queue branches; the cloud proxy cannot delete

state_ref.py:18-24.

<!-- fr:journal kind=finding scope=spec id=sr-r18 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r18 · finding [open] (reviewer: in scope) · Merged-on-push does not hold for Gitea by default; the engine is GhClient-only

ghclient.py:556-663; Gitea autodetect manual merge is off by default.

<!-- fr:journal kind=finding scope=spec id=sr-r19 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r19 · finding [open] (reviewer: in scope) · Restricted fr migrate artifacts does not exist

migrate_cmd.py:134-143 takes only --yes/--adopt.

<!-- fr:journal kind=finding scope=spec id=sr-r20 created=2026-11-19T22:23:19+00:00 state=open review_scope=in -->
### sr-r20 · finding [open] (reviewer: in scope) · Fast-forwarding a protected main needs a named identity

The operator credential as bypass actor would let every session push to main.

<!-- fr:journal kind=finding scope=spec id=sr-r21 created=2026-11-19T22:23:19+00:00 state=open review_scope=out -->
### sr-r21 · finding [open] (reviewer: out of scope) · Rebase method breaks release.py's first-parent PR cross-check

AGENTS.md release gating: land by merge commit or squash.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-19T22:23:19+00:00 -->
### spec-review-1 · review · independent spec review: 21 findings

fr-spec-reviewer raised sr-r1..sr-r20 in scope and sr-r21 out of scope; decisions honoured in substance, defects in mechanism. All in-scope findings fixed in the spec (commit 'spec review fixes'); rows updated for R31-R36 and a post-merge row added.

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-19T22:23:19+00:00 lens=errors step=spec-review -->
### lens-errors-1 · lens · Many partial-failure windows: atomic push, crash between build/land and its event, hold handshake races, cloud proxy refusals (reviewer suggestion).

<!-- fr:journal kind=finding scope=spec id=sr-r1-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r1 -->
### sr-r1-resolved · finding [fixed] · resolves sr-r1: Patch-id approval ignores whitespace and binary content

R12 names `git diff --binary --full-index --no-color <mb> <head> | git patch-id --verbatim`; Test Plan 5 adds whitespace-only and binary edits that void.

<!-- fr:journal kind=finding scope=spec id=sr-r2-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r2 -->
### sr-r2-resolved · finding [fixed] · resolves sr-r2: Under merge, the landing push leases no PR head

R10 and §D push every landed head ref (unchanged under merge) with a lease; Test Plan 3 runs under squash and merge.

<!-- fr:journal kind=finding scope=spec id=sr-r3-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r3 -->
### sr-r3-resolved · finding [fixed] · resolves sr-r3: Non-atomic fallback can leave PR branches carrying other PRs' changes

The fallback is removed: a server refusing --atomic is held (R10, R22); Test Plan 3 covers it.

<!-- fr:journal kind=finding scope=spec id=sr-r4-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r4 -->
### sr-r4-resolved · finding [fixed] · resolves sr-r4: Patch-id 'survives the landing rewrite' is false

Claim dropped: R12 says the patch-id is read only before landing; a landed PR is merged and never re-read.

<!-- fr:journal kind=finding scope=spec id=sr-r5-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r5 -->
### sr-r5-resolved · finding [fixed] · resolves sr-r5: Hold commit identity is contradictory; ls-remote cannot read state

R17: a hold is a commit whose parent is the base (open) or drained main (drained); release clears when its base contains that parent. R18/§G: release.py fetches the ref and reads the message; --version runs are held; a superseded run clears nothing.

<!-- fr:journal kind=finding scope=spec id=sr-r6-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r6 -->
### sr-r6-resolved · finding [fixed] · resolves sr-r6: A drain not carried by a main push starts no release

R19: every drain reaches the release through the drained-hold push; release.yml runs on fr-hold/** pushes (not deletions); Test Plan 18 covers deferral and land: merge drains.

<!-- fr:journal kind=finding scope=spec id=sr-r7-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r7 -->
### sr-r7-resolved · finding [fixed] · resolves sr-r7: Test Plan 11 contradicts R17

Item 11 rewritten: the driver moves it to drained; only the release (or release: none) clears it, by a leased push.

<!-- fr:journal kind=finding scope=spec id=sr-r8-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r8 -->
### sr-r8-resolved · finding [fixed] · resolves sr-r8: R7 refuses ci none repos that R20 admits

R7 adds `queue.ci: none`, allowed only where services say ci none; R20 keyed on it; Test Plan 12/14.

<!-- fr:journal kind=finding scope=spec id=sr-r9-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r9 -->
### sr-r9-resolved · finding [fixed] · resolves sr-r9: Queue branch has two names

One name: bounded slots `fr-queue/<scope-id>/slot-<k>` (R4, §C).

<!-- fr:journal kind=finding scope=spec id=sr-r10-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r10 -->
### sr-r10-resolved · finding [fixed] · resolves sr-r10: Two scopes on one repo would run two queues

R31: one hold ref per repo (`fr-hold/queue`) taken by a leased push; another scope's hold blocks opening and landing with a Need; Test Plan 23.

<!-- fr:journal kind=finding scope=spec id=sr-r11-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r11 -->
### sr-r11-resolved · finding [fixed] · resolves sr-r11: Repo-level queue events and non-batch entries have no home in judgements

R24: schema 13 adds a `queues:` list with repo-level records and snake_case kinds registered in _EVENT_SCHEMAS; non-batch entries and their approvals live there.

<!-- fr:journal kind=finding scope=spec id=sr-r12-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r12 -->
### sr-r12-resolved · finding [fixed] · resolves sr-r12: DevOps stage 2 completion would let stage 3 run before the merge

R26/§J: stage 2 adds `fr-queue:release` and records nothing; _merged reads only the forge; the driver settles labels into events (no state-ref access from fr ops gate); a Need names `fr ops gate --run <id>` after landing.

<!-- fr:journal kind=finding scope=spec id=sr-r13-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r13 -->
### sr-r13-resolved · finding [fixed] · resolves sr-r13: _archive and _export_merge are other merge paths

R32: close-out, archive, export and housekeeping PRs are queue entries under their trust rules; §I lists the change; Test Plan 24.

<!-- fr:journal kind=finding scope=spec id=sr-r14-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r14 -->
### sr-r14-resolved · finding [fixed] · resolves sr-r14: post_merge and post_merge_restart undefined for multi-batch landings

R33: post_merge once per landing at the landed main, gating the next landing and the close-out start; failure pauses with a Need; Test Plan 25.

<!-- fr:journal kind=finding scope=spec id=sr-r15-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r15 -->
### sr-r15-resolved · finding [fixed] · resolves sr-r15: Wave selection and the in-flight cap can deadlock; a later wave could open first

R2/§B: open the lowest wave with a non-terminal batch; R36: PRs waiting on a later queue do not count against max_inflight; Test Plan 9.

<!-- fr:journal kind=finding scope=spec id=sr-r16-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r16 -->
### sr-r16-resolved · finding [fixed] · resolves sr-r16: Combinations do not run the acceptance gate

R7: every workflow reporting a required check must run on fr-queue/**; a check that never reports is a Need; this repo adds fr-queue/** to ci.yml and acceptance-report.yml.

<!-- fr:journal kind=finding scope=spec id=sr-r17-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r17 -->
### sr-r17-resolved · finding [fixed] · resolves sr-r17: Nothing cleans fr-queue branches; the cloud proxy cannot delete

R4: bounded slot branches reused by leased force-push, never deleted; R17: the hold is cleared by a `cleared` commit where deletion is refused.

<!-- fr:journal kind=finding scope=spec id=sr-r18-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r18 -->
### sr-r18-resolved · finding [fixed] · resolves sr-r18: Merged-on-push does not hold for Gitea by default; the engine is GhClient-only

Background corrected; R35: the queue runs on the GitHub clients (graphql and rest), glab/tea are held naming gh#611, Gitea needs autodetect, and every landed PR is read back (a still-open one is a Need).

<!-- fr:journal kind=finding scope=spec id=sr-r19-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r19 -->
### sr-r19-resolved · finding [fixed] · resolves sr-r19: Restricted fr migrate artifacts does not exist

R16 names a new repeatable `--path`, refusing non-per-file (retiring) hops; Test Plan 10.

<!-- fr:journal kind=finding scope=spec id=sr-r20-resolved created=2026-11-19T22:23:19+00:00 state=fixed resolves=sr-r20 -->
### sr-r20-resolved · finding [fixed] · resolves sr-r20: Fast-forwarding a protected main needs a named identity

R34: main must accept the direct push via a ruleset with no PR rule (required checks already passed on the tested sha) or a driver-dedicated bypass identity; fr never makes the operator's credential a bypass actor; a refusal holds with both remedies and land: merge.

<!-- fr:journal kind=finding scope=spec id=sr-r21-resolved created=2026-11-19T22:23:19+00:00 state=open resolves=sr-r21 out_of_scope=true -->
### sr-r21-resolved · finding [out-of-scope] · resolves sr-r21: Rebase method breaks release.py's first-parent PR cross-check

Out of scope: a forge rebase merge has the same effect today and this repo uses squash; not caused by this change.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-19T22:23:21+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  wave-queue-approval-content: none
  wave-queue-broken-hold: none
  wave-queue-closeout-migrates: none
  wave-queue-devops-barrier: none
  wave-queue-eject: none
  wave-queue-land-methods: none
  wave-queue-leave-wave: none
  wave-queue-live-wave: tester
  wave-queue-migratable-validation: none
  wave-queue-one-path: none
  wave-queue-operator-loop: none
  wave-queue-post-merge: none
  wave-queue-release-hold: none
  wave-queue-speculative-land: none
  wave-queue-visible: none
  wave-queue-wave-exclusive: none
row_kinds:
  wave-queue-approval-content: candidate
  wave-queue-broken-hold: candidate
  wave-queue-closeout-migrates: candidate
  wave-queue-devops-barrier: candidate
  wave-queue-eject: candidate
  wave-queue-land-methods: candidate
  wave-queue-leave-wave: candidate
  wave-queue-live-wave: live
  wave-queue-migratable-validation: candidate
  wave-queue-one-path: candidate
  wave-queue-operator-loop: candidate
  wave-queue-post-merge: candidate
  wave-queue-release-hold: candidate
  wave-queue-speculative-land: candidate
  wave-queue-visible: candidate
  wave-queue-wave-exclusive: candidate
run_gate: none
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-19-wave-merge-queue-p2 created=2026-11-19T22:27:41+00:00 decided_by=agent -->
### phase-split-2026-11-19-wave-merge-queue-p2 · decision · ask: the pure planner (wave choice, slots, landing prefix, ejection, drain) is its own reviewable ask (R2, R3, R8, R9, R13, R14, R30, R31, R36)

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-19-wave-merge-queue-p3 created=2026-11-19T22:27:45+00:00 decided_by=agent -->
### phase-split-2026-11-19-wave-merge-queue-p3 · decision · ask: git and forge execution of builds and landings (R4-R7, R10, R11, R20, R33-R35)

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-19-wave-merge-queue-p4 created=2026-11-19T22:27:48+00:00 decided_by=agent -->
### phase-split-2026-11-19-wave-merge-queue-p4 · decision · ask: the hold handshake with the release (R17-R19, R27)

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-19-wave-merge-queue-p5 created=2026-11-19T22:27:52+00:00 decided_by=agent -->
### phase-split-2026-11-19-wave-merge-queue-p5 · decision · ask: one merge path, other merges as entries and the old train removed (R22, R23, R32)

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-19-wave-merge-queue-p6 created=2026-11-19T22:27:55+00:00 decided_by=agent -->
### phase-split-2026-11-19-wave-merge-queue-p6 · decision · ask: gates and the wave close-out (R15, R16, R21, R26)

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-19-wave-merge-queue-p7 created=2026-11-19T22:27:58+00:00 decided_by=agent -->
### phase-split-2026-11-19-wave-merge-queue-p7 · decision · ask: the operator's view and leaving a wave (R25, R28, R29)

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-19-wave-merge-queue-p1 created=2026-11-19T22:28:01+00:00 decided_by=agent -->
### tier-2026-11-19-wave-merge-queue-p1 · decision · hard: changes the approval gate every merge path relies on (head SHA to patch-id) and the judgements schema

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-19-wave-merge-queue-p2 created=2026-11-19T22:28:05+00:00 decided_by=agent -->
### tier-2026-11-19-wave-merge-queue-p2 · decision · hard: the queue's ordering, exclusivity and ejection rules are the concurrency core every landing relies on

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-19-wave-merge-queue-p3 created=2026-11-19T22:28:08+00:00 decided_by=agent -->
### tier-2026-11-19-wave-merge-queue-p3 · decision · hard: leased atomic pushes to main and PR heads, and crash-window resumption

<!-- fr:journal kind=finding scope=spec id=sr-r21-resolved-2 created=2026-11-21T06:32:26+00:00 state=open resolves=sr-r21 tracked_by=https://github.com/derio-net/super-fr/issues/1603 -->
### sr-r21-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1603] · resolves sr-r21: Rebase method breaks release.py's first-parent PR cross-check

Filed at deliver as https://github.com/derio-net/super-fr/issues/1603.
