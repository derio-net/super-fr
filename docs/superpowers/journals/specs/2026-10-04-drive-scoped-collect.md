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
