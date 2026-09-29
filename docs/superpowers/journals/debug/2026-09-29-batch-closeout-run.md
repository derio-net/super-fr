# Journal: 2026-09-29-batch-closeout-run

<!-- fr:journal kind=ruled-out scope=debug id=single-root-cause created=2026-09-29T11:09:08+00:00 -->
### single-root-cause · ruled-out · The four closeout-run members do not share one root cause

Four independent defects in four modules: #811 fr/commands/pickup_cmd.py + fr/run/model.py:552 (RunStateError with no origin/<default> probe) and fr/commands/status_cmd.py (reads the working tree while naming origin); #824 fr/isolation/local.py:2552-2557 excludes only .fr-isolation, never .devcontainer/<profile>/devcontainer-lock.json; #825 fr/run/closeout.py:284 emits a down for the feature branch but none for the chore/archive-*|chore/closeout-* branch the brief opens (lines 169-178); #826 fr/plan_validator_wrapper.py:16-20 WRAPPER_TEXT hard-codes the Claude Code marketplace path. The common theme is close-out hygiene, not a shared cause. Batch rules say stop and ask before fixing.
