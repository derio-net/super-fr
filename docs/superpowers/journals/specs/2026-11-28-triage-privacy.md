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
