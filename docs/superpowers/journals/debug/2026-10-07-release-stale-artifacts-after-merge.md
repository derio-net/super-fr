# Journal: 2026-10-07-release-stale-artifacts-after-merge

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-07T02:41:33+00:00 -->
### repro · repro · Release 37562684100 on b44d9f45 (#1058) refuses: runs/ and usage/ files of run 2026-10-06-feat-triage-batch-adopt staged outside the allowed set

release.py runs fr migrate artifacts --yes at the new number; on b44d9f45 it rewrites both (run cursor schema_version 8->9, usage 1->2, stamp only, no body change); verify_staged admits only version values, consumed fragments and widened plan ceilings, so it refuses.
