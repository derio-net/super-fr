# Journal: 2026-10-02-wave-driver

<!-- fr:journal kind=discovery scope=spec id=wave-driver-brief created=2026-10-02T17:48:22+00:00 -->
### wave-driver-brief · discovery · Operator brief: make the wave-driving and report-page work fr verbs and skills

Operator, verbatim (2026-10-02): "so, remind me, are these 3 artifacts already created via a super-fr skill or are they adhoc? Also, what about the dispatching? What about the monitoring and merging when PRs are mergeable (green CI and not draft)?" — answered: the triage board is fr triage render output patched by hand; the architecture and defect-origins pages are hand-built HTML; the scheduling (4 in flight, dependencies, wave order, merge when ready and green, close-out launch) is an ad-hoc script. Operator: "good, yes, let's make everything skills and/or fr verbs." Answers to the scoping questions: scope = all three parts (driver, board section, skills for the architecture and defect-origins pages); verb = fr triage batch drive with a loop and --once; close-out started through the runner; waves and dependencies as fields on each batch.
