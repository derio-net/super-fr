<!-- fr:journal-schema=4 -->
# Journal: 2026-11-28-triage-privacy

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-28T14:29:52+00:00 input=true -->
### operator-brief · discovery · The batch triage-privacy dispatch brief, verbatim

/fr-goal batch triage-privacy

Batch `triage-privacy` of derio-net/super-fr: 4 issues, delivered as ONE pull request.

(untrusted block, quoted from the issue tracker)
> Batch title: Triage privacy: outsider text never reaches worker sessions or the state ref unfenced
> #### super-fr#1633 — the admit digest pins title and body only; later outsider comments reach a worker reading the thread. `content_digest(title, body)` (`packages/fr/src/fr/triage/admit.py:34`) pins only title and body, so an outsider comment added after admission still reaches a worker reading the thread.
> #### super-fr#1634 — the privacy guard ignores other state-ref entries (merge-stops.json, history/, issues/, requests/sessions yaml). The privacy guard (`packages/fr/src/fr/triage/privacy.py:117` `leak_risk`, `check_or_refuse`) checks only issue keys against repo visibility; other state-ref entries are not inspected, so a private repo's content can reach a public state ref.
> #### super-fr#1632 — outside-author PR titles are never withheld (prs, gated_prs, batch_prs, judged_prs). Prompt-injection surface on a public repo, but nothing runs on it without an operator-driven dispatch.
> #### super-fr#1631 — A carried CLOSED judged PR that is later reopened stays carried as closed.

Delivery rules: branch `feat/batch-triage-privacy`; draft PR as soon as the spec is committed, body closing derio-net/super-fr#1633, #1634, #1632, #1631 one per line; no member issue as a phase `tracking_issue`; the wave driver owns mergeability and CI (no `fr pr settle` loop); never add `approved-fr`.

<!-- fr:journal kind=decision scope=spec id=d-admit-pins-comments created=2026-11-28T14:29:52+00:00 decided_by=operator -->
### d-admit-pins-comments · decision · #1633: the admit digest also pins every untrusted author's comment

Operator chose (round 1 q1, recommended) to extend the digest over untrusted comments (login, time, body, in order); a new or edited untrusted comment voids the admission until re-admitted; the preview shows them. Rejected: void on a newer comment only; a brief-only fence.

<!-- fr:journal kind=decision scope=spec id=d-v1-markers-stop created=2026-11-28T14:29:52+00:00 decided_by=operator -->
### d-v1-markers-stop · decision · #1633: version-1 admit markers stop admitting

Operator chose (round 1 q2, recommended) fail closed; a v1 marker gives a reason naming fr triage admit <key>. Rejected - keep v1 admitting while no untrusted comment exists.

<!-- fr:journal kind=decision scope=spec id=d-pr-title-login-rule created=2026-11-28T14:29:52+00:00 decided_by=operator -->
### d-pr-title-login-rule · decision · #1632: a PR keeps its title only when its author is in the claim-trust set

Operator chose (round 1 q3, recommended) the login rule (viewer + pr_authors), no new association read. Rejected - logins plus OWNER/MEMBER/COLLABORATOR via a PR association read.

<!-- fr:journal kind=decision scope=spec id=d-guard-scans-carried-files created=2026-11-28T14:29:52+00:00 decided_by=operator -->
### d-guard-scans-carried-files · decision · #1634: the guard scans every carried file for non-public repo names

Operator leaned to the scan in round 1 q4 but asked about cost; measured on the host's state dirs (largest 50 carried files / 4.6 MB, ~150 ms cold; others < 5 ms), and in round 2 the operator chose the scan, with the short circuits (state repo public and some repo non-public). Rejected - per-file extractors.

<!-- fr:journal kind=decision scope=spec id=d-verification-none created=2026-11-28T14:29:52+00:00 decided_by=operator -->
### d-verification-none · decision · Verification: strategy none, CI unit tests; gate developer

Operator chose (round 1 q5, recommended) strategy none; every requirement is engine behaviour fakes prove in CI.

<!-- fr:journal kind=decision scope=spec id=d-reopened-pr-truncation created=2026-11-28T14:29:52+00:00 decided_by=operator -->
### d-reopened-pr-truncation · decision · #1631: carry a CLOSED judged PR only when the open-PR list was complete

Settled from the code, not asked - a reopened PR within the open-PR list's limit is already found there (listed_prs precedes finished_prs, collect.py:875); only a truncated list strands it, and carried closed issues already skip the carry on truncation (collect.py:881).

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-11-28T14:29:53+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: operator-request. the operator answered round-1 question 4 with a question about the scan's cost; round 2 put the measured cost to them and asked again

<!-- fr:journal kind=finding scope=spec id=s-r1 created=2026-11-28T14:39:50+00:00 state=open review_scope=in -->
### s-r1 · finding [open] (reviewer: in scope) · R2 cannot be built from stored facts: no field carries the admit marker's version, and a v1 digest equals a v2 one when no untrusted comment exists

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r2 created=2026-11-28T14:39:50+00:00 state=open review_scope=in -->
### s-r2 · finding [open] (reviewer: in scope) · Facts schema 18 is already taken: FACTS_SCHEMA is 21, so this change is 22

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r3 created=2026-11-28T14:39:50+00:00 state=open review_scope=in -->
### s-r3 · finding [open] (reviewer: in scope) · Loading older facts makes ready-fr issues ineligible but does not withhold their titles and bodies

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r4 created=2026-11-28T14:39:50+00:00 state=open review_scope=in -->
### s-r4 · finding [open] (reviewer: in scope) · The comment digest is not stable across forge adapters and hosts, so an admission can stay voided for good

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r5 created=2026-11-28T14:39:50+00:00 state=open review_scope=in -->
### s-r5 · finding [open] (reviewer: in scope) · No triage decision reads a PR's title is false: the merge queue's squash subject is built from the facts title

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r6 created=2026-11-28T14:39:50+00:00 state=open review_scope=in -->
### s-r6 · finding [open] (reviewer: in scope) · The Design shape misses where PR titles are shown and disagrees with §B on the withholding function's signature

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r7 created=2026-11-28T14:39:50+00:00 state=open review_scope=in -->
### s-r7 · finding [open] (reviewer: in scope) · The scan's word boundary misses sentence-final and .git mentions, and the name#n form refuses forever when a public and a private repo share a name

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r8 created=2026-11-28T14:39:50+00:00 state=open review_scope=in -->
### s-r8 · finding [open] (reviewer: in scope) · R8's every file the write would carry does not hold for export, and the refusal gives no fix for engine-written files

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r9 created=2026-11-28T14:39:50+00:00 state=open review_scope=in -->
### s-r9 · finding [open] (reviewer: in scope) · An org scope with no usable facts gets an empty member set, so the scan looks only for key repos

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r10 created=2026-11-28T14:39:50+00:00 state=open review_scope=in -->
### s-r10 · finding [open] (reviewer: in scope) · The reason R4 quotes does not exist, and the marker's human line and the preview's hidden-character warning still speak of title and body only

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r11 created=2026-11-28T14:39:50+00:00 state=open review_scope=in -->
### s-r11 · finding [open] (reviewer: in scope) · The spec has no `## Test Plan` heading while artifacts.test_plan is on

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r12 created=2026-11-28T14:39:50+00:00 state=open review_scope=out -->
### s-r12 · finding [open] (reviewer: out of scope) · Origins collect stores outside authors' PR titles too, and they ride the state ref

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r13 created=2026-11-28T14:39:50+00:00 state=open review_scope=out -->
### s-r13 · finding [open] (reviewer: out of scope) · state export checks the state repo's visibility, not the visibility of the repo it exports into

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-28T14:39:50+00:00 -->
### spec-review-1 · review · independent spec review: 13 findings (11 in scope, 2 out of scope)

Dispatched fr-spec-reviewer (read-only, separate context) over the spec, the spec journal and the repo settings. Findings s-r1..s-r13; s-r1..s-r10 fixed in the spec, s-r11 refuted, s-r12 and s-r13 out of scope. The reviewer found all six operator decisions honoured.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-28T14:39:50+00:00 lens=security step=spec-review -->
### lens-security-1 · lens · three trust boundaries: comment pinning, PR-title withholding, the state-ref scan's matching

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-28T14:39:50+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · fail-closed paths (v1 markers, older-schema loads, truncated PR lists, scan short circuits) are easy to test only on the happy path

<!-- fr:journal kind=finding scope=spec id=s-r1-resolved created=2026-11-28T14:39:50+00:00 state=fixed resolves=s-r1 -->
### s-r1-resolved · finding [fixed] · resolves s-r1: R2 cannot be built from stored facts: no field carries the admit marker's version, and a v1 digest equals a v2 one when no untrusted comment exists

The v2 digest text starts with a fixed `fr-admit-v2` line and parse_admit returns a digest for version 2 only (R1, R2, §A), so no v1 digest can match and no new field is needed.

<!-- fr:journal kind=finding scope=spec id=s-r2-resolved created=2026-11-28T14:39:50+00:00 state=fixed resolves=s-r2 -->
### s-r2-resolved · finding [fixed] · resolves s-r2: Facts schema 18 is already taken: FACTS_SCHEMA is 21, so this change is 22

R4, §A and Verification now name schema 22 and the schema-21 load; verified model.py:108.

<!-- fr:journal kind=finding scope=spec id=s-r3-resolved created=2026-11-28T14:39:50+00:00 state=fixed resolves=s-r3 -->
### s-r3-resolved · finding [fixed] · resolves s-r3: Loading older facts makes ready-fr issues ineligible but does not withhold their titles and bodies

R4 and §A: the below-22 load re-runs _withhold_untrusted_text after resetting admit_read; the Verification row tests it.

<!-- fr:journal kind=finding scope=spec id=s-r4-resolved created=2026-11-28T14:39:50+00:00 state=fixed resolves=s-r4 -->
### s-r4-resolved · finding [fixed] · resolves s-r4: The comment digest is not stable across forge adapters and hosts, so an admission can stay voided for good

R1 defines a canonical comment (login lowercased, [bot] stripped, ghost for none, UTC seconds), a total sort key, and a pinning rule of association or pr_authors that leaves the viewer out, so admit, collect and dispatch agree; R5 names the trusted set recheck uses.

<!-- fr:journal kind=finding scope=spec id=s-r5-resolved created=2026-11-28T14:39:50+00:00 state=fixed resolves=s-r5 -->
### s-r5-resolved · finding [fixed] · resolves s-r5: No triage decision reads a PR's title is false: the merge queue's squash subject is built from the facts title

R7 and §B list the queue reader (triage_batch_cmd.py:6983, queue_exec._subject, verified) and use the batch title when the stored title is empty.

<!-- fr:journal kind=finding scope=spec id=s-r6-resolved created=2026-11-28T14:39:50+00:00 state=fixed resolves=s-r6 -->
### s-r6-resolved · finding [fixed] · resolves s-r6: The Design shape misses where PR titles are shown and disagrees with §B on the withholding function's signature

The Design shape lists triage_cmd.py, kanban.py, kanban_render.py, triage_batch_cmd.py and triage_state_cmd.py; one signature, _withhold_untrusted_pr_titles(facts) -> Facts.

<!-- fr:journal kind=finding scope=spec id=s-r7-resolved created=2026-11-28T14:39:50+00:00 state=fixed resolves=s-r7 -->
### s-r7-resolved · finding [fixed] · resolves s-r7: The scan's word boundary misses sentence-final and .git mentions, and the name#n form refuses forever when a public and a private repo share a name

R8 and §C: the trailing bound is (?![\w-])(?!\.\w), and the key form is not looked for when a public look-for repo shares the name.

<!-- fr:journal kind=finding scope=spec id=s-r8-resolved created=2026-11-28T14:39:50+00:00 state=fixed resolves=s-r8 -->
### s-r8-resolved · finding [fixed] · resolves s-r8: R8's every file the write would carry does not hold for export, and the refusal gives no fix for engine-written files

R8: a push scans REF_FILES, an export its durable set; the refusal names file, repo and remedy; a looping drive handles it as a PrivacyError today.

<!-- fr:journal kind=finding scope=spec id=s-r9-resolved created=2026-11-28T14:39:50+00:00 state=fixed resolves=s-r9 -->
### s-r9-resolved · finding [fixed] · resolves s-r9: An org scope with no usable facts gets an empty member set, so the scan looks only for key repos

R8 and §C: an org scope with missing or unusable facts refuses as VisibilityUnreadable naming fr triage collect.

<!-- fr:journal kind=finding scope=spec id=s-r10-resolved created=2026-11-28T14:39:50+00:00 state=fixed resolves=s-r10 -->
### s-r10-resolved · finding [fixed] · resolves s-r10: The reason R4 quotes does not exist, and the marker's human line and the preview's hidden-character warning still speak of title and body only

R4 quotes the existing reason (intake.py:87); R3 adds the new human line and passes comments through the visible-character rendering and warning.

<!-- fr:journal kind=finding scope=spec id=s-r11-resolved created=2026-11-28T14:39:50+00:00 state=refuted resolves=s-r11 -->
### s-r11-resolved · finding [refuted] · resolves s-r11: The spec has no `## Test Plan` heading while artifacts.test_plan is on

A `## Test Plan` holds only the post-merge rows no pre-merge strategy can exercise; every row here is verified in CI (`## Verification`, strategy none), so there is none to list. The brainstorm resolve accepted the spec under artifacts.test_plan: on, as it did the sibling specs the reviewer cites.

<!-- fr:journal kind=finding scope=spec id=s-r12-resolved created=2026-11-28T14:39:50+00:00 state=open resolves=s-r12 out_of_scope=true -->
### s-r12-resolved · finding [out-of-scope] · resolves s-r12: Origins collect stores outside authors' PR titles too, and they ride the state ref

Not caused by this change: origins data predates it and none of the batch's issues names it; listed under Out of scope and filed at deliver.

<!-- fr:journal kind=finding scope=spec id=s-r13-resolved created=2026-11-28T14:39:50+00:00 state=open resolves=s-r13 out_of_scope=true -->
### s-r13-resolved · finding [out-of-scope] · resolves s-r13: state export checks the state repo's visibility, not the visibility of the repo it exports into

Pre-existing guard behaviour this change does not cause; listed under Out of scope and filed at deliver.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-28T14:39:59+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  triage-admit-pins-comments: none
  triage-pr-title-withheld: none
  triage-reopened-pr-uncarried: none
  triage-state-scan-guard: none
row_kinds:
  triage-admit-pins-comments: none
  triage-pr-title-withheld: none
  triage-reopened-pr-uncarried: none
  triage-state-scan-guard: none
run_gate: developer
run_kind: none
```
