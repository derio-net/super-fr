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

<!-- fr:journal kind=review scope=spec id=r-spec created=2026-09-25T15:05:29 -->
### r-spec · review · Spec review (independent fr-spec-reviewer): 3 findings, all fixed

Reviewer verified the telemetry readers, units.py consumers, pickup_cmd.py:65, run v6 + legacy freeze precedent, fr-goal.yaml emits, fr-isolation-guard.sh:206-215 (host-side cd form already allowed; §5.B.6 updated), parity.yaml shape, plan_ops.py:1804-1871, and the gh#610 dependency.

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-09-25T15:06:06 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · emits: gates only the journal section; ticks/refactor/acceptance/resolves were stated by step id

Spec §5.C.2.1 vs plugins/super-fr/workflows/fr-goal.yaml emits values and fr/workflow/model.py:53. Two incompatible implementations possible.

<!-- fr:journal kind=finding scope=spec id=sr-1-fixed created=2026-09-25T15:06:07 state=fixed resolves=sr-1 -->
### sr-1-fixed · finding [fixed] · resolves sr-1

§5.C.2.1 now a table: journal/resolves <- journal:<scope>; ticks/refactor <- new plan:ticks token; acceptance <- new acceptance token; both manifests and fr.workflow.artifacts vocabulary gain them (§6).

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-09-25T15:06:09 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · No devcontainer marker value exists; devcontainer and host-worktree both write mode: worktree

Spec §5.B.6 vs fr/isolation/hostworktree.py:9, external.py:104-119.

<!-- fr:journal kind=finding scope=spec id=sr-2-fixed created=2026-09-25T15:06:10 state=fixed resolves=sr-2 -->
### sr-2-fixed · finding [fixed] · resolves sr-2

In-process check reworded: mode: worktree marker AND container evidence (the external.py checks).

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-09-25T15:06:12 state=open review_scope=out -->
### sr-3 · finding [open] (reviewer: out of scope) · parity.yaml isolation-mode dimension had no stated shape

Spec §5.B.8 vs packages/fr/src/fr/harness/parity.yaml:16-45. Reclassified in scope by the orchestrator: the ambiguity is in this spec's own new requirement.

<!-- fr:journal kind=finding scope=spec id=sr-3-fixed created=2026-09-25T15:06:13 state=fixed resolves=sr-3 -->
### sr-3-fixed · finding [fixed] · resolves sr-3

§5.B.8 now specifies optional harnesses.<harness>.modes.<mode>: {state, scope_note}; absent = one state for all modes.
