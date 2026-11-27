<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-board-session-state

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-27T19:57:09+00:00 input=true -->
### brief · discovery · Operator brief (batch board-session-state, derio-net/super-fr#1731)

Batch `board-session-state` of derio-net/super-fr: 1 issues, delivered as ONE pull request.
Batch title: Batches page: session state, lane owners, time per column
super-fr#1731: Batches page: show who each session waits for (session state within the columns), lane owners, and dwell time per column.
Batches page: session state within the existing columns (who waits for whom), an owner per Needs-you lane, and time per column and state. Builds on `fr_herdr.restart.has_background_work`; columns stay decided by `lanes.lane_of`.
Note: Works without Stations; helps orchestrating today.
Why these belong together: Operator-requested: shows who each session waits for, and where waves lose time; needed to orchestrate waves now.
Delivery rules: branch feat/batch-board-session-state; draft PR with "Closes derio-net/super-fr#1731"; run started with --issue 1731; no member issue as a phase tracking_issue; the wave driver owns mergeability and CI (no fr pr settle loop); never add approved-fr.

<!-- fr:journal kind=decision scope=spec id=q1-wait-parties created=2026-11-27T19:57:09+00:00 decided_by=operator -->
### q1-wait-parties · decision · A card names one of six parties it waits for

Operator chose the six-party set: you (with lane role), agent, background (via has_background_work, one herdr screen read per idle session per render), ci, queue/driver, dependency. Recommended option.

<!-- fr:journal kind=decision scope=spec id=q2-lane-owners created=2026-11-27T19:57:09+00:00 decided_by=operator -->
### q2-lane-owners · decision · Lane owners come from each repo's .fr/triage.yaml

Operator chose a new `lane_owners` key in `.fr/triage.yaml` read at the default branch; unset lane shows 'owner: unassigned'; shown in the lane header and on the card; per repo when a multi-repo scope differs. Recommended option.

<!-- fr:journal kind=decision scope=spec id=q3-dwell-ledger created=2026-11-27T19:57:09+00:00 decided_by=operator -->
### q3-dwell-ledger · decision · Dwell time is measured by a dwell ledger in the state directory

Operator chose `dwell.json` in the scope's state directory, carried by the state ref, updated by every board render and driver pass; precision is the cadence. Recommended option.

<!-- fr:journal kind=decision scope=spec id=q4-display created=2026-11-27T19:57:09+00:00 decided_by=operator -->
### q4-display · decision · Cards carry a dwell line, waves a time summary

Operator chose per-card 'in <column> <t> · waits for <party> <t>' plus a per-wave summary of time per column and per wait party naming the slowest batch per column. Recommended option.

<!-- fr:journal kind=decision scope=spec id=q5-verification created=2026-11-27T19:57:09+00:00 decided_by=operator -->
### q5-verification · decision · Verified by CI unit tests and browser checks, gate developer

Operator chose strategy none per row (CI unit tests plus fr-goal's browser checks at review and deliver over a fixture-rendered page), gate developer; the live herdr background read is a post-merge Test Plan row. Recommended option.
