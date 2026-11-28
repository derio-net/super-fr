# Tester gate auto-pass for PRs outside a batch

One agentic phase: the wave driver's rows-walked gate pass (exit-gates R14) is extended from
landed batches to every merged gated PR that is not the PR of a batch without a close-out,
including a closed-out batch's PR. The shared rule moves into the pure `fr.triage.pr_gates`;
reads go in `commands/triage_drive_loose.py` because `triage_batch_cmd.py` sits 4 lines under
its budget. The cursor read gains a PR-number check so a reused branch never passes a gate on
another delivery's rows.
