# Journal: 2026-10-04-drive-closeout-recognition

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-04T04:50:56+00:00 -->
### repro · repro · Three symptoms of one gap: a close-out the driver did not start is never recorded

Read from code (batch_drive.drive_pass, _Driver.snapshot, views.needs_you, batch.closeout_state); the live evidence is in the issues. #912: a landed batch with no closeout event and its run still live on origin/main reads as owed; the snapshot never looks for an open PR on chore/closeout-<branch with / as ->, so a named drive with --yes starts a second close-out beside the hand-opened one (#895, #896 on 2026-10-03). #899: views.drive_snapshot has no git, so its archived set is always empty; needs_you's post-merge row is suppressed only by a closeout or post_merge event, so a hand-closed waved batch keeps the row forever. #900: snapshot() re-derives archived (pr_view, fetch, diff, cat-file) every pass because nothing records the finding; batch list shows close-out none for those batches.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-10-04T04:50:57+00:00 -->
### root-cause · root-cause · The closeout event is the only durable close-out signal, and a close-out the driver did not start never enters it

Every consumer (drive_pass close-out and archive steps, the snapshot's probing, views.needs_you, closeout_state / batch list) keys off a CloseoutEvent. The driver writes one only when it starts the close-out itself. It recognises a hand close-out only transiently (Snapshot.archived, git-derived per pass, invisible to the git-less board) and never recognises an open hand-opened close-out PR. Fix: when the snapshot finds evidence of a close-out it did not start (artifacts archived, or a PR on chore/closeout-<branch->, open or merged), the pass emits an adopt action, and with --yes the driver records a CloseoutEvent: runner hand, handle naming the evidence, archive the PR head, archived set to the merged PR number, or 0 when git shows the archive but no PR is known. archived is only ever tested for is-not-None, so 0 needs no schema change and older fr reads it as finished.
