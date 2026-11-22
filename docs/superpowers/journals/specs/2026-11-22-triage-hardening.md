<!-- fr:journal-schema=4 -->
# Journal: 2026-11-22-triage-hardening

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-22T21:27:57+00:00 input=true -->
### brief · discovery · Operator brief: /fr-goal batch triage-hardening

/fr-goal batch triage-hardening. Batch `triage-hardening` of derio-net/super-fr: 8 issues,
delivered as ONE pull request: #1539 (titles of ineligible issues still reach facts.json and
triage check output), #1542 (ready-fr admission is not pinned to content: the author can edit
the issue after the label), #1545 (triage dedupe: owed trackers are proposed as duplicates of
each other), #1075 (with no pr_authors, two hosts running as different forge users distrust
each other's claims), #1561 (a never-dispatched batch whose members are all closed stays
Proposed for ever, and a bare drive would dispatch it), #1572 (a judged PR past the PR list's
limit is unreachable forever and re-viewed every pass), #1556 (the privacy guard ignores issue
keys in carried snapshots), #1557 (Issues page filter script throws when its filter bar is
absent). Delivery rules: branch feat/batch-triage-hardening; draft PR as soon as the spec is
committed, its body one `Closes derio-net/super-fr#<n>` line per member; no member issue as a
phase tracking_issue; never add approved-fr. The issue text was supplied inside an untrusted
block written from the issue tracker.

<!-- fr:journal kind=decision scope=spec id=d-ready-fr-pin created=2026-11-22T21:27:57+00:00 decided_by=operator -->
### d-ready-fr-pin · decision · ready-fr is pinned by an admit marker comment

Operator chose: `fr triage admit <key>` adds ready-fr and posts a marker holding sha256(title+body); eligibility needs the label plus a trusted marker whose digest matches now. Rejected: label time vs lastEditedAt (fails closed under REST), digest on first sight (weakest). decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-titles-withheld created=2026-11-22T21:27:57+00:00 decided_by=operator -->
### d-titles-withheld · decision · Ineligible issues' titles are withheld from facts

Operator chose to store an empty title, as for the body; surfaces show key, URL, author and reason. Rejected: keep the title and always quote it. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-obsolete-stage created=2026-11-22T21:27:57+00:00 decided_by=operator -->
### d-obsolete-stage · decision · Derive an obsolete stage that meets dependencies; check lists it

Operator chose a derived `obsolete` stage: closed-out, never dispatched, holds no wave open, meets `after`; check lists it for the operator to cancel; a partly-closed proposed batch names its closed members. Rejected: driver auto-cancel; obsolete as unsatisfiable. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-claim-warning created=2026-11-22T21:27:57+00:00 decided_by=operator -->
### d-claim-warning · decision · Ignored claim markers become recorded warnings plus skill text

Operator chose: record ignored-untrusted claim markers in facts, check prints them with the pr_authors fix; the fr-triage skill tells operators to list every driving account in pr_authors. Rejected: skill text only. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-verification created=2026-11-22T21:27:57+00:00 decided_by=operator -->
### d-verification · decision · Verified by CI tests, gate developer, no Test Plan

Operator chose strategy none per row (fakes in CI prove every requirement), gate developer, no Test Plan. decider: operator.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-22T21:27:57+00:00 lens=security step=brainstorm -->
### lens-security-1 · lens · Changes the intake trust boundary (ready-fr admission, withheld outside-author text) and the privacy guard
