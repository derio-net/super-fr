<!-- fr:journal-schema=3 -->
# Journal: 2026-11-03-gate-backfill-ambiguous-pr

<!-- fr:journal kind=repro scope=debug id=37da5c8468c4 created=2026-11-03T18:32:57+00:00 -->
### 37da5c8468c4 · repro · Ambiguous delivering PR can never be resolved (gh#1369)

Open manual phase whose plan two run cursors emitted on branches with merged PRs #21/#22. Dry run: entry ambiguous, decision review, and the summary says 'add pr: in a manifest (--from)'. A manifest item {key: <held key>, kind: ..., pr: 22} is refused by collect_candidates ('fr debt already holds this key'); hand-setting the plan file's pr: then --yes skips with 'delivering PR re-resolves to none, plan recorded #22' (apply.py R15 guard). Pinned by tests/unit/test_gate_cmd.py#test_gh1369_a_manifest_pr_resolves_an_ambiguous_key_fr_debt_holds.

<!-- fr:journal kind=root-cause scope=debug id=71e741ef20cb created=2026-11-03T18:33:00+00:00 -->
### 71e741ef20cb · root-cause · The manifest accepts only keys the fold lacks, so the spec's one resolution route is closed

Spec 2026-11-01-gate-backfill §C says an ambiguity 'stays unwritten until the operator sets pr: in a manifest', but §B says 'a key the fold already holds is an error', and candidates.collect_candidates implements §B (only the p2-r3 tracker-only take-back is exempt). ManifestItem also requires kind/title, which describe a NEW item. The plan-file route is closed by design: --yes re-resolves (R15) and an ambiguity re-resolves to no PR. Same trap for a planning PR, whose why text says 'set pr: to the delivering one' (the plan file).
