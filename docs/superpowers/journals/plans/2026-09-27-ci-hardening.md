# Journal: 2026-09-27-ci-hardening

<!-- fr:journal kind=decision scope=plan id=one-agentic-phase created=2026-09-27T14:38:41+00:00 -->
### one-agentic-phase · decision · One agentic phase, tier standard

Change is .github/** + two test files + matrix; no second phase to smoke. No tracking_issue set (brief: members stay batch-owned).

<!-- fr:journal kind=discovery scope=plan id=sha-pins-reresolved-no-drift created=2026-09-27T14:51:16+00:00 phase=1 -->
### sha-pins-reresolved-no-drift · discovery · Every spec §3.A row re-resolved identically via gh api on 2026-09-27 (phase 1)

Re-resolved all 12 rows of spec §3.A through `gh api repos/<o>/<r>/git/ref/tags/<tag>` (dereferencing annotated tag objects via `git/tags/<sha>` to their commit) and confirmed the exact vX.Y.Z version tag dereferences to the same commit. Every commit SHA matched the spec table exactly — no tag had moved, so no unreviewed commit was pinned and no finding was needed.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-09-27T14:51:16+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

acceptance status moves and verification runs only, no code written, so nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-09-27T14:51:16+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

_ci_ok_step's "every other job id" check already reuses _load_ci_workflow directly (other_job_ids = set(jobs) - {"ci-ok"}) rather than a second loader, so there was nothing to consolidate.
