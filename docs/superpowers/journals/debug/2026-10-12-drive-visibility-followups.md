# Journal: 2026-10-12-drive-visibility-followups

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-11T23:01:02+00:00 -->
### repro · repro · A failed visibility read outside take_lease/save_pass's state-repo read ends a looping driver

#1144: state repo public, a member repo's visibility read fails (rate limit). guard_state's _fill stores None; check_or_refuse's leaks() counts None as not public and raises the plain PrivacyError leak refusal. take_lease/save_pass translate only VisibilityUnreadable into ForgeReadError, so _fail exits 2 and the loop ends, with a message claiming a leak. #1145: a VisibilityUnreadable from guard_write during a pass goes through _write -> _fail (typer.Exit 2), which the loop does not retry.
