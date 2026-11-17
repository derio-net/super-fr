<!-- fr:journal-schema=4 -->
# Journal: 2026-11-17-triage-intake

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-17T09:11:00+00:00 input=true -->
### brief · discovery · operator brief (batch triage-intake launch brief), verbatim

/fr-goal Triage intake trust and driver correctness

Batch `triage-intake` of derio-net/super-fr: 4 issues, delivered as ONE pull request.

## super-fr#1252: Wave driver: gate batch eligibility on issue author trust
Batch eligibility has no author-trust gate. `author_association` is read only for claim markers (`packages/fr/src/fr/triage/claims.py:42`), and `triage/batch_dispatch.py` does not mark issue text as untrusted. On a public repo an outside account's issue can still reach an implementing session's brief. Still live.
Note: This is a security boundary. Rank it ahead of the other triage-batches work.

## super-fr#1213: MergeContext cached across passes: a later-unreachable origin is not re-fetched
`merge_ctx` (`packages/fr/src/fr/commands/triage_batch_cmd.py:4004`, was ~3573) caches the `MergeContext` per repo for the driver's lifetime. `_fresh_config` and the checkout setup run only on first creation. `ci_none` and `rules` are refreshed each pass, but nothing re-fetches origin, so later passes can act on stale refs instead of holding. Still live.

## super-fr#1406: triage batch cancel fails when the member's repo has no fr:in-progress label
Still live: cancel calls `edit_issue_labels(..., remove={fr:in-progress})` without condition (`commands/triage_batch_cmd.py:972-974`). That goes to `gh.swap_issue_labels` (`gh.py:407-425`, plain `gh issue edit --remove-label`), which errors when the repo does not define the label. Nothing treats 'not found' as already removed, so cancel never converges.
Note: The side asks (the dry run naming `--checkout`; a never-dispatched batch needing no checkout) could be split out. Shares the label-lifecycle area with super-fr#1268.

## super-fr#1299: non-forge exceptions escape close_gate_trackers and could crash the driver after the pass
Live: `close_gate_trackers` (`packages/fr/src/fr/gatebackfill/close.py:346`) catches only `_FAILURES = (*FORGE_ERRORS, UnsupportedForgeOperation)` (:35). An `OSError` or `ValueError` from `EvidenceReader`/`_one` escapes into the driver's `_gate_pass` (`packages/fr/src/fr/commands/triage_batch_cmd.py:5534`) after the gate label is already written. The pass is not reversed, but the driver pass can crash.

## Why these belong together
Security: no author-trust gate on batch eligibility (#1252). Changes the driver itself, so it runs after the other truth fixes. triage_batch_cmd.py.

## Delivery rules
- Work on branch `feat/batch-triage-intake`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1252
  Closes derio-net/super-fr#1213
  Closes derio-net/super-fr#1406
  Closes derio-net/super-fr#1299
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

Never add the `approved-fr` label: it is the operator's approval to merge, and fr voids it on your next push.

<!-- fr:journal kind=decision scope=spec id=d1-trust-label created=2026-11-17T09:11:00+00:00 decided_by=operator -->
### d1-trust-label · decision · the operator trust label is `ready-fr`

Operator answer (round 1 q1). Named like `approved-fr`; the `fr:` prefix stays for engine-set labels. GitHub lets only triage-or-higher accounts add labels, so the label's presence is the proof.

<!-- fr:journal kind=decision scope=spec id=d2-untrusted-text created=2026-11-17T09:11:00+00:00 decided_by=operator -->
### d2-untrusted-text · decision · an ineligible issue is set apart and its body withheld from facts.json

Operator answer (round 1 q2). collect keeps the title but stores no body; `fr triage check` lists an `untrusted` set with the reason; never ranked, unplaced or suggested; the triage agent never reads the body.

<!-- fr:journal kind=decision scope=spec id=d3-cancel-scope created=2026-11-17T09:11:00+00:00 decided_by=operator -->
### d3-cancel-scope · decision · #1406 scope: core convergence fix plus the dry run naming --checkout; no-checkout cancel is a follow-up

Operator answer (round 1 q3). The gh#803 tracking gate stays; a never-dispatched batch cancelling with no checkout is filed as a follow-up.

<!-- fr:journal kind=decision scope=spec id=d4-verification created=2026-11-17T09:11:00+00:00 decided_by=operator -->
### d4-verification · decision · verification: strategy candidate (smoke), gate developer, every row none — CI tests, no Test Plan

Operator answer (round 1 q4). Nothing here needs a released build to show.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-17T09:11:00+00:00 lens=security step=brainstorm -->
### lens-security-1 · lens · #1252 adds a trust boundary on issue intake and the launch brief; it must fail closed

<!-- fr:journal kind=finding scope=spec id=s-r1 created=2026-11-17T09:19:01+00:00 state=open review_scope=in -->
### s-r1 · finding [open] (reviewer: in scope) · R6 driver hold: the awaiting-live analogue emits `held`, not `blocked`; the design does not say which the untrusted hold is

The design cited awaiting-live's `held` path as if it emitted `blocked` (batch_drive.py:1981-1999); the kind and its summary effect were unspecified.

<!-- fr:journal kind=finding scope=spec id=s-r2 created=2026-11-17T09:19:01+00:00 state=open review_scope=in -->
### s-r2 · finding [open] (reviewer: in scope) · Snapshot.untrusted is built only in Driver.snapshot; the board and `drive --plan` would still show the batch dispatching

views.drive_snapshot (views.py:104,152) builds its own Snapshot from facts.

<!-- fr:journal kind=finding scope=spec id=s-r3 created=2026-11-17T09:19:01+00:00 state=open review_scope=in -->
### s-r3 · finding [open] (reviewer: in scope) · R3 body withholding does not hold for carried issues of a partial collect or for the view_issue path

collect.py:722-769 carry and view paths bypassed the verdict.

<!-- fr:journal kind=finding scope=spec id=s-r4 created=2026-11-17T09:19:01+00:00 state=open review_scope=in -->
### s-r4 · finding [open] (reviewer: in scope) · R1's per-issue association read costs O(outside issues) API calls on every collect, i.e. every driver pass; one list read already carries the field

Per-issue reads scale with outside issues on a per-pass path.

<!-- fr:journal kind=finding scope=spec id=s-r5 created=2026-11-17T09:19:01+00:00 state=open review_scope=in -->
### s-r5 · finding [open] (reviewer: in scope) · R2's fail-closed sentence contradicts R1's lazy read

As written, every login- or label-admitted issue would be ineligible.

<!-- fr:journal kind=finding scope=spec id=s-r6 created=2026-11-17T09:19:01+00:00 state=open review_scope=in -->
### s-r6 · finding [open] (reviewer: in scope) · §B per-pass check: `_fresh_config` always fetches; a failed check's in-pass state is undefined; a direct merge_ctx caller bypasses the hold

Three gaps that decided whether R9 holds.

<!-- fr:journal kind=finding scope=spec id=s-r7 created=2026-11-17T09:19:01+00:00 state=open review_scope=in -->
### s-r7 · finding [open] (reviewer: in scope) · The cached MergeContext keeps creation-time `version` and merge `method` while R9 re-validates the config each pass

Context fields set only at creation (triage_batch_cmd.py:4011-4031).

<!-- fr:journal kind=finding scope=spec id=s-r8 created=2026-11-17T09:19:01+00:00 state=open review_scope=in -->
### s-r8 · finding [open] (reviewer: in scope) · §C dry-run warning: `_open_checkout` never raises TriageError; it exits 2

`_open_checkout` calls `_fail`, which raises typer.Exit(2).

<!-- fr:journal kind=finding scope=spec id=s-r9 created=2026-11-17T09:19:01+00:00 state=open review_scope=in -->
### s-r9 · finding [open] (reviewer: in scope) · R10 retries only once, and the design does not state the no-partial-write assumption the retry relies on

A single retry fails when two removal labels are undefined.

<!-- fr:journal kind=finding scope=spec id=s-r10 created=2026-11-17T09:19:01+00:00 state=open review_scope=in -->
### s-r10 · finding [open] (reviewer: in scope) · `ready-fr` is not bound to the issue's content: an outside author can edit the title or body after an operator admits it

Accepted as a documented residual risk under d1 rather than silent.

<!-- fr:journal kind=finding scope=spec id=s-r11 created=2026-11-17T09:19:01+00:00 state=open review_scope=in -->
### s-r11 · finding [open] (reviewer: in scope) · The brief's `/fr-goal <batch.title>` line and `rationale` stay outside the untrusted block, but the triage agent writes them from issue text

Agent-written fields were left unmarked in the most instruction-like position.

<!-- fr:journal kind=finding scope=spec id=s-r12 created=2026-11-17T09:19:01+00:00 state=open review_scope=in -->
### s-r12 · finding [open] (reviewer: in scope) · R5's edit refusal and the dispatch-vs-driver member rule differ from the design

Requirement and design disagreed; two refusal paths could judge one batch differently.

<!-- fr:journal kind=finding scope=spec id=s-r13 created=2026-11-17T09:19:01+00:00 state=open review_scope=in -->
### s-r13 · finding [open] (reviewer: in scope) · Who creates the `ready-fr` label is left vague; a triage-permission operator cannot create a missing label

There was no generic operator-label ensurer.

<!-- fr:journal kind=finding scope=spec id=s-r14 created=2026-11-17T09:19:01+00:00 state=open review_scope=in -->
### s-r14 · finding [open] (reviewer: in scope) · Several Background citations are off by a line or name the wrong field list

Citation drift.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-17T09:19:01+00:00 -->
### spec-review-1 · review · independent spec review: 14 findings

fr-spec-reviewer raised s-r1..s-r14, all in scope; all fixed in the spec. Decisions d1-d4 honoured. Suggested lenses: security (already added at brainstorm) and tests (added here).

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-17T09:19:01+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · R6 and R9 need multi-pass and snapshot-builder-parity tests

<!-- fr:journal kind=finding scope=spec id=s-r1-resolved created=2026-11-17T09:19:01+00:00 state=fixed resolves=s-r1 -->
### s-r1-resolved · finding [fixed] · resolves s-r1: R6 driver hold: the awaiting-live analogue emits `held`, not `blocked`; the design does not say which the untrusted hold is

R6/§A now specify `Action("blocked", reason)`, counted as blocked so the drive stalls for the operator, placed before the `after` and in-flight-cap checks; the analogy is gone.

<!-- fr:journal kind=finding scope=spec id=s-r2-resolved created=2026-11-17T09:19:01+00:00 state=fixed resolves=s-r2 -->
### s-r2-resolved · finding [fixed] · resolves s-r2: Snapshot.untrusted is built only in Driver.snapshot; the board and `drive --plan` would still show the batch dispatching

§A: `Snapshot.rejected` is filled by both builders (`Driver.snapshot` and `views.drive_snapshot`) from one `rejected_members`; the row tests the builders agree.

<!-- fr:journal kind=finding scope=spec id=s-r3-resolved created=2026-11-17T09:19:01+00:00 state=fixed resolves=s-r3 -->
### s-r3-resolved · finding [fixed] · resolves s-r3: R3 body withholding does not hold for carried issues of a partial collect or for the view_issue path

R3 and §A Body: every issue collect writes, listed, viewed or carried, is judged in one final step and its body cleared when ineligible; a schema-13 carried issue is cleared on the first collect after the upgrade; the row covers the partial and view paths.

<!-- fr:journal kind=finding scope=spec id=s-r4-resolved created=2026-11-17T09:19:01+00:00 state=fixed resolves=s-r4 -->
### s-r4-resolved · finding [fixed] · resolves s-r4: R1's per-issue association read costs O(outside issues) API calls on every collect, i.e. every driver pass; one list read already carries the field

R1/§A The read: at most one extra read per repo per collect (one paginated `gh api repos/{r}/issues` read on the gh CLI client), none under REST (the list record keeps `authorAssociation`) or when every issue is admitted.

<!-- fr:journal kind=finding scope=spec id=s-r5-resolved created=2026-11-17T09:19:01+00:00 state=fixed resolves=s-r5 -->
### s-r5-resolved · finding [fixed] · resolves s-r5: R2's fail-closed sentence contradicts R1's lazy read

R2 reworded: an issue no clause admits is ineligible; an unread author or association never admits. The row covers trusted-login-with-unread-association as eligible.

<!-- fr:journal kind=finding scope=spec id=s-r6-resolved created=2026-11-17T09:19:01+00:00 state=fixed resolves=s-r6 -->
### s-r6-resolved · finding [fixed] · resolves s-r6: §B per-pass check: `_fresh_config` always fetches; a failed check's in-pass state is undefined; a direct merge_ctx caller bypasses the hold

§B: `_fresh_config` split into fetch and `_config_fresh`; `_ctx_held` makes a failed repo held for the rest of the pass (marked checked only on success); `_closeout_hand_back` goes through `_ctx_or_hold`.

<!-- fr:journal kind=finding scope=spec id=s-r7-resolved created=2026-11-17T09:19:01+00:00 state=fixed resolves=s-r7 -->
### s-r7-resolved · finding [fixed] · resolves s-r7: The cached MergeContext keeps creation-time `version` and merge `method` while R9 re-validates the config each pass

R9/§B step 4: `version` and `method` follow each pass's config (method recomputed over the allowed methods stored at build, no forge read); the row tests a config change between passes.

<!-- fr:journal kind=finding scope=spec id=s-r8-resolved created=2026-11-17T09:19:01+00:00 state=fixed resolves=s-r8 -->
### s-r8-resolved · finding [fixed] · resolves s-r8: §C dry-run warning: `_open_checkout` never raises TriageError; it exits 2

§C: a non-exiting `_checkout_refusal` shared by `_open_checkout` and the dry run, so the warning and the `--yes` refusal come from one check (R11).

<!-- fr:journal kind=finding scope=spec id=s-r9-resolved created=2026-11-17T09:19:01+00:00 state=fixed resolves=s-r9 -->
### s-r9-resolved · finding [fixed] · resolves s-r9: R10 retries only once, and the design does not state the no-partial-write assumption the retry relies on

§C: loops while gh names a further remove label (at most len(remove) retries); the gh resolve-before-mutate assumption is stated and documented in the docstring; the row adds a two-missing-labels case.

<!-- fr:journal kind=finding scope=spec id=s-r10-resolved created=2026-11-17T09:19:01+00:00 state=fixed resolves=s-r10 -->
### s-r10-resolved · finding [fixed] · resolves s-r10: `ready-fr` is not bound to the issue's content: an outside author can edit the title or body after an operator admits it

R8 now requires the docs to state the residual risk (the label admits later edits; R7's quoting still applies), and Out of scope records why voiding is not done (a timeline read per labelled issue).

<!-- fr:journal kind=finding scope=spec id=s-r11-resolved created=2026-11-17T09:19:01+00:00 state=fixed resolves=s-r11 -->
### s-r11-resolved · finding [fixed] · resolves s-r11: The brief's `/fr-goal <batch.title>` line and `rationale` stay outside the untrusted block, but the triage agent writes them from issue text

R7/§A Brief: the first line is the skill command and batch id only; batch title and rationale move inside the quoted untrusted block.

<!-- fr:journal kind=finding scope=spec id=s-r12-resolved created=2026-11-17T09:19:01+00:00 state=fixed resolves=s-r12 -->
### s-r12-resolved · finding [fixed] · resolves s-r12: R5's edit refusal and the dispatch-vs-driver member rule differ from the design

R5/R6: one member rule (`rejected_members`: ineligible whether open or closed; absent from facts = `not collected`) used by create, edit (on the batch it would write), dispatch and both snapshot builders; an edit removing the last rejected member succeeds.

<!-- fr:journal kind=finding scope=spec id=s-r13-resolved created=2026-11-17T09:19:01+00:00 state=fixed resolves=s-r13 -->
### s-r13-resolved · finding [fixed] · resolves s-r13: Who creates the `ready-fr` label is left vague; a triage-permission operator cannot create a missing label

R8/§A: the driver ensures `ready-fr` beside `approved-fr` in approval.py's ensure step and reports when it cannot; the docs say a write-permission operator creates it where fr has not.

<!-- fr:journal kind=finding scope=spec id=s-r14-resolved created=2026-11-17T09:19:01+00:00 state=fixed resolves=s-r14 -->
### s-r14-resolved · finding [fixed] · resolves s-r14: Several Background citations are off by a line or name the wrong field list

Citations corrected: close.py:359/:36, triage_batch_cmd.py:895/:749, collect.py:61 ISSUE_FIELDS with the reason (gh's issue JSON has no association field).

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-17T09:19:02+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  cancel-converges-undefined-label: none
  cancel-dry-run-names-checkout: none
  driver-refetches-origin-each-pass: none
  gate-trackers-contain-errors: none
  intake-batch-refuses-untrusted: none
  intake-brief-quotes-untrusted: none
  intake-trust-eligibility: none
  intake-untrusted-set-apart: none
row_kinds:
  cancel-converges-undefined-label: none
  cancel-dry-run-names-checkout: none
  driver-refetches-origin-each-pass: none
  gate-trackers-contain-errors: none
  intake-batch-refuses-untrusted: none
  intake-brief-quotes-untrusted: none
  intake-trust-eligibility: none
  intake-untrusted-set-apart: none
run_gate: developer
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-17-triage-intake-p2 created=2026-11-17T09:21:40+00:00 -->
### phase-split-2026-11-17-triage-intake-p2 · decision · ask: #1213 (R9), the driver's per-pass fetch, an independently reviewable driver change
