# Journal: 2026-10-06-batch-drive-adopt-and-trust

<!-- fr:journal kind=repro scope=debug id=77a8298c2a5d created=2026-10-06T16:09:01+00:00 -->
### 77a8298c2a5d · repro · Three driver defects reproduced by reading the pass (gh#990, gh#991, gh#1004)

gh#990: a merged wave-less batch with no close-out event, alongside any waved batch, is never adopted: `default_selection` drops it, and both the snapshot's archived read and drive_pass step 2 iterate `chosen` only.
gh#991: `fr triage batch drive --once` (no --yes) with an unreadable clone reports archived batches as `closeout start`: `_archived`/`_released`/`_ci_none` swallow TriageError outside --yes.
gh#1004: an archive PR retargeted off the default branch is merged by step 3/`_archive`: archive LivePrs never carry `base`.

<!-- fr:journal kind=root-cause scope=debug id=e11888cd2dd2 created=2026-10-06T16:09:02+00:00 -->
### e11888cd2dd2 · root-cause · Not one cause but three independent ones (operator chose: fix all three in one PR)

1. Adoption (bookkeeping) is scoped to the drive selection; it must read every landed batch without a close-out event (gh#990).
2. Plan-mode clone reads turn a read failure into a negative answer, silently (gh#991).
3. The archive-PR trust check omits the base branch the export path already checks via `_wrong_base` (gh#1004, p4-r15).
Investigation found three causes; the batch rule required stopping to ask, and the operator chose to fix all three in this PR.
