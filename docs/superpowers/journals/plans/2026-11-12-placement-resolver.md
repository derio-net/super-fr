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

<!-- fr:journal kind=decision scope=plan id=placement-resolver-shell-names created=2026-11-12T13:06:04+00:00 phase=1 -->
### placement-resolver-shell-names · decision · Shell variable names come from the resolver's one table, not from the kind name (phase 1)

`fr.artifacts.paths._TABLE` holds (kind, repo-relative path, shell suffix), and
KIND_DIRS and `shell_name` are both derived from it. The plan names both
`kind_dir("plan", …)` and `FR_PLANS_DIR`, so the variable cannot be the upper-cased
kind. Entries that name a file (plan-config, models, trackers) end in `_FILE`, not
`_DIR`. Phase 6's hooks read these names.

<!-- fr:journal kind=decision scope=plan id=placement-resolver-locators-stay-enumerated-in-registry created=2026-11-12T13:06:04+00:00 phase=1 -->
### placement-resolver-locators-stay-enumerated-in-registry · decision · Registry locators are built with paths.repo_glob; the kind enumeration stays in registry.py (phase 1)

A locator table keyed by kind name in paths.py tripped
test_tripwire_artifact_kinds (only fr.artifacts.registry may enumerate kinds). Each
ArtifactKind now writes `locator=repo_glob("<dir kind>", "<pattern>")`; the
`profiles` and `agents` locators stay literal, because they are repo configuration
(`.devcontainer/`, `.claude/agents/`) that no placement moves.

<!-- fr:journal kind=discovery scope=plan id=placement-resolver-space-for-is-filesystem-only created=2026-11-12T13:06:04+00:00 phase=1 -->
### placement-resolver-space-for-is-filesystem-only · discovery · space_for reads the switch ref from the filesystem, so a lookup spawns no git process (phase 1)

resolve_logical runs once per row reference in a fold, so `space_for` checks for
`refs/remotes/origin/fr` through the common git dir (a loose ref or a packed-refs
line, worktrees followed through `.git` gitdir/commondir). It runs `git show` only
when the ref exists. The stealth marker is read as an optional `placement` key in
the `.fr-isolation` marker (phase 4 writes it). A logical ref found in a feature root
outside the repo resolves to an absolute path, which `repo_root / found` still reads
correctly.

<!-- fr:journal kind=finding scope=plan id=placement-resolver-row-ci-ahead-of-shell-side created=2026-11-12T13:06:04+00:00 phase=1 state=open review_scope=in -->
### placement-resolver-row-ci-ahead-of-shell-side · finding [open] (reviewer: in scope) · placement-resolver is ci while the tripwire still has 57 PENDING modules and the shell side is unbuilt (phase 1)

The plan's step moves the row to `ci` in phase 1. Its acceptance text also covers
hooks, the OpenCode plugin, the Hermes hook and CI templates, which phases 2 and 6
build, and the Python tripwire allowlists 57 modules until phase 2. The row's note
says so. Phases 2 and 6 should extend the row's levels when they land, or the row
should go back to a debt status until they do.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-12T13:06:04+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

the smoke's module was a five-line placeholder that task 2 replaced wholesale; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-12T13:06:04+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

cleaned: the kind-name locator table first put in paths.py tripped the artifact-kinds tripwire, so it became repo_glob(kind, pattern) with the enumeration left in registry.py

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-12T13:06:04+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the command is a thin adapter over paths_answers (the one function shell and JSON share); nothing duplicated to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-12T13:06:04+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

the detector is two small predicates and one walk; PENDING was pasted from its own output, so nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-11-12T13:06:04+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

a scenario, a row move and docs prose; no code to clean
