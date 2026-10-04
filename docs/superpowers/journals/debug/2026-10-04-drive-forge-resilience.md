# Journal: 2026-10-04-drive-forge-resilience

<!-- fr:journal kind=repro scope=debug id=82958a6fae6b created=2026-10-04T04:26:44+00:00 -->
### 82958a6fae6b · repro · A stalled forge read hangs the drive loop; its failure then ends it (exit 2)

Live (wave-driver Test Plan 16, 2026-10-03, GitHub API degradation): the per-pass re-collect's `gh issue list --limit 1000` stalled ~16 min, then failed with `Post .../graphql: unexpected EOF`; `fr triage batch drive` (loop mode) printed `error: ...` and exited 2. A ready, green PR sat unmerged throughout. Repro in tests: (a) `fr.gh._run_gh` against a `gh` that never returns blocks forever; (b) make the drive's re-collect raise `ForgeError` on one pass in loop mode → exit 2 instead of a retry after --interval.
