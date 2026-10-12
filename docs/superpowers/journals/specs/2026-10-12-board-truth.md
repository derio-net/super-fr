# Journal: 2026-10-12-board-truth

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-12T05:58:46+00:00 input=true -->
### operator-brief · discovery · Batch board-truth dispatch brief (verbatim)

/fr-goal Triage board and labels that tell the truth

Batch `board-truth` of derio-net/super-fr: 5 issues, delivered as ONE pull request.

## super-fr#1085: fr:in-progress is never removed when a batch finishes: 197 closed issues still say an agent is working on them
`FR_IN_PROGRESS` is removed only on the cancel path (`triage_batch_cmd.py:755-793`); a merged batch leaves the label on (197 closed issues). Held by scope `s-c8805331` (its driver stopped refreshing 2026-10-09 ~20:05 UTC; operator released these to this scope 2026-10-10).

## super-fr#1065: the card front shows the batch session's pill, so an idle close-out card reads the wrong session's status
Close-out card shows the batch session's pill. Held by scope `s-c8805331` (its driver stopped refreshing 2026-10-09 ~20:05 UTC; operator released these to this scope 2026-10-10) (batch `cancelled-batch-state`).
Note: Also fix the Jump button (operator, 2026-10-11, see the issue comment): the card front builds Jump with closeout=False (`kanban_render.py:307`), so during a close-out it focuses the batch session. While a close-out session is live, the front pill AND Jump follow the close-out (`--closeout`); the batch session's jump moves into the body.

## super-fr#1109: Triage collector/schema skew can make an active batch unreachable
Collector/config schema skew drops an active batch to unreachable. Held by scope `s-c8805331` (its driver stopped refreshing 2026-10-09 ~20:05 UTC; operator released these to this scope 2026-10-10).

## super-fr#1111: Cancelled batches still render as Running and immediately owe released claims
**Probably fixed on main** by ce7974a2 (#1115, 2026-10-10): `derive_batch_stage` now folds only dispatch/cancel events (`lifecycle_events`, `batch.py:254-266`), so a trailing `claims_released` audit no longer hides the cancel, and `releasing()` drops cancelled batches from claims owed (`claims.py`). Confirm with one cancel walk, then close.
Note: Close after a cancel walk: `gh issue close 1111 --repo derio-net/super-fr --comment "Fixed by #1115: stage derivation folds lifecycle events only."`

## super-fr#1122: triage pages: the nav lists pages the scope doesn't have (origins/architecture 404 on org scopes) and omits the batch board
Filed from this scope. `page_header()` (`packages/fr/src/fr/triage/components.py:264-277`) renders the fixed four-entry `PAGES` tuple (:50-64), so org scopes link to origins/architecture pages that never exist, and `board.html` is not a tab (only linked at `render.py:754`).

## Why these belong together
fr:in-progress never removed, wrong card pill, schema skew hides batches, nav lists absent pages; verify #1111 (likely fixed by #1115) and close it. Held members taken over from the inactive scope s-c8805331 at the operator's request, 2026-10-10.

## Delivery rules
- Work on branch `feat/batch-board-truth`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1085
  Closes derio-net/super-fr#1065
  Closes derio-net/super-fr#1109
  Closes derio-net/super-fr#1111
  Closes derio-net/super-fr#1122
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

Overnight rule (operator via coordinator, 2026-10-12): targeted tests only locally; heavy suites through ~/.cache/fr/coord/testslot.sh; prefer tests: ci; PRs stay drafts, never merged.

<!-- fr:journal kind=decision scope=spec id=q1-unlabel-on-release created=2026-10-12T05:58:46+00:00 -->
### q1-unlabel-on-release · decision · fr:in-progress comes off on release

Operator chose: when this scope releases a member of a releasing batch (cancelled/abandoned/archived), also remove fr:in-progress unless another scope's claim stands (R1).

<!-- fr:journal kind=decision scope=spec id=q2-stale-labels-verb created=2026-10-12T05:58:46+00:00 -->
### q2-stale-labels-verb · decision · Closed-but-in-progress check set plus a --yes cleanup verb

Operator chose a check/board set plus a `fr triage` verb that removes the labels with --yes, over a printed command only or a one-off run (R2, R3).

<!-- fr:journal kind=decision scope=spec id=q3-lenient-collect created=2026-10-12T05:58:46+00:00 -->
### q3-lenient-collect · decision · Every collect reads triage config leniently, skew shown as a banner

Operator chose lenient reads everywhere plus a prominent scope banner for ignored keys and skipped repos; no stale-facts carrying (R4, R5).

<!-- fr:journal kind=decision scope=spec id=q4-page-names created=2026-10-12T05:58:46+00:00 -->
### q4-page-names · decision · Backlog (triage.html) + Batches (board.html)

Operator chose the rename that removes the Board clash (R12).

<!-- fr:journal kind=decision scope=spec id=q5-nav-rewrite created=2026-10-12T05:58:46+00:00 -->
### q5-nav-rewrite · decision · Every render rewrites all existing pages' navs

Operator chose a registry deciding presence from the state dir and an in-place nav rewrite of every existing page (R9-R11).

<!-- fr:journal kind=decision scope=spec id=q6-1111-tests created=2026-10-12T05:58:46+00:00 -->
### q6-1111-tests · decision · #1111 confirmed by regression tests, PR Closes it

Operator chose regression tests (unit + scenario) over a live cancel walk; no forge writes (R8).

<!-- fr:journal kind=decision scope=spec id=q7-closeout-front created=2026-10-12T05:58:46+00:00 -->
### q7-closeout-front · decision · Close-out card front exactly per the operator's note

Front pill and Jump follow a live close-out; body gets a real Jump for the other session; no extra pill prefix (R6, R7).

<!-- fr:journal kind=decision scope=spec id=q8-verification created=2026-10-12T05:58:46+00:00 -->
### q8-verification · decision · Verification strategy: candidate

Operator chose candidate walks for the rendering/check rows; label writes and runner statuses are proven by unit tests (spec ## Verification).
