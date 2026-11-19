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
