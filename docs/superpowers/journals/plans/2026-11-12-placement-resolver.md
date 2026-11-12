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

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-11-12T13:26:46+00:00 phase=1 -->
### review-phase-1 · review · Phase 1 review (resolver): five in-scope findings, all fixed; one out of scope, filed as #1419 (phase 1)

Independent reviewer over `git diff 0b0585288..9874212ba`. Repo-placement locators are
byte-identical to the old ones, `fr settings paths` quotes with shlex and exits 2 on bad
flags and settings refusals, the scenario is wired, docstring exclusion and the stale-entry
check of the tripwire work, and the change fragment fits the one-PR run. Fixes landed in
4126c3299, bc85621d4, 9a4b76514, 178adaf56 and 5e7703c67.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-12T13:26:46+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Tripwire missed Path("docs") / "superpowers", Path("docs", ...), joinpath, segment tuples and "superpowers/..." right segments; 7 unlisted modules hardcoded paths and passed (phase 1)

Phase 2's proof (PENDING ends empty) would have gone green with records, usage files and renames still writing into the repo.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-12T13:26:46+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · placement-resolver row moved to ci while its acceptance text (all surfaces read the resolver) is not yet true (phase 1)

The report and fr debt would show unpaid debt as paid.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-12T13:26:46+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · space_for took any non-repo placement on any origin/fr as a switch, unvalidated (phase 1)

placement: stealth or foo, or garbage YAML on an unrelated fr branch, made every logical resolve refuse with a misleading message.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-12T13:26:46+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · resolve_logical's absolute return for out-of-repo feature roots made as_path_ref and origin_spec_path emit <repo>:/abs/path refs (phase 1)

Broken refs, and a local home path leaking into derived reports.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-12T13:26:46+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · KIND_DIRS lacked directories live code uses (implemented/usage, archived-specs, implemented/audits) (phase 1)

The names fr settings paths prints would have kept moving after phase 6's hooks start reading them.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-12T13:26:46+00:00 phase=1 state=open review_scope=out -->
### p1-r6 · finding [open] (reviewer: out of scope) · branch_slug is not injective (feat/a__b and feat__a/b share a slug), now reused as the quiet/stealth feature id (phase 1)

Pre-existing in isolation's worktree naming; filed as derio-net/super-fr#1419.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-12T13:26:46+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Tripwire missed Path("docs") / "superpowers", Path("docs", ...), joinpath, segment tuples and "superpowers/..." right segments; 7 unlisted modules hardcoded paths and passed (phase 1)

4126c3299: the tripwire splits every join into segments and flags docs followed by superpowers/acceptance across / chains, Path(), joinpath, os.path.join, other calls and tuples/lists; planted cases for all eight forms; PENDING re-derived 57 -> 64 and every module outside it scanned clean.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-12T13:26:46+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: placement-resolver row moved to ci while its acceptance text (all surfaces read the resolver) is not yet true (phase 1)

bc85621d4: row back to not-implemented with phase 1's unit refs kept; it moves to ci when phase 2 empties PENDING and phase 6 lands the shell side.

<!-- fr:journal kind=finding scope=plan id=placement-resolver-row-ci-ahead-of-shell-side-resolved created=2026-11-12T13:26:46+00:00 phase=1 state=fixed resolves=placement-resolver-row-ci-ahead-of-shell-side -->
### placement-resolver-row-ci-ahead-of-shell-side-resolved · finding [fixed] · resolves placement-resolver-row-ci-ahead-of-shell-side: placement-resolver is ci while the tripwire still has 57 PENDING modules and the shell side is unbuilt (phase 1)

Same defect as p1-r2, fixed by bc85621d4.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-12T13:26:46+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: space_for took any non-repo placement on any origin/fr as a switch, unvalidated (phase 1)

9a4b76514: the switch is parsed by parse_settings_text (servable=False skips only the placement check); quiet is the switch, stealth is refused by R24's rule, unknown values/keys and invalid YAML refuse in the loader's wording, each naming refs/remotes/origin/fr:settings.yaml. An fr branch saying repo, or with no settings.yaml, stays no switch.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-12T13:26:46+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: resolve_logical's absolute return for out-of-repo feature roots made as_path_ref and origin_spec_path emit <repo>:/abs/path refs (phase 1)

178adaf56: a Resolved result (feature root + relative path) and resolve_logical_at; as_path_ref and origin_spec_path always print the relative path; test with a fake out-of-repo feature root asserts no absolute path appears.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-12T13:26:46+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: KIND_DIRS lacked directories live code uses (implemented/usage, archived-specs, implemented/audits) (phase 1)

5e7703c67: usage-archived, spec-legacy-archived and audit-archived added with shell names; existing values byte-identical; EXPECTED_DIRS updated.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-12T13:26:46+00:00 phase=1 state=open resolves=p1-r6 out_of_scope=true -->
### p1-r6-resolved · finding [out-of-scope] · resolves p1-r6: branch_slug is not injective (feat/a__b and feat__a/b share a slug), now reused as the quiet/stealth feature id (phase 1)

branch_slug predates this plan and its collision already exists for isolation worktrees; tracked as derio-net/super-fr#1419.

<!-- fr:journal kind=decision scope=plan id=placement-callers-lazy-import-in-refs created=2026-11-12T14:36:21+00:00 phase=2 -->
### placement-callers-lazy-import-in-refs · decision · fr.refs imports the resolver inside its functions (phase 2) (phase 2)

`import fr` runs fr.parser, which imports fr.refs; a top-level `from fr.artifacts.paths import ...` there runs fr/artifacts/__init__.py, which reaches fr.spec and fr.parser while both are half-initialised (ImportError on _PHASE_FILE_RE). refs.py therefore imports kind_dir/space_for inside _resolve and the one other function that needs them. Every other converted module imports at the top and was checked with a fresh `import <module>`.

<!-- fr:journal kind=decision scope=plan id=placement-callers-scaffold-placeholders created=2026-11-12T14:36:21+00:00 phase=2 -->
### placement-callers-scaffold-placeholders · decision · scaffold templates take their directories from placeholders filled at import (phase 2) (phase 2)

The CI workflow and rule templates are full of braces, `${{ }}` and @@MARKERS@@, so f-strings are unusable. They now carry @@ACC_FRAGMENTS@@ / @@ACC_REPORT@@ and `_render_paths` fills them from KIND_DIRS once, at import; the rendered text is byte-identical (the scaffold tests are unchanged).

<!-- fr:journal kind=decision scope=plan id=placement-callers-row-spec-resolver created=2026-11-12T14:36:21+00:00 phase=2 -->
### placement-callers-row-spec-resolver · decision · gatebackfill.row_spec follows the resolver (phase 2) (phase 2)

Phase 1's review found row_spec checked `root / rel`, so a spec in a feature root outside the repo was missed. A logical spec origin now resolves through resolve_logical_at; a path origin is looked up in every feature_roots entry. The result is repo-relative under the repo and absolute elsewhere (as resolve_logical does). A new test pins the out-of-repo case.

<!-- fr:journal kind=discovery scope=plan id=placement-callers-validate-plans-shell created=2026-11-12T14:36:21+00:00 phase=2 -->
### placement-callers-validate-plans-shell · discovery · validate-plans.sh reads its directories from `fr settings paths --shell` with literal fallbacks (phase 2) (phase 2)

Both copies (scripts/ and packages/fr/src/fr/data/) changed identically: the script evals the resolver's FR_* lines when `fr` is on PATH and answers, else uses the repo layout's own literals (commented as such). The tripwire scans .py only; phase 6 owns the remaining shell surfaces. The script's pre-existing BSD-sed incompatibility on macOS is untouched.

<!-- fr:journal kind=discovery scope=plan id=placement-callers-registry-tripwire created=2026-11-12T14:36:21+00:00 phase=2 -->
### placement-callers-registry-tripwire · discovery · a kind-name tuple in batch_drive tripped the artifact-kinds tripwire (phase 2) (phase 2)

`tuple(KIND_DIRS[k] for k in ("plan", "spec", ...))` is a second enumeration of kinds. ARCHIVE_DIRS is now five subscripts, which the detector does not read as a list of names.

<!-- fr:journal kind=discovery scope=plan id=placement-callers-red-order created=2026-11-12T14:36:21+00:00 phase=2 -->
### placement-callers-red-order · discovery · the tripwire's RED was taken after the conversion, not before (phase 2) (phase 2)

The plan's steps remove modules from PENDING first and watch the tripwire name them. Here the 64 modules were converted in one sweep and PENDING emptied after, so the detector (which still fails a module with a literal left, as the scaffold and isolation/local.py leftovers showed) was the proof. PENDING's machinery is kept (empty): the stale-entry test and the 'only shrinks' contract are what the next exemption would need.

<!-- fr:journal kind=discovery scope=plan id=placement-callers-pages-restamped created=2026-11-12T14:36:21+00:00 phase=2 -->
### placement-callers-pages-restamped · discovery · twelve docs pages were restamped, none edited (phase 2) (phase 2)

The sweep touched modules covered by twelve pages (`fr docs check` said so); none describes a path or behaviour that changed, so each reviewed stamp names this phase and says so.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-12T14:36:21+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

pure literal-to-resolver rewrites; each module was touched once and the result is the shortest spelling (KIND_DIRS constant or kind_dir(space_for(root))), nothing left to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-12T14:36:21+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

same mechanical rewrites as T1; the per-module constants became derivations of the table, no duplicate left behind
