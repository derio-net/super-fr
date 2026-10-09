# Batch sweep status lanes — implementation plan

Spec: `docs/superpowers/specs/2026-10-08-batch-sweep-status-lanes-design.md`.

Two agentic phases, split by independently reviewable behavior:

1. **Board human lanes and run signals** (R1–R6, R10) is the skeleton. It first
   keeps the existing board smoke green, then adds the pure nine-column model,
   remote-head cursor reads through explicit checkout mappings, and responsive
   rendering. It ends with fresh visual evidence and the existing board contract
   still green.
2. **Mergeability and session relay** (R7–R9) extends the driver's pure decision
   inputs, gates merge readiness, and executes one-per-head prompts through the
   existing optional dispatch protocols. It ends with the installed candidate
   scenario, acceptance evidence, change fragment, and full suite.

The split keeps UI/git-read behavior separate from merge automation and runner
messaging. Both phases remain fully agent-completable; there is no manual phase
and no post-merge Test Plan.

Import direction remains load-bearing: `fr.triage.kanban`, `batch_drive`, and
`views` stay pure and never import `fr_dispatch`; the two command modules remain
the only triage soft points. Cursor reads use explicit clones and remote refs,
never the host triage cache or the checked-out feature files.
