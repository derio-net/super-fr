<!-- fr:journal-schema=4 -->
# Journal: 2026-11-26-landing-method

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-26T13:05:48+00:00 input=true -->
### operator-brief · discovery · Batch landing-method brief (super-fr#1705, #1702, #1603) and the operator's decisions

Batch `landing-method` of derio-net/super-fr: 3 issues, delivered as ONE pull request.
Batch title: Landing method: refuse squash/rebase under land: push on GitHub, configured merge_method beats the viewer default.

super-fr#1705 — Queue: a squash landing by push makes GitHub close the PR, not merge it (#1704).
Live 2026-11-25: the queue landed #1704 as a squash by push and force-pushed its head ref; GitHub recorded it closed, not merged, so its `Closes` never fired and release gating now reads a first-parent `(#1704)` the forge calls unmerged (RCs only). Squash/rebase cannot mark a GitHub PR merged by push.

super-fr#1702 — triage: the driver ignores the configured merge_method when GitHub reports a viewer default.
`choose_method` (batch_merge.py:92) returns the forge default before the configured `merge_method`, and under graphql the default is the viewer's `viewerDefaultMergeMethod` (real_ghclient.py:597-606), so `.fr/triage.yaml`'s `squash` is never reached and landings are merge commits.

super-fr#1603 — Rebase method breaks release.py's first-parent PR cross-check.
`choose_method` accepts `rebase`, whose branch-subject commits break release.py's first-parent `(#N)` cross-check; that fails safe to an RC, never a wrong final.

Delivery rules: branch feat/batch-landing-method; draft PR with one `Closes derio-net/super-fr#<n>` line per member; no member issue as a phase tracking_issue; the wave driver owns mergeability and CI (no `fr pr settle` loop); never add `approved-fr`.

Operator decisions (session message, verbatim in substance):
(1) On GitHub under queue land: push, only a merge commit makes GitHub mark the PR merged; a squash or rebase force-push closes it unmerged (#1705, what happened to #1704). So under land: push on GitHub, refuse squash and rebase with a reason that names the fix, never land them.
(2) A configured merge_method in .fr/triage.yaml wins over the forge's viewer default (#1702); the viewer default is only a fallback when nothing is configured.
(3) Set this repo's .fr/triage.yaml merge_method to merge in this PR.
(4) #1603: rebase stays refused for any repo whose release reads first-parent (#N); warn or refuse, author's call in the spec.
(5) Say what release.py should do about a first-parent (#N) whose PR is closed unmerged but whose content landed (ff14a97ae, #1704): it currently makes the gate state unknown, so RCs only. Propose the fix in the spec, or file a follow-up if it does not fit.
The driver is stopped; the operator hand-merges this PR as a merge commit, so do not wait for the driver.

<!-- fr:journal kind=decision scope=spec id=d1-push-merge-only created=2026-11-26T13:05:48+00:00 -->
### d1-push-merge-only · decision · Under queue.land: push, squash and rebase are refused (held with the fix named), never landed

Operator decision (1). Spec R2, R3, R5. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d2-configured-beats-default created=2026-11-26T13:05:48+00:00 -->
### d2-configured-beats-default · decision · A configured merge_method wins over the forge's viewer default; the default is only a fallback

Operator decision (2). Spec R1. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d3-repo-merge-method-merge created=2026-11-26T13:05:48+00:00 -->
### d3-repo-merge-method-merge · decision · This repo's .fr/triage.yaml sets merge_method: merge in this PR

Operator decision (3). Spec R6. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d4-rebase-warn-under-land-merge created=2026-11-26T13:05:48+00:00 -->
### d4-rebase-warn-under-land-merge · decision · Rebase: refused under land: push (by R2); under land: merge it lands with a once-per-process warning

Operator decision (4) left warn-vs-refuse to the author. fr cannot know whether a repo's release reads first-parent (#N), so refusing rebase everywhere would remove a method other repos may rely on; this repo is protected by R2 + R6. A warning names the consequence. Spec R4. decider: author (delegated by operator).

<!-- fr:journal kind=decision scope=spec id=d5-release-closed-unmerged-counts created=2026-11-26T13:05:48+00:00 -->
### d5-release-closed-unmerged-counts · decision · release.py counts a first-parent PR the forge reports CLOSED-unmerged as landed, dated by its commit

Operator decision (5) asked for a proposal or a follow-up; it fits (one read per missed PR in waiting_prs), so it is in the spec as R7. Gate labels still decide; an OPEN PR or a failed read stays unknown. decider: author (delegated by operator).

<!-- fr:journal kind=decision scope=spec id=d6-verification-none-ci created=2026-11-26T13:05:48+00:00 -->
### d6-verification-none-ci · decision · Verification: strategy none, every row proven by unit tests in this PR's CI; gate developer

The change is pure decision logic plus a script read, all drivable with fakes; no behaviour needs an installed candidate or a released build. The operator hand-merges as a merge commit. decider: author.

<!-- fr:journal kind=decision scope=spec id=gate-no-questions-brainstorm created=2026-11-26T13:05:49+00:00 -->
### gate-no-questions-brainstorm · decision · Operator gate `brainstorm` cleared without asking

The operator stated every operator-owned decision in the session's second message (decisions 1-5 below) and asked that they be recorded instead of asked; the two calls left to the author (warn vs refuse for rebase under land: merge, the verification strategy) are recorded as author decisions.
