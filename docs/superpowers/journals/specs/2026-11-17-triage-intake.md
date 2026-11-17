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
