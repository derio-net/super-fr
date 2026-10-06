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
