# Journal: 2026-10-06-batch-drive-adopt-and-trust

<!-- fr:journal kind=repro scope=debug id=77a8298c2a5d created=2026-10-06T16:09:01+00:00 -->
### 77a8298c2a5d · repro · Three driver defects reproduced by reading the pass (gh#990, gh#991, gh#1004)

gh#990: a merged wave-less batch with no close-out event, alongside any waved batch, is never adopted: `default_selection` drops it, and both the snapshot's archived read and drive_pass step 2 iterate `chosen` only.
gh#991: `fr triage batch drive --once` (no --yes) with an unreadable clone reports archived batches as `closeout start`: `_archived`/`_released`/`_ci_none` swallow TriageError outside --yes.
gh#1004: an archive PR retargeted off the default branch is merged by step 3/`_archive`: archive LivePrs never carry `base`.
