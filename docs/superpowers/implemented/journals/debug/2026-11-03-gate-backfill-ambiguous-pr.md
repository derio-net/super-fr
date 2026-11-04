<!-- fr:journal-schema=3 -->
# Journal: 2026-11-03-gate-backfill-ambiguous-pr

<!-- fr:journal kind=repro scope=debug id=37da5c8468c4 created=2026-11-03T18:32:57+00:00 -->
### 37da5c8468c4 · repro · Ambiguous delivering PR can never be resolved (gh#1369)

Open manual phase whose plan two run cursors emitted on branches with merged PRs #21/#22. Dry run: entry ambiguous, decision review, and the summary says 'add pr: in a manifest (--from)'. A manifest item {key: <held key>, kind: ..., pr: 22} is refused by collect_candidates ('fr debt already holds this key'); hand-setting the plan file's pr: then --yes skips with 'delivering PR re-resolves to none, plan recorded #22' (apply.py R15 guard). Pinned by tests/unit/test_gate_cmd.py#test_gh1369_a_manifest_pr_resolves_an_ambiguous_key_fr_debt_holds.

<!-- fr:journal kind=root-cause scope=debug id=71e741ef20cb created=2026-11-03T18:33:00+00:00 -->
### 71e741ef20cb · root-cause · The manifest accepts only keys the fold lacks, so the spec's one resolution route is closed

Spec 2026-11-01-gate-backfill §C says an ambiguity 'stays unwritten until the operator sets pr: in a manifest', but §B says 'a key the fold already holds is an error', and candidates.collect_candidates implements §B (only the p2-r3 tracker-only take-back is exempt). ManifestItem also requires kind/title, which describe a NEW item. The plan-file route is closed by design: --yes re-resolves (R15) and an ambiguity re-resolves to no PR. Same trap for a planning PR, whose why text says 'set pr: to the delivering one' (the plan file).

<!-- fr:journal kind=finding scope=debug id=fix-manifest-override created=2026-11-03T18:35:44+00:00 state=fixed -->
### fix-manifest-override · finding [fixed] · Manifest override (no kind:) for a held key sets pr:/gate:/walk_only:

ManifestItem.kind/title optional; candidates._check_manifest_item: a held key takes only an override (pr/gate/walk_only, no title/issue), an unheld key only a new item (kind+title); a kind: item for a held key still refuses, naming the override. Override keeps the fold source and shape gate (gate: replaces it if given). to_entry's why and apply's R15 skip line now say 'in a manifest entry for this key (--from), not in the plan file'. Tests failing first: test_gate_cmd.py#test_gh1369_a_manifest_pr_resolves_an_ambiguous_key_fr_debt_holds (end to end: label on #22 only, one fr:owed tracker), #test_gh1369_an_ambiguous_entry_applied_without_its_manifest_says_how_to_resolve_it, test_gatebackfill_candidates.py#test_gh1369_*. docs/gate-backfill.md documents the override.

<!-- fr:journal kind=review scope=debug id=064a3820b4cd created=2026-11-04T03:10:35+00:00 -->
### 064a3820b4cd · review · Self-review of the diff: no findings

Read the full source diff. Checked: the p2-r3 take-back now requires a kind: item, so an override never turns a row/plan key into a manifest-source candidate; _settle_trackers keys on source == manifest (same set as before for new items); gate_for only ever gets a new item. Full suite via testslot: 14063 passed, 5 failed (test_records_commit stuck-index-lock timing, 3 test_run_evidence_visual, 1 test_status_owed), all outside gatebackfill; the 62 tests of those files pass in isolation, so load-timing, not this change.
