<!-- fr:journal-schema=3 -->
# Journal: 2026-11-12-placement-resolver

<!-- fr:journal kind=decision scope=plan id=placement-one-layout created=2026-11-12T11:58:25+00:00 -->
### placement-one-layout · decision · Quiet and stealth keep the repo layout below a per-feature root

Under quiet and stealth a feature's artifacts live at features/<feature-id>/ with the repo
layout unchanged below it (docs/superpowers/..., docs/acceptance/features/...); the root is the
fr worktree (quiet) or <tracking worktree>/<host>--<owner>--<repo>/ (stealth). The feature id is
fr's branch slug. The resolver changes the root, never the relative layout; cross-feature reads
iterate feature_roots(). Placement precedence: stealth marker/state, then a valid origin/fr
switch, then repo. `up --no-fetch` reads the last fetched origin/fr and says so.

<!-- fr:journal kind=decision scope=plan id=placement-rows-added-at-planning created=2026-11-12T11:58:25+00:00 -->
### placement-rows-added-at-planning · decision · Three rows added at planning for R1, R25 and R26

placement-resolver (R1), placement-merged-status (R25, R17 quiet/stealth clause) and
placement-fr-enabled (R26) had no row; each phase needs a requirement of its own. Each carries a
candidate scenario under tests/scenarios/. Deferral #1412 (record kind v10 freeze) is untouched:
plan 3 changes no record field. #1379 (plan 2 tracking) is plan 2's and stays as is.
