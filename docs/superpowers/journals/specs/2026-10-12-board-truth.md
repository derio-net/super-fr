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

<!-- fr:journal kind=finding scope=spec id=spec-r1 created=2026-10-12T06:11:24+00:00 state=open review_scope=in -->
### spec-r1 · finding [open] (reviewer: in scope) · §C/R5: ignored config keys live only in CollectStats, not facts.json

CollectStats.ignored (collect.py:425-436) is transient; Facts (model.py:520-552) has no field and only facts.to_json() is written (triage_cmd.py:475-477), so skew_banner(facts) and check's config_ignored had nothing to read.

<!-- fr:journal kind=finding scope=spec id=spec-r2 created=2026-10-12T06:11:24+00:00 state=open review_scope=in -->
### spec-r2 · finding [open] (reviewer: in scope) · §C: check JSON has no existing skipped list

CheckResult.to_json (check.py:188-252) has no skipped key; skipped repos are only printed by collect's _report (triage_cmd.py:378-383).

<!-- fr:journal kind=finding scope=spec id=spec-r3 created=2026-10-12T06:11:24+00:00 state=open review_scope=in -->
### spec-r3 · finding [open] (reviewer: in scope) · §A/R1: batch= guard does not separate releasing-batch from bare own-claim releases

Every claim_sync release passes batch=op.batch (claim_sync.py:191-199), including own-claim releases for members dropped by batch edit --remove-issue (claims.py:361-364); only cancel unlabels (triage_batch_cmd.py:833).

<!-- fr:journal kind=finding scope=spec id=spec-r4 created=2026-10-12T06:11:24+00:00 state=open review_scope=in -->
### spec-r4 · finding [open] (reviewer: in scope) · §A: claim release and scope retire call release without batch=

triage_claim_cmd.py:308-318 and :376-385 pass no batch; the spec listed claim release as covered and batch merge as a release path, which it is not.

<!-- fr:journal kind=finding scope=spec id=spec-r5 created=2026-10-12T06:11:24+00:00 state=open review_scope=in -->
### spec-r5 · finding [open] (reviewer: in scope) · §A: _remove_label's re-read restores only fr:claimed

claim_writes.py:67-73 re-adds only FR_CLAIMED after a foreign claim appears; a combined edit could strip a foreign fr:in-progress.

<!-- fr:journal kind=finding scope=spec id=spec-r6 created=2026-10-12T06:11:24+00:00 state=open review_scope=in -->
### spec-r6 · finding [open] (reviewer: in scope) · R2/§B: held defined as fr:claimed present misreports this scope's own pending release

A closed issue's fr:claimed is often this scope's own claim awaiting release; collect reads no closed issue comments (collect.py:739-745).

<!-- fr:journal kind=finding scope=spec id=spec-r7 created=2026-10-12T06:11:24+00:00 state=open review_scope=in -->
### spec-r7 · finding [open] (reviewer: in scope) · §B: clean-labels acts on cached facts without a re-read

Facts are always older than the verb's start; a reopened or newly claimed target could lose a live label. claim_writes convention re-reads before writing.

<!-- fr:journal kind=finding scope=spec id=spec-r8 created=2026-10-12T06:11:24+00:00 state=open review_scope=in -->
### spec-r8 · finding [open] (reviewer: in scope) · §B: failure and truncation of the extra closed-issue call unspecified

Inside the per-repo try (collect.py:539-558) a diagnostic read failure would skip the whole repo, which is #1109's failure; no truncation warning was specified.

<!-- fr:journal kind=finding scope=spec id=spec-r9 created=2026-10-12T06:11:24+00:00 state=open review_scope=in -->
### spec-r9 · finding [open] (reviewer: in scope) · R9 presence rules contradict R11's never-link-absent rule

batches-without-board.html, origins-facts-without-origins.html and History-always would link missing pages.

<!-- fr:journal kind=finding scope=spec id=spec-r10 created=2026-10-12T06:11:24+00:00 state=open review_scope=in -->
### spec-r10 · finding [open] (reviewer: in scope) · §F: current page must count as present on first render; pages_present must not need judgements

architecture/origins compute keys before writing (triage_architecture_cmd.py:113-124, triage_origins_cmd.py:185-186); origins may render with judgements None.

<!-- fr:journal kind=finding scope=spec id=spec-r11 created=2026-10-12T06:11:24+00:00 state=open review_scope=in -->
### spec-r11 · finding [open] (reviewer: in scope) · §F: nav rewrite must be atomic and skip identical navs

Driver pass and kanban --watch render every interval (triage_batch_cmd.py:3672-3676, triage_kanban_cmd.py:430-469); pages are written with plain write_text.

<!-- fr:journal kind=finding scope=spec id=spec-r12 created=2026-10-12T06:11:24+00:00 state=open review_scope=in -->
### spec-r12 · finding [open] (reviewer: in scope) · §F/R10: published board.html would carry relative nav links that 404

publish_board publishes board.html alone (scope_config.py:182-203).

<!-- fr:journal kind=finding scope=spec id=spec-r13 created=2026-10-12T06:11:24+00:00 state=open review_scope=in -->
### spec-r13 · finding [open] (reviewer: in scope) · R6 says known, but show_closeout_jump is true for unknown

kanban.py:419-421,456.

<!-- fr:journal kind=finding scope=spec id=spec-r14 created=2026-10-12T06:11:24+00:00 state=open review_scope=in -->
### spec-r14 · finding [open] (reviewer: in scope) · Decision q3 'everywhere' vs collect-only; dispatch still strict

_fresh_config(lenient=False) (triage_batch_cmd.py:963-1002), batch_dispatch.py:238-253.

<!-- fr:journal kind=finding scope=spec id=spec-r15 created=2026-10-12T06:11:24+00:00 state=open review_scope=in -->
### spec-r15 · finding [open] (reviewer: in scope) · §C names collect_facts; lenient lives on collect_facts_counted and collect_into

collect.py:486-499, triage_cmd.py:428,472, driver call triage_batch_cmd.py:2390.

<!-- fr:journal kind=finding scope=spec id=spec-r16 created=2026-10-12T06:11:24+00:00 state=open review_scope=in -->
### spec-r16 · finding [open] (reviewer: in scope) · §B: label filter crosses GhClient protocol and every adapter; closedAt not in ISSUE_LIST_FIELDS

ghclient.py:315-319,449; gh.py:485-511; real_ghrestclient.py:606-614.

<!-- fr:journal kind=finding scope=spec id=spec-r17 created=2026-10-12T06:11:24+00:00 state=open review_scope=in -->
### spec-r17 · finding [open] (reviewer: in scope) · R12: fr-triage SKILL.md is at the 120-line cap; mirrors need regenerating

SKILL.md is 120 lines; sync-opencode.py and sync-hermes.py.

<!-- fr:journal kind=finding scope=spec id=spec-r18 created=2026-10-12T06:11:24+00:00 state=open review_scope=out -->
### spec-r18 · finding [open] (reviewer: out of scope) · Background line references drifted by a few lines

collect.py:541, kanban_render.py:290-317, collect.py:552-557, components.py:49-64.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-10-12T06:11:24+00:00 -->
### spec-review-1 · review · Spec review of 2026-10-12-board-truth

18 findings raised by fr-spec-reviewer: spec-r1..spec-r17 in scope (all fixed in the spec), spec-r18 out of scope (cosmetic line drift).

<!-- fr:journal kind=finding scope=spec id=spec-r1-resolved created=2026-10-12T06:11:24+00:00 state=fixed resolves=spec-r1 -->
### spec-r1-resolved · finding [fixed] · resolves spec-r1: §C/R5: ignored config keys live only in CollectStats, not facts.json

Added Facts.config_ignored (schema 9) written by collect; §B lists it, §C writes it.

<!-- fr:journal kind=finding scope=spec id=spec-r2-resolved created=2026-10-12T06:11:24+00:00 state=fixed resolves=spec-r2 -->
### spec-r2-resolved · finding [fixed] · resolves spec-r2: §C: check JSON has no existing skipped list

check JSON gains skipped and config_ignored (and closed_in_progress) with matching text sections (§B, R5).

<!-- fr:journal kind=finding scope=spec id=spec-r3-resolved created=2026-10-12T06:11:24+00:00 state=fixed resolves=spec-r3 -->
### spec-r3-resolved · finding [fixed] · resolves spec-r3: §A/R1: batch= guard does not separate releasing-batch from bare own-claim releases

release gains unlabel=; claim_sync.execute passes unlabel=True on every release (all are claims no live batch owes, incl. removed members); R1 and §A rewritten, cancel sentence corrected.

<!-- fr:journal kind=finding scope=spec id=spec-r4-resolved created=2026-10-12T06:11:24+00:00 state=fixed resolves=spec-r4 -->
### spec-r4-resolved · finding [fixed] · resolves spec-r4: §A: claim release and scope retire call release without batch=

R1/§A now state claim release and scope retire keep unlabel=False, leaving closed ones to R2/R3 and open ones to the stale-dispatch set; batch merge claim removed.

<!-- fr:journal kind=finding scope=spec id=spec-r5-resolved created=2026-10-12T06:11:24+00:00 state=fixed resolves=spec-r5 -->
### spec-r5-resolved · finding [fixed] · resolves spec-r5: §A: _remove_label's re-read restores only fr:claimed

§A: the re-read restores every label it removed when a foreign claim appeared.

<!-- fr:journal kind=finding scope=spec id=spec-r6-resolved created=2026-10-12T06:11:24+00:00 state=fixed resolves=spec-r6 -->
### spec-r6-resolved · finding [fixed] · resolves spec-r6: R2/§B: held defined as fr:claimed present misreports this scope's own pending release

R2/§B: three states stale | release-pending | held, decided by reading comments of closed hits carrying fr:claimed.

<!-- fr:journal kind=finding scope=spec id=spec-r7-resolved created=2026-10-12T06:11:24+00:00 state=fixed resolves=spec-r7 -->
### spec-r7-resolved · finding [fixed] · resolves spec-r7: §B: clean-labels acts on cached facts without a re-read

R3/§B: clean-labels re-reads each target before writing and skips reopened or newly claimed ones; vacuous freshness warning dropped.

<!-- fr:journal kind=finding scope=spec id=spec-r8-resolved created=2026-10-12T06:11:24+00:00 state=fixed resolves=spec-r8 -->
### spec-r8-resolved · finding [fixed] · resolves spec-r8: §B: failure and truncation of the extra closed-issue call unspecified

§B: the closed-issue list is best-effort outside the skip try (warning + empty set) with a Truncation warning at the limit.

<!-- fr:journal kind=finding scope=spec id=spec-r9-resolved created=2026-10-12T06:11:24+00:00 state=fixed resolves=spec-r9 -->
### spec-r9-resolved · finding [fixed] · resolves spec-r9: R9 presence rules contradict R11's never-link-absent rule

R9 now: present = file exists, or the page being rendered now; no other rule.

<!-- fr:journal kind=finding scope=spec id=spec-r10-resolved created=2026-10-12T06:11:24+00:00 state=fixed resolves=spec-r10 -->
### spec-r10-resolved · finding [fixed] · resolves spec-r10: §F: current page must count as present on first render; pages_present must not need judgements

§F: pages_present(state_dir, current) always includes current and needs no judgements.

<!-- fr:journal kind=finding scope=spec id=spec-r11-resolved created=2026-10-12T06:11:24+00:00 state=fixed resolves=spec-r11 -->
### spec-r11-resolved · finding [fixed] · resolves spec-r11: §F: nav rewrite must be atomic and skip identical navs

R11/§F: rewrite via write_text_atomic, skipped when the nav already matches.

<!-- fr:journal kind=finding scope=spec id=spec-r12-resolved created=2026-10-12T06:11:24+00:00 state=fixed resolves=spec-r12 -->
### spec-r12-resolved · finding [fixed] · resolves spec-r12: §F/R10: published board.html would carry relative nav links that 404

R10/§F: the publish step hands a temp copy of board.html with the nav stripped.

<!-- fr:journal kind=finding scope=spec id=spec-r13-resolved created=2026-10-12T06:11:24+00:00 state=fixed resolves=spec-r13 -->
### spec-r13-resolved · finding [fixed] · resolves spec-r13: R6 says known, but show_closeout_jump is true for unknown

R6/§D: the front follows the close-out only when its status is set and not absent/unknown, narrower than show_closeout_jump.

<!-- fr:journal kind=finding scope=spec id=spec-r14-resolved created=2026-10-12T06:11:24+00:00 state=fixed resolves=spec-r14 -->
### spec-r14-resolved · finding [fixed] · resolves spec-r14: Decision q3 'everywhere' vs collect-only; dispatch still strict

R4/§C extended to every triage config read: _fresh_config and batch_dispatch default to lenient (the operator's chosen option said every collect; dispatch reads the same file and the same skew refuses it, so lenient there is in the decision's spirit).

<!-- fr:journal kind=finding scope=spec id=spec-r15-resolved created=2026-10-12T06:11:24+00:00 state=fixed resolves=spec-r15 -->
### spec-r15-resolved · finding [fixed] · resolves spec-r15: §C names collect_facts; lenient lives on collect_facts_counted and collect_into

§C names collect_facts_counted, collect_into and the driver call site.

<!-- fr:journal kind=finding scope=spec id=spec-r16-resolved created=2026-10-12T06:11:24+00:00 state=fixed resolves=spec-r16 -->
### spec-r16-resolved · finding [fixed] · resolves spec-r16: §B: label filter crosses GhClient protocol and every adapter; closedAt not in ISSUE_LIST_FIELDS

§B lists the full chain and the closedAt field via ORIGINS_ISSUE_LIST_FIELDS.

<!-- fr:journal kind=finding scope=spec id=spec-r17-resolved created=2026-10-12T06:11:24+00:00 state=fixed resolves=spec-r17 -->
### spec-r17-resolved · finding [fixed] · resolves spec-r17: R12: fr-triage SKILL.md is at the 120-line cap; mirrors need regenerating

R12 states the 120-line cap and both mirror syncs.

<!-- fr:journal kind=finding scope=spec id=spec-r18-resolved created=2026-10-12T06:11:24+00:00 state=open resolves=spec-r18 out_of_scope=true -->
### spec-r18-resolved · finding [out-of-scope] · resolves spec-r18: Background line references drifted by a few lines

Cosmetic line-number drift in Background; the code cited is right. The rewritten Background already uses the corrected numbers, but the finding asks for no design change.
