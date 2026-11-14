<!-- fr:journal-schema=4 -->
# Journal: 2026-11-14-local-stamp-design-fragment

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-11-14T19:05:28+00:00 -->
### repro-1 · repro · deliver passes with local rows unstamped when the feature fragment is <slug>-design.yaml (gh#1456)

Stealth walk on 7.0.0-rc.8: fr run resolve --step deliver passed; fr acceptance status then lists the feature's rows [local, unstamped]. The fragment was created by rc.3, before #1451, as <slug>-design.yaml.

<!-- fr:journal kind=root-cause scope=debug id=rc-1 created=2026-11-14T19:05:30+00:00 -->
### rc-1 · root-cause · _local_stamp_plan opens only <fragment_slug_for_spec(spec)>.yaml and returns None when absent

run_cmd._local_stamp_plan built one path from the -design-stripped slug; a -design-named fragment (which the fold still reads) was never found, so deliver planned no stamp and said nothing. Secondly, the leftovers refusal printed set-status --status local while the pending deliver record's acceptance entry set the row unwired; apply_record writes the record before the gates read the fold, so the record wins and the refusal repeats without naming it.
