# Journal: 2026-09-26-version-bump-churn

<!-- fr:journal kind=decision scope=spec id=d1-intent-on-merge created=2026-09-26T08:04:32 -->
### d1-intent-on-merge · decision · PRs declare a bump in a .changes/ fragment; the release workflow on main assigns the number

Operator chose intent-in-PR / number-on-merge over consolidating the version surfaces.
Consolidation alone shrinks a 13-file conflict to a one-line conflict but keeps the
collision and the CI rerun; only moving the number out of the PR removes both.

<!-- fr:journal kind=decision scope=spec id=d2-no-consolidation created=2026-09-26T08:04:32 -->
### d2-no-consolidation · decision · Version surfaces stay as they are; only the release bot writes them

Once PRs never edit a version surface, bump-version.py already writes all 12 files plus uv.lock.

<!-- fr:journal kind=decision scope=spec id=d3-reports-in-scope created=2026-09-26T08:04:32 -->
### d3-reports-in-scope · decision · Committed acceptance reports drop aggregates; add inserts rows by capability

Operator put the report conflicts in scope. The row-count stamp and status table are shared
write hotspots. Exploration also found append_row always writes at EOF of matrix.yaml,
so insert-by-capability is included to make "different rows do not conflict" actually true.

<!-- fr:journal kind=decision scope=spec id=d4-no-test-skip-guard created=2026-09-26T08:04:32 -->
### d4-no-test-skip-guard · decision · No general version-only test-skip guard

The release commit is pushed with GITHUB_TOKEN, which triggers no workflow, so it reruns nothing.

<!-- fr:journal kind=discovery scope=spec id=ruleset-allows-bot-push created=2026-09-26T08:04:32 -->
### ruleset-allows-bot-push · discovery · main's ruleset enforces only deletion and non_fast_forward

GET /repos/derio-net/super-fr/rules/branches/main returns ["deletion","non_fast_forward"] (2026-09-26),
so a GITHUB_TOKEN release commit can fast-forward main. AGENTS.md's "branch-protection blocks direct
commits" overstates it; the spec corrects the sentence and requires a bypass actor if rules tighten.

<!-- fr:journal kind=discovery scope=spec id=floors-need-a-guard created=2026-09-26T08:04:32 -->
### floors-need-a-guard · discovery · Hand-written fr_version floors name a release number the PR no longer knows

SCOPE_FR_VERSION / WORKFLOW_FR_VERSION and plan_ops refusal text; three introduced in two months.
Spec §3.E adds a PR-time and a release-time guard instead of a mechanism.
