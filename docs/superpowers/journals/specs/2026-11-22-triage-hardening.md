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

<!-- fr:journal kind=finding scope=spec id=s-r1 created=2026-11-22T21:35:09+00:00 state=open review_scope=in -->
### s-r1 · finding [open] (reviewer: in scope) · Admission digest can never match for a body over 2000 chars: facts store a truncated body

See the spec reviewer's return; fixed in the spec (see resolution).

<!-- fr:journal kind=finding scope=spec id=s-r2 created=2026-11-22T21:35:09+00:00 state=open review_scope=in -->
### s-r2 · finding [open] (reviewer: in scope) · `batch cancel` refuses every CLOSED_OUT stage, so the command R9 prints for an obsolete batch fails

See the spec reviewer's return; fixed in the spec (see resolution).

<!-- fr:journal kind=finding scope=spec id=s-r3 created=2026-11-22T21:35:09+00:00 state=open review_scope=in -->
### s-r3 · finding [open] (reviewer: in scope) · `_admitted` still treats the ready-fr label as admitting, so the association of a labelled issue is never read

See the spec reviewer's return; fixed in the spec (see resolution).

<!-- fr:journal kind=finding scope=spec id=s-r4 created=2026-11-22T21:35:09+00:00 state=open review_scope=in -->
### s-r4 · finding [open] (reviewer: in scope) · A facts file of schema 15 loads with titles, and bodies once admitted by the label, that the new rule withholds

See the spec reviewer's return; fixed in the spec (see resolution).

<!-- fr:journal kind=finding scope=spec id=s-r5 created=2026-11-22T21:35:09+00:00 state=open review_scope=in -->
### s-r5 · finding [open] (reviewer: in scope) · 'Holds no wave open' is not designed: `finished_waves` and `preselected_wave` do not read CLOSED_OUT

See the spec reviewer's return; fixed in the spec (see resolution).

<!-- fr:journal kind=finding scope=spec id=s-r6 created=2026-11-22T21:35:09+00:00 state=open review_scope=in -->
### s-r6 · finding [open] (reviewer: in scope) · Obsolete silently replaces the awaiting-live hold for never-dispatched batches

See the spec reviewer's return; fixed in the spec (see resolution).

<!-- fr:journal kind=finding scope=spec id=s-r7 created=2026-11-22T21:35:09+00:00 state=open review_scope=in -->
### s-r7 · finding [open] (reviewer: in scope) · The privacy guard misses private repo keys in the snapshot `prs` map, and a lenient read lets an unparseable snapshot through

See the spec reviewer's return; fixed in the spec (see resolution).

<!-- fr:journal kind=finding scope=spec id=s-r8 created=2026-11-22T21:35:09+00:00 state=open review_scope=in -->
### s-r8 · finding [open] (reviewer: in scope) · On GitLab/Gitea scopes, admission becomes impossible: admit can write, collect cannot read comments

See the spec reviewer's return; fixed in the spec (see resolution).

<!-- fr:journal kind=finding scope=spec id=s-r9 created=2026-11-22T21:35:09+00:00 state=open review_scope=in -->
### s-r9 · finding [open] (reviewer: in scope) · The operator-facing text still says 'label it ready-fr to admit it'

See the spec reviewer's return; fixed in the spec (see resolution).

<!-- fr:journal kind=finding scope=spec id=s-r10 created=2026-11-22T21:35:09+00:00 state=open review_scope=in -->
### s-r10 · finding [open] (reviewer: in scope) · `pr_view` does not carry what a `PullRequest` needs, and the cited lines are not the CLI and REST clients

See the spec reviewer's return; fixed in the spec (see resolution).

<!-- fr:journal kind=finding scope=spec id=s-r11 created=2026-11-22T21:35:09+00:00 state=open review_scope=in -->
### s-r11 · finding [open] (reviewer: in scope) · R1 says dedupe shows withheld issues by key, but R6/§C remove them from dedupe

See the spec reviewer's return; fixed in the spec (see resolution).

<!-- fr:journal kind=finding scope=spec id=s-r12 created=2026-11-22T21:35:09+00:00 state=open review_scope=in -->
### s-r12 · finding [open] (reviewer: in scope) · §E counts `batch_drive.py:2039` as a dependency test; it is an assignment

See the spec reviewer's return; fixed in the spec (see resolution).

<!-- fr:journal kind=finding scope=spec id=s-r13 created=2026-11-22T21:35:09+00:00 state=open review_scope=in -->
### s-r13 · finding [open] (reviewer: in scope) · The admit read reuses the claim read's comments, but `_comment_facts` neither returns them nor tolerates a failure

See the spec reviewer's return; fixed in the spec (see resolution).

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-22T21:35:09+00:00 -->
### spec-review-1 · review · Spec review of 2026-11-22-triage-hardening: 13 findings

Dispatched fr-spec-reviewer raised s-r1..s-r13, all in scope; every operator decision appears in the spec. All 13 fixed in the spec. Suggested lenses: security (already recorded), tests.

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-22T21:35:09+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · Back-compat loads (v15 facts), forge-call counts and wave predicates are easy to leave untested

<!-- fr:journal kind=finding scope=spec id=s-r1-resolved created=2026-11-22T21:35:09+00:00 state=fixed resolves=s-r1 -->
### s-r1-resolved · finding [fixed] · resolves s-r1: Admission digest can never match for a body over 2000 chars: facts store a truncated body

R3/R5 and §B: collect computes `content_digest` from the full forge record before `_body` truncates it and stores it on `Issue`; intake compares the two stored digests. Test row names a body over BODY_LIMIT.

<!-- fr:journal kind=finding scope=spec id=s-r2-resolved created=2026-11-22T21:35:09+00:00 state=fixed resolves=s-r2 -->
### s-r2-resolved · finding [fixed] · resolves s-r2: `batch cancel` refuses every CLOSED_OUT stage, so the command R9 prints for an obsolete batch fails

R9 and §E: `batch cancel` accepts `obsolete` (appends the cancel event only; a never-dispatched batch withdraws nothing).

<!-- fr:journal kind=finding scope=spec id=s-r3-resolved created=2026-11-22T21:35:09+00:00 state=fixed resolves=s-r3 -->
### s-r3-resolved · finding [fixed] · resolves s-r3: `_admitted` still treats the ready-fr label as admitting, so the association of a labelled issue is never read

R5 and §B: `_admitted` drops the ready-fr clause, so the association is read; admit's already-eligible check is the login clause only. Test row names a MEMBER-authored labelled issue with no marker.

<!-- fr:journal kind=finding scope=spec id=s-r4-resolved created=2026-11-22T21:35:09+00:00 state=fixed resolves=s-r4 -->
### s-r4-resolved · finding [fixed] · resolves s-r4: A facts file of schema 15 loads with titles, and bodies once admitted by the label, that the new rule withholds

R1 and §A: `load_facts` re-withholds any file below schema 16; test row names the v15 load.

<!-- fr:journal kind=finding scope=spec id=s-r5-resolved created=2026-11-22T21:35:09+00:00 state=fixed resolves=s-r5 -->
### s-r5-resolved · finding [fixed] · resolves s-r5: 'Holds no wave open' is not designed: `finished_waves` and `preselected_wave` do not read CLOSED_OUT

R8 and §E: `finished_waves` counts obsolete terminal, `preselected_wave` treats it non-live, `cancelled_waves` counts an all-obsolete wave as delivering nothing; in the test row.

<!-- fr:journal kind=finding scope=spec id=s-r6-resolved created=2026-11-22T21:35:09+00:00 state=fixed resolves=s-r6 -->
### s-r6-resolved · finding [fixed] · resolves s-r6: Obsolete silently replaces the awaiting-live hold for never-dispatched batches

R8 and §E: obsolete takes precedence over the awaiting-live hold for a never-dispatched batch, stated; the hold still applies to batches with a lifecycle event; in the test row.

<!-- fr:journal kind=finding scope=spec id=s-r7-resolved created=2026-11-22T21:35:09+00:00 state=fixed resolves=s-r7 -->
### s-r7-resolved · finding [fixed] · resolves s-r7: The privacy guard misses private repo keys in the snapshot `prs` map, and a lenient read lets an unparseable snapshot through

R12 and §G: snapshot issue and PR keys plus debt repos are checked; a strict per-file reader refuses an unparseable snapshot.

<!-- fr:journal kind=finding scope=spec id=s-r8-resolved created=2026-11-22T21:35:09+00:00 state=fixed resolves=s-r8 -->
### s-r8-resolved · finding [fixed] · resolves s-r8: On GitLab/Gitea scopes, admission becomes impossible: admit can write, collect cannot read comments

R2/R4, §B and Out of scope: admit refuses on glab/tea before any write; the intake reason says the forge cannot list comments; GitLab/Gitea admission recorded as out of scope.

<!-- fr:journal kind=finding scope=spec id=s-r9-resolved created=2026-11-22T21:35:09+00:00 state=fixed resolves=s-r9 -->
### s-r9-resolved · finding [fixed] · resolves s-r9: The operator-facing text still says 'label it ready-fr to admit it'

R4 and §B name every operator-facing line to reword (rejection_line, check header, skill, both explainers) and the generated CLI tree/README.

<!-- fr:journal kind=finding scope=spec id=s-r10-resolved created=2026-11-22T21:35:09+00:00 state=fixed resolves=s-r10 -->
### s-r10-resolved · finding [fixed] · resolves s-r10: `pr_view` does not carry what a `PullRequest` needs, and the cited lines are not the CLI and REST clients

§F builds the PullRequest from the view_issue record (number, url, title) plus pr_view (state, draft, head_ref); merged_at/created_at/author stay None; citations corrected.

<!-- fr:journal kind=finding scope=spec id=s-r11-resolved created=2026-11-22T21:35:09+00:00 state=fixed resolves=s-r11 -->
### s-r11-resolved · finding [fixed] · resolves s-r11: R1 says dedupe shows withheld issues by key, but R6/§C remove them from dedupe

R1 drops dedupe and covers the untrusted_digests set too.

<!-- fr:journal kind=finding scope=spec id=s-r12-resolved created=2026-11-22T21:35:09+00:00 state=fixed resolves=s-r12 -->
### s-r12-resolved · finding [fixed] · resolves s-r12: §E counts `batch_drive.py:2039` as a dependency test; it is an assignment

§E names batch.py:410, batch_drive.py:2063, views.py:612 (plus the :405 docstring and :614 wording); 2039 stays.

<!-- fr:journal kind=finding scope=spec id=s-r13-resolved created=2026-11-22T21:35:09+00:00 state=fixed resolves=s-r13 -->
### s-r13-resolved · finding [fixed] · resolves s-r13: The admit read reuses the claim read's comments, but `_comment_facts` neither returns them nor tolerates a failure

§B splits `_comment_facts`: one fetch per issue serving claim and admit reads; a claim-read failure keeps today's repo skip, an admit-only failure stays on that issue (admit_read False). §D: read_claims fills untrusted_authors.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-22T21:35:12+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  batch-obsolete-stage: none
  claim-untrusted-warning: none
  collect-past-limit-pr: none
  dedupe-set-apart: none
  intake-admit-pinned: none
  intake-title-withheld: none
  issues-page-filter-guard: none
  privacy-snapshot-keys: none
row_kinds:
  batch-obsolete-stage: none
  claim-untrusted-warning: none
  collect-past-limit-pr: none
  dedupe-set-apart: none
  intake-admit-pinned: none
  intake-title-withheld: none
  issues-page-filter-guard: none
  privacy-snapshot-keys: none
run_gate: developer
run_kind: none
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-22-triage-hardening-p2 created=2026-11-22T21:38:03+00:00 -->
### phase-split-2026-11-22-triage-hardening-p2 · decision · ask: batches and dedupe (R6, R8-R10) are an ask of their own, reviewable apart from intake

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-22-triage-hardening-p3 created=2026-11-22T21:38:05+00:00 -->
### phase-split-2026-11-22-triage-hardening-p3 · decision · ask: collect PRs past the limit, snapshot privacy keys and the filter-script guard (R11-R13) are an ask of their own

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-22-triage-hardening-p1 created=2026-11-22T21:38:08+00:00 -->
### tier-2026-11-22-triage-hardening-p1 · decision · hard: phase 1 changes the intake trust gate every batch dispatch relies on (ready-fr admission, withheld outside-author text) and the facts schema
