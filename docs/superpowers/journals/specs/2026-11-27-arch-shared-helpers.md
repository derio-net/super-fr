<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-arch-shared-helpers

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-27T09:02:49+00:00 input=true -->
### operator-brief · discovery · Operator brief: batch arch-shared-helpers (#1512, #1513, #1514, #1523)

/fr-goal batch arch-shared-helpers

Batch `arch-shared-helpers` of derio-net/super-fr: 4 issues, delivered as ONE pull request.
Batch title: #1318: shared duplicate-key YAML detector, record placement and hermetic-git fixtures, small duplicate readers
- super-fr#1512 Share the duplicate-key YAML detector between artifacts, harness and lenses (R04)
- super-fr#1513 Share the record-file placement helper across the record migration tests (R05)
- super-fr#1514 Share the hermetic-git test fixture across gate-backfill and merge-evidence tests (R06)
- super-fr#1523 Small duplicate readers left by the #1318 review: gate help text, _pr_time, _created_since, naive-as-UTC parsers
Why together: #1318 cheap shared-helper slices; no giant module touched.

Delivery rules: branch `feat/batch-arch-shared-helpers`; open a draft PR as soon as the spec is
committed, its body carrying one `Closes derio-net/super-fr#<n>` line per member; batches
`closeout-state` and `queue-followups` of this wave also change
packages/fr/src/fr/commands/triage_batch_cmd.py (whichever lands second resolves the queue's
conflict hand-back); no member issue as a phase `tracking_issue`; the wave driver owns
mergeability and CI (no `fr pr settle` loop); never add `approved-fr`.
(Issue bodies as on the tracker; the batch block was marked untrusted.)

<!-- fr:journal kind=decision scope=spec id=q-shape created=2026-11-27T09:02:49+00:00 decided_by=operator -->
### q-shape · decision · Shape: fr-goal-light, one agentic phase

Operator chose fr-goal-light with a single phase for all four asks (recommended): small mechanical extractions, no behaviour change.

<!-- fr:journal kind=decision scope=spec id=q-yaml-home created=2026-11-27T09:02:49+00:00 decided_by=operator -->
### q-yaml-home · decision · Strict YAML loader lives in fr.yamlio

Operator chose fr.yamlio (recommended): it imports only yaml and is already the one place that picks a loader. Stays on pure-Python SafeLoader; #1286 keeps the libyaml switch.

<!-- fr:journal kind=decision scope=spec id=q-utc-home created=2026-11-27T09:02:49+00:00 decided_by=operator -->
### q-utc-home · decision · parse_as_utc lives in new fr/utc_time.py

Operator chose a new top-level standard-library-only module (recommended), so debt and usage never import fr.triage and parse_aware's module stays single-contract.

<!-- fr:journal kind=decision scope=spec id=q-verify created=2026-11-27T09:02:49+00:00 decided_by=operator -->
### q-verify · decision · Verification: strategy none, gate developer

Operator chose no install walk (recommended): the CI unit suite and the new AST guards prove a no-behaviour-change refactor; nothing to do after merge.

<!-- fr:journal kind=decision scope=spec id=q-rows created=2026-11-27T09:02:49+00:00 decided_by=operator -->
### q-rows · decision · No new acceptance rows

Operator chose no new rows (recommended): no product behaviour changes; the guards are tests, not business claims.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-arch-shared-helpers-p1 created=2026-11-27T09:04:33+00:00 -->
### phase-split-2026-11-27-arch-shared-helpers-p1 · decision · review-size: the whole batch (R1-R9) is one reviewable diff; it has no acceptance rows by operator decision q-rows, so the phase serves the requirements directly
