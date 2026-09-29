# Journal: 2026-09-29-batch-closeout-run

<!-- fr:journal kind=ruled-out scope=debug id=single-root-cause created=2026-09-29T11:09:08+00:00 -->
### single-root-cause · ruled-out · The four closeout-run members do not share one root cause

Four independent defects in four modules: #811 fr/commands/pickup_cmd.py + fr/run/model.py:552 (RunStateError with no origin/<default> probe) and fr/commands/status_cmd.py (reads the working tree while naming origin); #824 fr/isolation/local.py:2552-2557 excludes only .fr-isolation, never .devcontainer/<profile>/devcontainer-lock.json; #825 fr/run/closeout.py:284 emits a down for the feature branch but none for the chore/archive-*|chore/closeout-* branch the brief opens (lines 169-178); #826 fr/plan_validator_wrapper.py:16-20 WRAPPER_TEXT hard-codes the Claude Code marketplace path. The common theme is close-out hygiene, not a shared cause. Batch rules say stop and ask before fixing.

<!-- fr:journal kind=root-cause scope=debug id=rc-811 created=2026-09-29T11:35:44+00:00 -->
### rc-811 · root-cause · #811: pickup --run and status read the working tree only, never comparing it to the ref they name

pickup_cmd.py maps RunStateError straight to exit 2 with 'no run state at <path>' and never looks at <remote>/<default>, so a clone that has not pulled the merge gets no hint. status_cmd's sweep enumerates plan dirs (fr.closeout.plan_sweep) and owed artifacts from the working tree, while merge_evidence reads the fetched origin/<default>. When HEAD is strictly behind that ref, the merged plan is not on disk, so no bucket lists it. The header names the ref ('origin/master @ sha'), which reads as though the ref was evaluated.

<!-- fr:journal kind=root-cause scope=debug id=rc-824 created=2026-09-29T11:35:45+00:00 -->
### rc-824 · root-cause · #824: up git-excludes .fr-isolation but not the devcontainer CLI's devcontainer-lock.json

LocalIsolation._write_isolation_marker (isolation/local.py) appends only '.fr-isolation' to the shared info/exclude. The devcontainer CLI writes .devcontainer/<profile>/devcontainer-lock.json on 'up', untracked. down's reap-hazard check (git status --porcelain, untracked counts: #435 d1) then sees a dirty worktree and refuses.

<!-- fr:journal kind=root-cause scope=debug id=rc-825 created=2026-09-29T11:35:46+00:00 -->
### rc-825 · root-cause · #825: the close-out brief opens a housekeeping workspace but only downs the feature branch

run/closeout.py branch_closeout_brief prints 'fr isolation up --branch <housekeeping>' (chore/archive-<plan> or chore/closeout-<...>) and ends with 'fr isolation down --branch <feature branch>'. It has no line for the housekeeping branch, so that workspace outlives every close-out.
