# Journal: 2026-10-06-drive-checks-pending

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-06T08:02:18+00:00 -->
### repro · repro · gh's 'no checks reported' escapes pr_required_checks as a GhError

Observed live (#952, fr 5.2.9): `warning: a forge read failed: no checks reported on the '<branch>' branch; pass skipped` right after a batch pushed a new head. #947: `batch merge --yes` crashed in its post-push check wait the same way. gh 2.101.0 has TWO no-checks messages (strings of the binary): `no required checks reported on the '%s' branch` (checks exist, none required) and `no checks reported on the '%s' branch` (the head has none at all, what a just-pushed head says, with or without --required). `RealGhClient.pr_required_checks` maps only the first to []; the second propagates as GhError.
