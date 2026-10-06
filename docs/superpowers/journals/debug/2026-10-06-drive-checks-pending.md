# Journal: 2026-10-06-drive-checks-pending

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-06T08:02:18+00:00 -->
### repro · repro · gh's 'no checks reported' escapes pr_required_checks as a GhError

Observed live (#952, fr 5.2.9): `warning: a forge read failed: no checks reported on the '<branch>' branch; pass skipped` right after a batch pushed a new head. #947: `batch merge --yes` crashed in its post-push check wait the same way. gh 2.101.0 has TWO no-checks messages (strings of the binary): `no required checks reported on the '%s' branch` (checks exist, none required) and `no checks reported on the '%s' branch` (the head has none at all, what a just-pushed head says, with or without --required). `RealGhClient.pr_required_checks` maps only the first to []; the second propagates as GhError.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-10-06T08:03:23+00:00 -->
### root-cause · root-cause · pr_required_checks recognises one of gh's two no-checks answers; merge paths apply only required checks

One cause, two commands: the unrecognised 'no checks reported' is raised (1) inside the driver's live-read try block -> ForgeReadError -> whole pass skipped (#952), and (2) from wait_required_checks inside batch merge's post-push _checks -> crash (#947). Mapping it to [] is necessary but not sufficient: batch merge's wait then accepts [] after a 120s grace as 'none required' and merges a head with no CI evidence at all, because merge_one/merge_ready gate on required checks only (#880). R4 (`batch_drive.checks_verdict`: required, else all checks, nothing reported = pending, only `ci none` merges bare) is the rule that tells 'none required' from 'not registered yet', so the fix routes both merge paths through it.
