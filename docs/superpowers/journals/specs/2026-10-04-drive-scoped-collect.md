# Journal: 2026-10-04-drive-scoped-collect

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-04T06:00:36+00:00 input=true -->
### operator-brief · discovery · Operator brief (verbatim) — batch drive-scoped-collect, gh#911

/fr-goal Drive collects only what its selected batches need each pass

Batch `drive-scoped-collect` of derio-net/super-fr: 1 issues, delivered as ONE pull request.

## super-fr#911: Drive: every pass re-collects all facts (200+ serial gh issue view calls)
each drive pass re-collects all facts with 200+ serial gh issue view calls

## Why these belong together
Needs a design (scope of the per-pass collect); builds on the read-timeout/retry change

## Delivery rules
- Work on branch `feat/batch-drive-scoped-collect`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#911
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

Issue body (gh#911): Found in wave-driver Test Plan item 16 (live two-batch wave, 2026-10-03, during a GitHub API degradation). Each driver pass calls `collect_into`. On this repo that includes one `gh issue view` per judged issue, more than 200 serial calls, so a pass took about 10 minutes against the 120s `--interval`, and every call was another chance to stall (one hung on `gh issue view 625` for over 2 minutes). The driver only needs fresh state for the batches it is acting on: their members, their PRs and the open `chore/*` PRs. Consider a scoped collect for the driver (the selected batches' members and PRs), or reusing unchanged facts between passes.

<!-- fr:journal kind=decision scope=spec id=d1-carry-known-closed created=2026-10-04T06:00:36+00:00 -->
### d1-carry-known-closed · decision · Carry known-closed judged keys over from the previous facts.json

Operator chose carry-over (over scoping views to batch members, or both). A judged key the previous facts show closed is carried, with links recomputed; only keys that just left the open list, were unviewed, or never seen are viewed. facts.json stays complete for the board.

<!-- fr:journal kind=decision scope=spec id=d2-driver-only created=2026-10-04T06:00:36+00:00 -->
### d2-driver-only · decision · Only the driver carries over; fr triage collect stays a full re-read

Operator chose driver-only. collect is the explicit refresh that heals carry-over drift.

<!-- fr:journal kind=decision scope=spec id=d3-every-pass created=2026-10-04T06:00:36+00:00 -->
### d3-every-pass · decision · Every drive pass carries over, the first included

Operator chose every pass with a readable same-scope facts.json; none readable falls back to a full collect.

<!-- fr:journal kind=decision scope=spec id=d4-cost-line created=2026-10-04T06:00:36+00:00 -->
### d4-cost-line · decision · One line per pass naming issues viewed vs carried over

Operator chose a per-pass report line, e.g. "collect - 3 issues viewed, 214 carried over".

<!-- fr:journal kind=finding scope=spec id=sr-truncated-issue-list created=2026-10-04T06:04:21+00:00 state=open review_scope=in -->
### sr-truncated-issue-list · finding [open] (reviewer: in scope) · Carry-over breaks R3 when a repo's open-issue list hit its limit

A judged issue reopened past a truncated open list (len == ISSUE_LIMIT) would stay carried as closed and could stage its batch merged instead of partial. collect.py:376,393-394,431-447. Fix: carry nothing in a repo whose issue list was truncated this pass.

<!-- fr:journal kind=finding scope=spec id=sr-older-schema-not-refused created=2026-10-04T06:04:21+00:00 state=open review_scope=in -->
### sr-older-schema-not-refused · finding [open] (reviewer: in scope) · §B says an older-schema facts.json carries nothing, but load_facts accepts schema 3

model.py:41 FACTS_READS = (3, 4); load_facts refuses only outside it. The spec must say which schemas are carried.

<!-- fr:journal kind=finding scope=spec id=sr-viewed-count-definition created=2026-10-04T06:04:21+00:00 state=open review_scope=in -->
### sr-viewed-count-definition · finding [open] (reviewer: in scope) · R6 'issues viewed' is undefined for failed or PR views, and the counts have no path from collect_into to recollect

Count view_issue calls, failures included. collect_into must return the stats, because recollect only sees collect_into (triage_cmd.py:178, triage_batch_cmd.py:1189).

<!-- fr:journal kind=finding scope=spec id=sr-test-plan-2-no-row created=2026-10-04T06:04:21+00:00 state=open review_scope=in -->
### sr-test-plan-2-no-row · finding [open] (reviewer: in scope) · Test Plan item 2 (check's settled count) has no acceptance row

No row cites Test Plan 2; add a verify: post-merge row.

<!-- fr:journal kind=finding scope=spec id=sr-group-scope-name-collision created=2026-10-04T06:04:21+00:00 state=open review_scope=out -->
### sr-group-scope-name-collision · finding [open] (reviewer: out of scope) · Judgement keys are owner-blind, so two repos with the same name in a group scope collide

collect.py:324 _judged_elsewhere keys by repo name only; model.py:154-156 issue_key drops the owner. This predates the change, and the carried lookup only inherits it.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-10-04T06:04:21+00:00 -->
### spec-review-1 · review · independent spec review: 5 findings (4 in scope, 1 out)

fr-spec-reviewer checked decisions d1-d4 (all honoured), the §2 safety argument against batch.py:163-179, stage.py, check.py:195 and render/views, skipped-repo handling (collect.py:324-331), unviewed handling and the scope/kind match (model.py:314-315). Findings: sr-truncated-issue-list, sr-older-schema-not-refused, sr-viewed-count-definition, sr-test-plan-2-no-row (in); sr-group-scope-name-collision (out).

<!-- fr:journal kind=finding scope=spec id=sr-truncated-issue-list-resolved created=2026-10-04T06:04:21+00:00 state=fixed resolves=sr-truncated-issue-list -->
### sr-truncated-issue-list-resolved · finding [fixed] · resolves sr-truncated-issue-list: Carry-over breaks R3 when a repo's open-issue list hit its limit

Spec §2 and §A now say a repo whose open-issue list was truncated this pass carries nothing; R1 and R3 are reworded, and an engine test is named in §D.

<!-- fr:journal kind=finding scope=spec id=sr-older-schema-not-refused-resolved created=2026-10-04T06:04:21+00:00 state=fixed resolves=sr-older-schema-not-refused -->
### sr-older-schema-not-refused-resolved · finding [fixed] · resolves sr-older-schema-not-refused: §B says an older-schema facts.json carries nothing, but load_facts accepts schema 3

§B now says both readable schemas (FACTS_READS 3 and 4) are carried, since Issue has the same shape; anything load_facts refuses carries nothing.

<!-- fr:journal kind=finding scope=spec id=sr-viewed-count-definition-resolved created=2026-10-04T06:04:21+00:00 state=fixed resolves=sr-viewed-count-definition -->
### sr-viewed-count-definition-resolved · finding [fixed] · resolves sr-viewed-count-definition: R6 'issues viewed' is undefined for failed or PR views, and the counts have no path from collect_into to recollect

R6 and §A now define viewed as view_issue calls, failures and PR answers included. CollectStats comes from collect_facts_counted, and collect_into returns it to recollect (§B).

<!-- fr:journal kind=finding scope=spec id=sr-test-plan-2-no-row-resolved created=2026-10-04T06:04:21+00:00 state=fixed resolves=sr-test-plan-2-no-row -->
### sr-test-plan-2-no-row-resolved · finding [fixed] · resolves sr-test-plan-2-no-row: Test Plan item 2 (check's settled count) has no acceptance row

Added the drive-carry-keeps-settled-set row (verify: post-merge) for Test Plan 2.

<!-- fr:journal kind=finding scope=spec id=sr-group-scope-name-collision-resolved created=2026-10-04T06:04:21+00:00 state=open resolves=sr-group-scope-name-collision out_of_scope=true -->
### sr-group-scope-name-collision-resolved · finding [out-of-scope] · resolves sr-group-scope-name-collision: Judgement keys are owner-blind, so two repos with the same name in a group scope collide

Pre-existing: the judgement key grammar has no owner, and this change did not cause that. To avoid adding a new cross-carry, the spec keys the carried map by (repo.lower(), number), checked against the loop's repo.
