# Journal: 2026-10-02-wave-driver

<!-- fr:journal kind=discovery scope=spec id=wave-driver-brief created=2026-10-02T17:48:22+00:00 -->
### wave-driver-brief · discovery · Operator brief: make the wave-driving and report-page work fr verbs and skills

Operator, verbatim (2026-10-02): "so, remind me, are these 3 artifacts already created via a super-fr skill or are they adhoc? Also, what about the dispatching? What about the monitoring and merging when PRs are mergeable (green CI and not draft)?" — answered: the triage board is fr triage render output patched by hand; the architecture and defect-origins pages are hand-built HTML; the scheduling (4 in flight, dependencies, wave order, merge when ready and green, close-out launch) is an ad-hoc script. Operator: "good, yes, let's make everything skills and/or fr verbs." Answers to the scoping questions: scope = all three parts (driver, board section, skills for the architecture and defect-origins pages); verb = fr triage batch drive with a loop and --once; close-out started through the runner; waves and dependencies as fields on each batch.

<!-- fr:journal kind=decision scope=spec id=scope-all-three created=2026-10-02T18:54:04+00:00 -->
### scope-all-three · decision · One spec for the driver, the board views and the page skills

Operator: the three parts fit together, so one spec.

<!-- fr:journal kind=decision scope=spec id=verb-drive-loop-once created=2026-10-02T18:54:04+00:00 -->
### verb-drive-loop-once · decision · fr triage batch drive, a loop with --once

Operator chose the foreground loop plus a single-pass --once over a single-pass-only verb or a daemon.

<!-- fr:journal kind=decision scope=spec id=closeout-through-runner created=2026-10-02T18:54:04+00:00 -->
### closeout-through-runner · decision · Close-out starts through the runner

Operator chose a runner work item (unit run, payload kind closeout) over printing the command or running the steps in-process.

<!-- fr:journal kind=decision scope=spec id=waves-as-batch-fields created=2026-10-02T18:54:04+00:00 -->
### waves-as-batch-fields · decision · wave and after are fields on each batch

Operator chose fields on Batch (judgements schema 3) over a separate plan file; the in-flight cap is a drive flag.

<!-- fr:journal kind=decision scope=spec id=post-merge-config created=2026-10-02T18:54:04+00:00 -->
### post-merge-config · decision · The host install is a per-repo post_merge command

Raised by the operator: without install.sh the harnesses on the host run a stale fr. The driver runs a post_merge command from .fr/triage.yaml once per merge, before the close-out.

<!-- fr:journal kind=decision scope=spec id=scope-groups-and-views created=2026-10-02T18:54:04+00:00 -->
### scope-groups-and-views · decision · Comma-separated repo groups; three new board views; nothing removed

Operator asked for a comma-separated repo list as one group, wave tabs with the latest preselected, and a reorganisation around what changed and what to do next. Operator: the same three artifacts, nothing removed, just reordered, plus three new views (Since last report, Needs you now, Next up).
