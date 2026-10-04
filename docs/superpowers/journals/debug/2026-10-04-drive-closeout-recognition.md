# Journal: 2026-10-04-drive-closeout-recognition

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-04T04:50:56+00:00 -->
### repro · repro · Three symptoms of one gap: a close-out the driver did not start is never recorded

Read from code (batch_drive.drive_pass, _Driver.snapshot, views.needs_you, batch.closeout_state); the live evidence is in the issues. #912: a landed batch with no closeout event and its run still live on origin/main reads as owed; the snapshot never looks for an open PR on chore/closeout-<branch with / as ->, so a named drive with --yes starts a second close-out beside the hand-opened one (#895, #896 on 2026-10-03). #899: views.drive_snapshot has no git, so its archived set is always empty; needs_you's post-merge row is suppressed only by a closeout or post_merge event, so a hand-closed waved batch keeps the row forever. #900: snapshot() re-derives archived (pr_view, fetch, diff, cat-file) every pass because nothing records the finding; batch list shows close-out none for those batches.
