# Journal: 2026-09-25-lean-cost-aware-process

<!-- fr:journal kind=decision scope=spec id=d1-scope created=2026-09-25T14:37:20 -->
### d1-scope · decision · One spec for usage, lean process and pages, fewest phases

Operator: one spec covering A (usage), B (lean process) and C (architecture page + updated Paper Trail Audit), in as few phases as possible. Heuristic: fewer, larger sessions keep more decision context.

<!-- fr:journal kind=decision scope=spec id=d2-backward-reads created=2026-09-25T14:37:21 -->
### d2-backward-reads · decision · Old fr need not read new artifacts

Operator: the plugin is updated instead. New fr still migrates old artifacts forward.

<!-- fr:journal kind=decision scope=spec id=d3-state-in-git created=2026-09-25T14:37:22 -->
### d3-state-in-git · decision · Run state stays in git; bookkeeping becomes mechanical

Operator rejected run state outside git (stale/lost sessions must be resumable). Option 2 accepted: batched, mechanical, committed when it should be, gates holding.

<!-- fr:journal kind=decision scope=spec id=d4-record-per-step created=2026-09-25T14:37:22 -->
### d4-record-per-step · decision · One record file per workflow step, one resolve --record

Operator chose a record file per step over commit trailers or batch flags. Measured basis: 867 bookkeeping calls in 866 messages, 6.1 per step, 90% of their cost context carry.

<!-- fr:journal kind=decision scope=spec id=d5-usage-central created=2026-09-25T14:37:23 -->
### d5-usage-central · decision · Usage captured once per host into docs/superpowers/usage/<run-id>.yaml

Operator: central per-run files, archived at closeout like other fr artifacts; existing telemetry migrated in; hosts opaque (third-party privacy). Rejected: on-demand only (pruning, locality), cursor block, append-only ledger, outside git.

<!-- fr:journal kind=decision scope=spec id=d6-atdd created=2026-09-25T14:37:24 -->
### d6-atdd · decision · ATDD rows stay at brainstorm; reports stay committed

Operator: acceptance tests up front. Rows written by the brainstorm record. skipped = manually verified at least once, not in CI.

<!-- fr:journal kind=decision scope=spec id=d7-quiet-then-measure created=2026-09-25T14:37:24 -->
### d7-quiet-then-measure · decision · Quiet mechanics now; thin orchestrator only after measuring

Operator chose option 3: quiet one-line success output now; dispatching plan/deliver to subagents waits for usage/ evidence, given the fewer-sessions heuristic.

<!-- fr:journal kind=decision scope=spec id=d8-ticks-verbs-stay created=2026-09-25T14:37:25 -->
### d8-ticks-verbs-stay · decision · Ticks and verbs stay; verbs become one-entry records

Ticks serve intra-phase resume (pickup_cmd.py:65), the runner path and GitHub sync. Verbs serve fr-execute, fr-acceptance, fr-debugging and humans; same apply engine as resolve --record.

<!-- fr:journal kind=decision scope=spec id=d9-phases created=2026-09-25T14:37:26 -->
### d9-phases · decision · Phases: audit mechanism, usage, step records, post-merge walk

Operator: the page-generating mechanism is kept (skill + engine), phase 1. Usage and step records are separate phases. Post-merge walk as usual; no Hermes walk, marked in parity.yaml.

<!-- fr:journal kind=decision scope=spec id=d10-host-side created=2026-09-25T14:37:27 -->
### d10-host-side · decision · fr run / fr usage execute on the harness host in every mode

From the #604 phase-5 steer: in devcontainer mode fr run ran in the container with no harness env or transcripts. fr isolation exec refuses inner fr run/usage in devcontainer mode with the host-side command; an in-process check keyed on the operated repo's marker catches the rest; external mode is never refused.
