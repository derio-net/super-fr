# Journal: 2026-10-12-drive-visibility-followups

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-11T23:01:02+00:00 -->
### repro · repro · A failed visibility read outside take_lease/save_pass's state-repo read ends a looping driver

#1144: state repo public, a member repo's visibility read fails (rate limit). guard_state's _fill stores None; check_or_refuse's leaks() counts None as not public and raises the plain PrivacyError leak refusal. take_lease/save_pass translate only VisibilityUnreadable into ForgeReadError, so _fail exits 2 and the loop ends, with a message claiming a leak. #1145: a VisibilityUnreadable from guard_write during a pass goes through _write -> _fail (typer.Exit 2), which the loop does not retry.

<!-- fr:journal kind=hypothesis scope=debug id=h1-guard-write-reachable created=2026-10-11T23:01:06+00:00 -->
### h1-guard-write-reachable · hypothesis · guard_write reaches a forge read during a driver pass

Ruled out for today's code: every driver write is event-only (dispatch, closeout, claims_released, the closeout rollback), so added_keys() is empty and guard_write returns before reading anything (as p1-r8 recorded). The path is latent: the first driver write that adds a key would end the loop on a transient read. The coordinator log's 00:11 stall ('driver died on GraphQL visibility read (#1134)') predates #1137's release, so it is #1134 itself, not guard_write.
