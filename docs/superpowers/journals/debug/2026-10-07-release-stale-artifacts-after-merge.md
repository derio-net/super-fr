# Journal: 2026-10-07-release-stale-artifacts-after-merge

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-07T02:41:33+00:00 -->
### repro · repro · Release 37562684100 on b44d9f45 (#1058) refuses: runs/ and usage/ files of run 2026-10-06-feat-triage-batch-adopt staged outside the allowed set

release.py runs fr migrate artifacts --yes at the new number; on b44d9f45 it rewrites both (run cursor schema_version 8->9, usage 1->2, stamp only, no body change); verify_staged admits only version values, consumed fragments and widened plan ceilings, so it refuses.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-10-07T02:41:36+00:00 -->
### root-cause · root-cause · A PR's live artifacts carry the stamps of the registry it was tested with; main's registry moved before it merged

#1041 (91742128, merged 02:29) bumped run 8->9 and usage 1->2 and migrated main's own artifacts. #1058 last merged main before #1041, so its fr wrote and validated its cursor and usage file at 8 and 1, and PR CI (the merge ref as of its last push) was green. #1058 merged at 02:35 on top of #1041 with no re-test. Nothing between merge and release re-checks a PR's artifacts against the base's registry; the release's own migration is the first to see it and correctly refuses. Needed only: an artifact-version bump merging while another PR carrying live artifacts of that kind is open.
