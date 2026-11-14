<!-- fr:journal-schema=4 -->
# Journal: 2026-11-14-local-stamp-design-fragment

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-11-14T19:05:28+00:00 -->
### repro-1 · repro · deliver passes with local rows unstamped when the feature fragment is <slug>-design.yaml (gh#1456)

Stealth walk on 7.0.0-rc.8: fr run resolve --step deliver passed; fr acceptance status then lists the feature's rows [local, unstamped]. The fragment was created by rc.3, before #1451, as <slug>-design.yaml.

<!-- fr:journal kind=root-cause scope=debug id=rc-1 created=2026-11-14T19:05:30+00:00 -->
### rc-1 · root-cause · _local_stamp_plan opens only <fragment_slug_for_spec(spec)>.yaml and returns None when absent

run_cmd._local_stamp_plan built one path from the -design-stripped slug; a -design-named fragment (which the fold still reads) was never found, so deliver planned no stamp and said nothing. Secondly, the leftovers refusal printed set-status --status local while the pending deliver record's acceptance entry set the row unwired; apply_record writes the record before the gates read the fold, so the record wins and the refusal repeats without naming it.

<!-- fr:journal kind=finding scope=debug id=f-1 created=2026-11-14T19:51:56+00:00 state=fixed -->
### f-1 · finding [fixed] · deliver reads both spellings of the feature fragment and stamps or refuses each

_local_stamp_plan reads <slug>.yaml and <slug>-design.yaml; _LocalStamps carries one (path, text) per fragment. Pinned by tests/unit/test_deliver_local_stamp.py::test_a_local_row_in_a_design_named_fragment_is_stamped (red before: row stayed unstamped) and ::test_a_design_named_fragment_that_cannot_be_stamped_refuses.

<!-- fr:journal kind=finding scope=debug id=f-2 created=2026-11-14T19:51:58+00:00 state=fixed -->
### f-2 · finding [fixed] · the leftovers refusal names the pending record that sets a row

apply_record passes the record's name and per-row statuses into resolve_in_process (_RECORD_ROWS); _deliver_leftovers_gate prefixes such a row's fix with 'the record <path> sets this row <status>, and the record wins over the fragment'. Pinned by tests/unit/test_deliver_leftovers.py::test_a_row_the_pending_record_sets_names_the_record and ::test_record_rows_reads_rows_and_amendments.

<!-- fr:journal kind=review scope=debug id=rev-1 created=2026-11-14T19:52:00+00:00 -->
### rev-1 · review · self-review of the diff: no findings

Read the full diff. Both spellings are read only when they exist; a fragment with no local row still returns before the fold (review p2-r1 test still green). The record annotation only touches row leftovers whose id the record sets. Full suite: 16143 passed, 128 skipped. fr docs check clean after the two reviewed stamps.
