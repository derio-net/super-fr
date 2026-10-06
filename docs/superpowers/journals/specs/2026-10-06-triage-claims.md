# Journal: 2026-10-06-triage-claims

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-06T18:36:38+00:00 input=true -->
### operator-brief · discovery · Operator brief: batch triage-claims (super-fr#1043)

Batch dispatch brief (operator, 2026-10-06), verbatim:

/fr-goal Triage across scopes and hosts: signed per-issue claims, and one named board per claim holder

Batch `triage-claims` of derio-net/super-fr: 1 issues, delivered as ONE pull request. Wave 10. Starts with a brainstorm: claim timing, expiry, take-over and the publishing hook are the operator's. Delivery rules: branch `feat/batch-triage-claims`; open a draft PR as soon as the spec is committed with `Closes derio-net/super-fr#1043`; do not name any member issue as a phase tracking_issue.

## super-fr#1043: Triage across scopes and hosts: a signed per-issue claim, so overlapping scopes keep clear, and one named board per claim holder

**Run with `/fr-brainstorming` (or `/fr-goal`): the claim's lifecycle is the operator's design call.**

## Problem

`fr triage` scopes overlap. One repo, a group of repos (`--repo A/B,C/D`) and a whole org (`--org`) can all contain the same issue. Each scope may be driven from a different host. Nothing coordinates them today:

- `drive.lock` lives in the scope's state directory (`~/.cache/fr/triage/<scope>/`), so it is per machine **and** per scope shape. A second driver on another host, or on an overlapping scope on the same host, never sees it.
- The state (`judgements.yaml`: batches, events, close-out records) is per scope directory. The repo copy (`docs/triage`, #969/#976) is history for single-repo scopes. An org scope has no single repo to keep it in, so persisting triage state in a repo is only a half measure.
- The only cross-host guard: a *proposed* batch refuses to dispatch when its branch is already on `origin` ("already dispatched from another scope"). A session pushes its branch only after its spec or failing test is committed, so for minutes after a dispatch a second driver can start the same work.

Two drivers on overlapping scopes would duplicate dispatches, race on updating and merging the same ready PRs, start duplicate close-outs (#883 across hosts) and export conflicting state (last writer wins). Each would render a different board.

## Proposal: a signed per-issue claim

Coordinate on the **issue**, which every scope shape shares, not on a repo or a directory.

1. **A scope identity.** Each triage scope on a host has a stable id: a hash of the scope shape (sorted `owner/repo` slugs, or `org:<owner>`) plus a host id. It is hashed the way `fr usage` labels hosts (`h-<sha256(...)>`), so no hostname reaches a public issue. It lives in the scope's own state, beside `judgements.yaml`, never in a target repo's `.fr/triage.yaml`: an org scope has no single repo.
2. **Claim at selection, not only at dispatch.** When an issue joins a batch that has a wave, the scope claims it: one `fr:claimed` label (cheap to list) plus a hidden marker comment carrying the signer id, the batch and a timestamp. This extends today's `fr:in-progress` label and batch marker (`batch_dispatch.py`, `latest_marker`).
3. **Hands off for everyone else.** Every other scope's `check` and driver still judge a claimed issue, but never batch, dispatch, merge, close out or export it. The board shows it as "held by `<scope id>`".
4. **Claims expire.** The holder refreshes a heartbeat on its marker each driver pass. A claim past its expiry is reported (extending the stale-dispatch check, `stale_dispatch_days`) and can be taken over. `batch cancel` releases a claim explicitly.
5. **One board per claim holder, published as a named artifact.** Each driving scope publishes its own batch board after each pass, named by its scope (for example `super-fr batches`, `derio-net batches`). Together they form a set of boards, each showing what its holder drives plus what others hold. This answers the stale-artifact problem too: today the published board only changes when someone republishes it by hand.

## Notes

- A claim is a coordination mark, not security. Anyone with write access can forge or delete one. The PR-author allowlist (`pr_authors`) still guards merging.
- Judging stays free: two scopes may rank the same issue differently. Only acting on it is exclusive.
- Open questions for the brainstorm: claim at batch creation or only at wave assignment; expiry length; take-over (automatic after expiry, or operator-confirmed); how the board-publishing hook is configured per scope and harness.

## Acceptance

- Two drivers on overlapping scopes (one repo and its org, two hosts) never dispatch, merge or close out the same issue.
- A claim whose holder stopped refreshing it is reported, and can be released or taken over.
- Each driving scope publishes its own named board after each pass.

Related: #970 (the pages), #976 (state export), #998 (driver restarts), #883 (duplicate close-outs on one host).

<!-- fr:journal kind=decision scope=spec id=claim-at-wave created=2026-10-06T18:36:38+00:00 -->
### claim-at-wave · decision · Claim at wave assignment

Operator: an issue is claimed when its batch gets a wave (create/edit --wave), and at dispatch for a wave-less batch. A proposed batch with no wave claims nothing.

<!-- fr:journal kind=decision scope=spec id=claim-expiry-24h created=2026-10-06T18:36:38+00:00 -->
### claim-expiry-24h · decision · Claims expire after 24 hours, per-scope override

Operator: 24h default, `claim_expiry_hours` in the scope config.

<!-- fr:journal kind=decision scope=spec id=claim-takeover-operator created=2026-10-06T18:36:38+00:00 -->
### claim-takeover-operator · decision · Take-over is operator-confirmed

Operator: expired claims are reported; `fr triage claim take`/`release` move them; a driver never takes one itself.

<!-- fr:journal kind=decision scope=spec id=claim-heartbeat-edit created=2026-10-06T18:36:38+00:00 -->
### claim-heartbeat-edit · decision · Heartbeat edits the marker in place

Operator: one marker comment per signer, edited with a new heartbeat once older than expiry/4. Needs a new edit-comment forge method; GitHub only.

<!-- fr:journal kind=decision scope=spec id=board-publish-scope-config created=2026-10-06T18:36:38+00:00 -->
### board-publish-scope-config · decision · Board publishing is a scope-local command

Operator: `publish:` argv in `<state>/scope.yaml` with {board}/{name}/{scope_id}, run after each --yes drive pass; failures warn once, never stop the drive. Default name `<scope> batches`.

<!-- fr:journal kind=decision scope=spec id=verify-candidate created=2026-10-06T18:36:38+00:00 -->
### verify-candidate · decision · Verification: candidate + scenarios

Operator: candidate walk with scenarios for the read-side (held elsewhere, expired); unit tests for the rest; no post-merge row.

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-10-06T18:43:36+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · claim()/holder() weigh live claims only, so an un-released expired foreign claim is silently taken over

R4's race rule ranged over live claims only: a scope claiming against an expired, un-released foreign claim would win, an automatic take-over the operator ruled out, and contradicting R6.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-10-06T18:43:36+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · release drops fr:claimed when no live claim is left, hiding expired claims from collect

collect reads comments only of fr:claimed issues, so dropping the label while an expired un-released marker remains hides it from facts, check and R6.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-10-06T18:43:36+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · claims released at stage merged, before the close-out runs

CLOSED_OUT includes merged (batch.py:59) but the close-out runs after it (batch_drive.py:851-888); releasing at merged reopens cross-host duplicate close-outs. The wave-less owed clause also alternated with releases.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-10-06T18:43:36+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · claims on closed members are never in facts, so owed_releases cannot release them

collect reads open issues only; a merged batch's members are closed.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-10-06T18:43:36+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · own expired claims are never refreshed after a driver outage

R8 refreshed live claims only; a refresh could also resurrect a marker another scope's take released.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-10-06T18:43:36+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · dispatch must claim before the runner launch

runner.dispatch (:1125) precedes _forge_writes (:1146); a lost race would be found after a session started.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-10-06T18:43:36+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · batch cancel refused for a held batch deadlocks it

A held own batch could never be dispatched, merged or cancelled.

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-10-06T18:43:36+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · deferring the wave-assignment claim to --yes departs from claim-at-wave, and the gap is invisible

create/edit are local-only today.

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-10-06T18:43:36+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · a re-claim posts a new comment, breaking one-marker-per-signer; moving a member between batches unspecified

Editing a released marker back to live would keep its old created_at and wrongly win R4.

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-10-06T18:43:36+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · concurrent first use can mint two host ids

Atomic rename does not stop two processes each minting an id.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-10-06T18:43:36+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · a held batch with a running session is left out of --max-inflight

A backfilled held batch may already be dispatched.

<!-- fr:journal kind=finding scope=spec id=sr-12 created=2026-10-06T18:43:36+00:00 state=open review_scope=in -->
### sr-12 · finding [open] (reviewer: in scope) · Verification row descriptions do not cover several requirements their rows claim

R1 scope show, R3 create/edit, R9 take/release, R12 collect/schema, R14 board --publish and names, R15 export exclusion, R16 mirrors were unnamed.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-10-06T18:43:36+00:00 -->
### spec-review-1 · review · independent spec review: 12 findings

fr-spec-reviewer checked the six operator decisions against R1-R16 and §3, every named file/line against the code (all references verified correct), and internal consistency across requirements, design, Verification and §6. Findings sr-1..sr-12, all in scope, all fixed in the spec. No finding on the facts schema bump, harness neutrality of the argv publish hook, privacy of the marker, or the gh comment url as the PATCH id source.

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-10-06T18:43:36+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: claim()/holder() weigh live claims only, so an un-released expired foreign claim is silently taken over

R4 and §3.B/§3.D now range over every un-released claim, live or expired; expiry changes only what the operator is offered.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-10-06T18:43:36+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: release drops fr:claimed when no live claim is left, hiding expired claims from collect

R10 and §3.D remove the label only when no un-released claim, live or expired, remains.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-10-06T18:43:36+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: claims released at stage merged, before the close-out runs

§3.B releasing(): cancelled, abandoned or finished (run archived); merged/partial keep and refresh claims. owed_claims bounded to not-releasing batches.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-10-06T18:43:36+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: claims on closed members are never in facts, so owed_releases cannot release them

Releases are derived from the batch side and read/written per member at release time, open or closed; recorded as a claims_released event (judgements schema 6) so they are not repeated.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-10-06T18:43:36+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: own expired claims are never refreshed after a driver outage

R8 refreshes own un-released claims, expired included; refresh re-reads and returns Held without writing when the marker was released by a take.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-10-06T18:43:36+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: dispatch must claim before the runner launch

R3 and §3.E: the claim, R4's re-read included, completes after the compare-before-write checks and before the runner launch.

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-10-06T18:43:36+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: batch cancel refused for a held batch deadlocks it

R6 and §3.E allow cancel on a held batch: it releases own claims and leaves held members' label and comments to their holder; touches_forge now covers a proposed batch with written claims.

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-10-06T18:43:36+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: deferring the wave-assignment claim to --yes departs from claim-at-wave, and the gap is invisible

create/edit gain --yes that writes the claims at wave assignment; without it the claims are owed and shown in check's and claim list's new `claims owed` set; recorded under §2.2 decision 1.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-10-06T18:43:36+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: a re-claim posts a new comment, breaking one-marker-per-signer; moving a member between batches unspecified

R2: at most one un-released marker per signer; re-claim posts a new one. R3/§3.D: an own un-released claim naming another batch is edited in place (continuous hold).

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-10-06T18:43:36+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: concurrent first use can mint two host ids

§3.A: temp file hard-linked into place (fails if it exists), loser re-reads the winner; path through fr.isolation.types._home().

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-10-06T18:43:36+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: a held batch with a running session is left out of --max-inflight

§3.F: held batches in LIVE_STAGES count; only proposed held batches do not.

<!-- fr:journal kind=finding scope=spec id=sr-12-resolved created=2026-10-06T18:43:36+00:00 state=fixed resolves=sr-12 -->
### sr-12-resolved · finding [fixed] · resolves sr-12: Verification row descriptions do not cover several requirements their rows claim

Every Verification row now names the tests that cover each requirement it maps.
