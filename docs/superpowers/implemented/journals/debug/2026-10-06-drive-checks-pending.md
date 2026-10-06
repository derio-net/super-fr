# Journal: 2026-10-06-drive-checks-pending

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-06T08:02:18+00:00 -->
### repro · repro · gh's 'no checks reported' escapes pr_required_checks as a GhError

Observed live (#952, fr 5.2.9): `warning: a forge read failed: no checks reported on the '<branch>' branch; pass skipped` right after a batch pushed a new head. #947: `batch merge --yes` crashed in its post-push check wait the same way. gh 2.101.0 has TWO no-checks messages (strings of the binary): `no required checks reported on the '%s' branch` (checks exist, none required) and `no checks reported on the '%s' branch` (the head has none at all, what a just-pushed head says, with or without --required). `RealGhClient.pr_required_checks` maps only the first to []; the second propagates as GhError.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-10-06T08:03:23+00:00 -->
### root-cause · root-cause · pr_required_checks recognises one of gh's two no-checks answers; merge paths apply only required checks

One cause, two commands: the unrecognised 'no checks reported' is raised (1) inside the driver's live-read try block -> ForgeReadError -> whole pass skipped (#952), and (2) from wait_required_checks inside batch merge's post-push _checks -> crash (#947). Mapping it to [] is necessary but not sufficient: batch merge's wait then accepts [] after a 120s grace as 'none required' and merges a head with no CI evidence at all, because merge_one/merge_ready gate on required checks only (#880). R4 (`batch_drive.checks_verdict`: required, else all checks, nothing reported = pending, only `ci none` merges bare) is the rule that tells 'none required' from 'not registered yet', so the fix routes both merge paths through it.

<!-- fr:journal kind=finding scope=debug id=fix created=2026-10-06T09:07:14+00:00 state=fixed -->
### fix · finding [fixed] · Both no-checks answers read as []; both merge paths apply R4 live

RealGhClient: `pr_required_checks` and the new `pr_checks` (every check) map gh's `no required checks reported` AND `no checks reported` to []; any other GhError still raises (a real read failure still skips the pass, #910). `batch_merge.live_checks` applies `batch_drive.checks_verdict` (R4) to live reads; `merge_ready` (#880) and `merge_one`'s check wait (#947) both use it, so a head with no check yet is pending until it has one, and only `ci none` merges without one. The client's `wait_required_checks` and its 120s grace are gone: R4 is what tells 'none required' from 'not registered yet'. `MergeContext` gains `sleep` and `ci_none`; `ci_none_at` is shared by the driver and `batch merge`. Tests first (red at a0…): test_forge_adapter_batch_ops.py#test_a_head_with_no_checks_registered_yet_reads_as_none_not_an_error, test_triage_batch_merge_ready.py#test_with_no_required_checks_every_check_gates_the_merge, #test_after_an_update_push_no_check_yet_is_waited_for_not_a_crash, #test_a_head_whose_checks_never_appear_is_not_merged.

<!-- fr:journal kind=review scope=debug id=review created=2026-10-06T09:07:18+00:00 -->
### review · review · Independent review: one finding, fixed; one noted

A fresh-context reviewer read the diff. (1) The driver caches its MergeContext across passes, so the new `ci_none` froze at the first merge attempt while each pass's own verdict re-read it: a repo declaring `ci none` mid-drive would be judged green and then refused by merge_ready until restart. Fixed: `merge_ctx` refreshes `ci_none` every call; pinned by test_triage_batch_drive_cmd.py#test_a_ci_none_declared_mid_drive_reaches_the_merge_too (red without the refresh, green with it). (2) Noted, not changed: with no required check registered yet but an optional check already green, R4 reads green; unchanged from the driver's existing rule, and the forge's branch protection still refuses such a merge (reported as a MergeStopError).
