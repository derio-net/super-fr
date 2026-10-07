# Journal: 2026-10-07-release-stale-artifacts-after-merge

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-07T02:41:33+00:00 -->
### repro · repro · Release 37562684100 on b44d9f45 (#1058) refuses: runs/ and usage/ files of run 2026-10-06-feat-triage-batch-adopt staged outside the allowed set

release.py runs fr migrate artifacts --yes at the new number; on b44d9f45 it rewrites both (run cursor schema_version 8->9, usage 1->2, stamp only, no body change); verify_staged admits only version values, consumed fragments and widened plan ceilings, so it refuses.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-10-07T02:41:36+00:00 -->
### root-cause · root-cause · A PR's live artifacts carry the stamps of the registry it was tested with; main's registry moved before it merged

#1041 (91742128, merged 02:29) bumped run 8->9 and usage 1->2 and migrated main's own artifacts. #1058 last merged main before #1041, so its fr wrote and validated its cursor and usage file at 8 and 1, and PR CI (the merge ref as of its last push) was green. #1058 merged at 02:35 on top of #1041 with no re-test. Nothing between merge and release re-checks a PR's artifacts against the base's registry; the release's own migration is the first to see it and correctly refuses. Needed only: an artifact-version bump merging while another PR carrying live artifacts of that kind is open.

<!-- fr:journal kind=finding scope=debug id=fix-release-stamp-allowance created=2026-10-07T02:46:21+00:00 state=fixed -->
### fix-release-stamp-allowance · finding [fixed] · release.py admits a live artifact's stamp moving up; main's two stale artifacts migrated

Repair: chore(fr) migrate commit moves runs/2026-10-06-feat-triage-batch-adopt.yaml 8->9 and usage/ 1->2 (stamp only). Defect fix: verify_staged admits, for live run/usage/journal/matrix paths only (never implemented/), a diff that is exactly one stamp line moving up (or one missing stamp inserted); body lines, a stamp moving down, archives and non-artifacts still refuse. The staged tree is still tested before the push. Pinned by tests/unit/test_release_script.py::test_a_stamp_only_migration_of_live_artifacts_rides_the_release_commit (RED reproduced the production error verbatim), ::test_inserting_a_missing_stamp_rides_the_release_commit and ::test_a_migration_beyond_a_live_stamp_refuses[5 cases].

<!-- fr:journal kind=review scope=debug id=review-1 created=2026-10-07T02:51:08+00:00 -->
### review-1 · review · Dispatched reviewer: 3 in-scope (r1-r3, low), 2 out (r4 fixed anyway, r5 info) — all in-scope fixed

r1: carrier not tied to path; inserted/moved/duplicate stamps admitted -> fixed: carrier by suffix, exactly one stamp in the staged file, stamp in the writer's header region. r2: records (runs/*.records/*.yaml) not covered, implemented/ journals not excluded, docstring wrong -> fixed + spec/profiles exclusion documented. r3: missing cases -> matrix, record, insert-after-header positives; cross-carrier, duplicate, inserted-below-key, moved-below-key, implemented-journal refusals. r4 (out, fixed anyway): -U0 parsed with split('\n') + CR strip; CRLF and U+2028 tests. r5 (out, info): new stamp == current_version is enforced by validate_repo in the pre-push staged suite. 79 release tests pass.
