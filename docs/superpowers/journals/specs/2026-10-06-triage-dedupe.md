# Journal: 2026-10-06-triage-dedupe

<!-- fr:journal kind=discovery scope=spec id=brief-971 created=2026-10-06T07:41:40+00:00 input=true -->
### brief-971 · discovery · Operator brief: batch triage-dedupe (super-fr#971), verbatim

/fr-goal Triage owns duplicates: a sweep proposes duplicate open issues, judgements record duplicate_of

Batch `triage-dedupe` of derio-net/super-fr: 1 issues, delivered as ONE pull request.

## super-fr#971: Triage owns duplicates: a sweep that finds duplicate open issues and records them structurally
No sweep finds duplicate open issues; #781 (check before filing) was closed not planned because a run must not search the backlog. Triage owns it: candidates from the engine, judgement from the skill, `duplicate_of` in judgements.
Note: Operator 2026-10-05: finding duplicates is our responsibility.

## Why these belong together
Wave 4: operator 2026-10-05, finding duplicates is our job. After state-integrity: both touch the judgement model and keys.

## Delivery rules
- Work on branch `feat/batch-triage-dedupe`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#971
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=q1-surface created=2026-10-06T07:41:40+00:00 -->
### q1-surface · decision · Sweep lives in check sets plus a board section; no new verb

Operator chose the recommended option: `check` gains `duplicate candidates` and `duplicates` sets, the board a Possible duplicates section. The refresh loop already runs check, so the sweep runs on every refresh.

<!-- fr:journal kind=decision scope=spec id=q2-dismissals created=2026-10-06T07:41:40+00:00 -->
### q2-dismissals · decision · Dismissals are per-issue distinct_from, read symmetrically

Operator chose `distinct_from: [keys]` on a judgement, beside `duplicate_of`.

<!-- fr:journal kind=decision scope=spec id=q3-board created=2026-10-06T07:41:40+00:00 -->
### q3-board · decision · A judged duplicate nests under its original on the board

Operator chose nesting: the duplicate leaves its tier and is never unplaced; a closed or missing original keeps it in its tier with a warning tag.

<!-- fr:journal kind=decision scope=spec id=q4-close-command created=2026-10-06T07:41:40+00:00 -->
### q4-close-command · decision · Print gh issue close --duplicate-of; no --yes executor

Operator chose printing GitHub's native duplicate close command and never running it; nothing in this change writes to the forge.

<!-- fr:journal kind=decision scope=spec id=q5-driver created=2026-10-06T07:41:40+00:00 -->
### q5-driver · decision · Driver reports candidates once when a wave finishes

Operator chose one warn line after a wave's close-out completes (spec §3.E makes it the pass whose archive merge finishes the wave, stateless).

<!-- fr:journal kind=decision scope=spec id=d-no-schema-bump created=2026-10-06T07:41:40+00:00 -->
### d-no-schema-bump · decision · duplicate_of/distinct_from are optional on every judgements schema

Follows the `kind`/`features` precedent (wave-driver R9): no engine verb writes them, and judgements.yaml is not an artifact kind.

<!-- fr:journal kind=decision scope=spec id=d-calibration created=2026-10-06T07:41:40+00:00 -->
### d-calibration · decision · Signal thresholds calibrated on this repo's 438 issues

Prototype recovered all three known duplicate groups (4 of 5 pairs directly, the fifth by connectivity) and flags 4 pairs among 61 open issues; spec §2.
