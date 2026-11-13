<!-- fr:journal-schema=4 -->
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

<!-- fr:journal kind=review scope=plan id=review-phase-2 created=2026-11-12T14:55:43+00:00 phase=2 -->
### review-phase-2 · review · Phase 2 review (callers on the resolver): four in-scope findings, fixed (the fourth partly, by decision) (phase 2)

Independent reviewer over `git diff 3fade42ec..0ed4dd4c8`. Every rewrite read is
byte-identical under `repo`; no root is joined at import and space_for is never cached;
the scaffold placeholders always render; both validate-plans.sh copies are identical and
eval-safe; PENDING is empty with no new exemption; the 12 restamps are honest. Fixes landed
in bc273c8c0, 2caf77995, 0a0585ccb (and its parent) and 6a3c8d75c.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-12T14:55:43+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · validate-plans.sh swallowed every fr settings paths failure, including deliberate placement refusals, and validated the repo literals; VK_REPO_ROOT could disagree with REPO_ROOT (phase 2)

Under quiet it would have reported success over the wrong directory.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-12T14:55:43+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · plan_ops derived the artifact root by .parent walks and hardcoded plan directory names (phase 2)

Under the features/<id>/ layout, superpowers_dir.parent.parent is not the repo root.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-12T14:55:43+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · Tripwire missed bare "superpowers", .name comparisons, concatenation and "/".join; isolation/local.py hardcoded _ARCHIVED_KINDS (phase 2)

The empty-PENDING claim was stronger than the detector.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-12T14:55:43+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · logical._resolve re-ran space_for's filesystem reads per ref; fr.refs uses function-local imports (phase 2)

A hot-path cost, not a correctness issue.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-12T14:55:43+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: validate-plans.sh swallowed every fr settings paths failure, including deliberate placement refusals, and validated the repo literals; VK_REPO_ROOT could disagree with REPO_ROOT (phase 2)

bc273c8c0: fall back to the literals only when fr is absent or lacks the subcommand; any other failure prints fr's stderr and exits 2; fr runs with VK_REPO_ROOT unset from $REPO_ROOT; tests for absent, old, refusing and working fr. Printed paths remain symlink-resolved; the script uses them as given.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-12T14:55:43+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: plan_ops derived the artifact root by .parent walks and hardcoded plan directory names (phase 2)

2caf77995: plan_ops finds the feature root via KIND_DIRS/feature_roots from the real repo root (_feature_root_of); _find_prior_rework now looks in archived-plans for an implemented parent, which it previously missed.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-12T14:55:43+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: Tripwire missed bare "superpowers", .name comparisons, concatenation and "/".join; isolation/local.py hardcoded _ARCHIVED_KINDS (phase 2)

0a0585ccb, 6a3c8d75c: the detector flags bare "superpowers" (exempt only as a KIND_DIRS/kind_dir key), + concatenation and "/".join, with planted cases; apply_cmd.py and isolation/local.py _ARCHIVED_KINDS now derive from the resolver; PENDING stays empty. A bare "acceptance" is not flagged: it is a feature/section key in ~75 places.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-12T14:55:43+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: logical._resolve re-ran space_for's filesystem reads per ref; fr.refs uses function-local imports (phase 2)

logical.feature_roots_of plus an optional roots= lets path_view and check compute the space once per batch; the single-ref API is unchanged. The fr.refs function-local imports stay: they correctly break the fr.artifacts -> fr.spec -> fr.refs cycle, and a leaf-module move buys nothing further.

<!-- fr:journal kind=decision scope=plan id=quiet-policy-source-is-fr-branch created=2026-11-12T17:57:33+00:00 phase=3 -->
### quiet-policy-source-is-fr-branch · decision · Under quiet the policy keys are read from the fr branch, so fr needs default-branch protection (phase 3)

Per R2/R23 the settings are read at the placement's own location: under quiet the policy keys
(artifacts.*, forge.*, git.*) come from `settings.yaml` on `origin/fr`, read by commit, and a
`.fr/settings.yaml` on the default branch is ignored (the loader's note says so). Consequence,
flagged by the phase-3 security review: anyone who can push to `fr` can change the policy, so
the `fr` branch needs the same branch protection as the default branch. Not changed in code
(that would be a spec change); stated in the quiet section of docs/explainers/01-fr-goal.md and
in the header `fr settings init --quiet` writes into the switch.

<!-- fr:journal kind=decision scope=plan id=quiet-feature-id-collision-refused created=2026-11-12T17:57:33+00:00 phase=3 -->
### quiet-feature-id-collision-refused · decision · A branch whose feature id another branch holds is refused under quiet, naming both (gh#1419) (phase 3)

`branch_slug` is not injective (`feat/a__b` and `feat__a/b` share `feat__a__b`), and under quiet
the slug is the feature PATH on `fr`. `fr.placement.quiet.check_feature_id` lists local and
origin branch names from the filesystem and refuses when another one maps to the same id (and a
feature branch named `fr`), at `up` and in every quiet `space_for`. That keeps R23's "each commit
touches one feature's path" true. gh#1419 itself (the slug) stays open: repo and the isolation
worktree names are unchanged.

<!-- fr:journal kind=decision scope=plan id=quiet-fr-worktree-ownership-check created=2026-11-12T17:57:33+00:00 phase=3 -->
### quiet-fr-worktree-ownership-check · decision · The shared fr worktree path is reused only when it is this repo's worktree on refs/heads/fr (phase 3)

`~/.cache/fr/worktrees/<name>/fr` is keyed by the repo's directory name (the plan's path shape,
as isolation names worktrees), so two repos of the same name share it. Before reusing it,
`ensure_worktree` and `fast_forward` require `git rev-parse --git-common-dir` there to be this
repo's common dir and HEAD to be refs/heads/fr, refusing with both repos named (security review
note 1). Verified pairs are cached per process.

<!-- fr:journal kind=decision scope=plan id=quiet-reachability-refusal-all-repos created=2026-11-12T17:57:33+00:00 phase=3 -->
### quiet-reachability-refusal-all-repos · decision · up and run start refuse an unreachable origin for every repo with an origin, not only quiet ones (phase 3)

R23 fetches the switch at up and run start and refuses when origin is unreachable; a repo cannot
know it is not quiet without reaching origin, so the refusal applies to any repo with an origin
(no origin is repo, with no fetch). `--no-fetch` reads the last fetched origin/fr and prints that
it did. Existing fixtures were fixed, never the rule: test_isolation_branch_classify's GitRunner
answers the switch probe as absent (those tests break origin on purpose to make the BRANCH probe
unknown); test_isolation's fetch-failure test now asserts the refusal and then the old HEAD
fallback under --no-fetch; repo-settings-file.sh uses stealth for the not-yet-available case.
An origin fr branch that is gone deletes the stale tracking ref, so the sticky check notices.

<!-- fr:journal kind=decision scope=plan id=quiet-artifact-root-scope created=2026-11-12T17:57:33+00:00 phase=3 -->
### quiet-artifact-root-scope · decision · Which writers moved to the fr worktree in phase 3, and what stays at the product toplevel (phase 3)

Phase 2 left ~150 sites joining `repo_root / KIND_DIRS[...]` constants, which under quiet would
still write on the product branch. `fr.artifacts.paths.artifact_root(root)` (the feature root)
now serves runs and records (run/model, record/model, run/cursors, run/adopt, run_cmd, pickup,
git_policy/templates, acceptance/amend's run lookup), journals, usage files and plan staging
(plan_ops/plan_cmd group by owning worktree). Repo configuration that a repo owner authors
(workflows, verifications, models, trackers, plan-config) stays at the product toplevel. Every
other writer still joins the toplevel; under quiet the commit seam refuses to commit an artifact
path inside the product checkout, so none reaches a product branch (finding
quiet-unconverted-writers). Also: `.fr/settings.yaml` saying `placement: quiet` is refused,
pointing at `fr settings init --quiet`; plan create installs no validator wrapper under quiet.

<!-- fr:journal kind=finding scope=plan id=quiet-unconverted-writers created=2026-11-12T17:57:33+00:00 phase=3 state=open review_scope=out -->
### quiet-unconverted-writers · finding [open] (reviewer: out of scope) · Writers not yet on artifact_root are refused under quiet instead of writing to the fr branch (phase 3)

Acceptance fragments (`fr acceptance add/set-status/amend`, the fold's working-tree read),
archive/closeout, debt, gatebackfill, triage snapshots, ops evidence, the usage backfill, and
isolation rename/preserve still join the product toplevel. Under quiet their commit is refused at
the seam (nothing reaches the product branch, which the placement-quiet row claims), but they
leave their file uncommitted in the product checkout, and readers among them see nothing. The
acceptance fold over the fr branch and archive belong with phase 5 (R17/R25 under quiet);
`isolation rename` changes a quiet feature's id and needs its own design.

<!-- fr:journal kind=discovery scope=plan id=quiet-red-order-p3-t4 created=2026-11-12T17:57:33+00:00 phase=3 -->
### quiet-red-order-p3-t4 · discovery · Task 4's implementation was written before its RED was observed; RED confirmed afterwards (phase 3)

test_push_quiet.py and atomic_push were written in one sitting while a suite ran. RED was then
taken honestly by restoring push.py and push_cmd.py to HEAD: 5 of 6 tests failed (the subject-check
test already held); the implementation was put back byte for byte and all 6 pass.

<!-- fr:journal kind=discovery scope=plan id=quiet-probe-wrote-into-workspace created=2026-11-12T17:57:33+00:00 phase=3 -->
### quiet-probe-wrote-into-workspace · discovery · A debugging probe's `fr plan create` committed into this workspace; dropped, tests now chdir (phase 3)

`fr plan create` resolves its repo from the cwd, not VK_REPO_ROOT. A scratch probe run from this
worktree created and committed plan `2026-11-12-q` here (chore(fr), unpushed). The commit was
dropped with `git reset --mixed HEAD~1` and its files removed before anything was pushed; every
quiet test fixture now `monkeypatch.chdir`s into its sandbox workspace.

<!-- fr:journal kind=discovery scope=plan id=quiet-acceptance-check-foreign-rows created=2026-11-12T17:57:33+00:00 phase=3 -->
### quiet-acceptance-check-foreign-rows · discovery · fr acceptance check --no-fetch exits 1 on site-* rows merged on origin/main after this base (phase 3)

23 errors, all on rows site-front-page-second-pass-published, site-landing-* and
site-wave-driver-and-exit-gates-pages: the fold reads origin/main's fragments while their spec
and tests are not on this branch. Nothing from this phase; it clears when the branch takes
origin/main (delivery's call). placement-quiet itself checks clean.

<!-- fr:journal kind=discovery scope=plan id=quiet-init-subject-through-templates created=2026-11-12T17:57:33+00:00 phase=3 -->
### quiet-init-subject-through-templates · discovery · The first full suite caught init --quiet's chore(fr) subject bypassing the R14 seam (phase 3)

test_every_chore_fr_producer_goes_through_the_seam failed on commands/settings_cmd.py: the root
commit of `fr` was written by commit-tree with a literal subject. It now goes through
`fr_message` (the repo's templates and the Fr-Commit trailer). The full suite was re-run after.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-11-12T17:57:33+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

new module (fr/placement/quiet.py) plus a rewrite of space_for that replaced its two switch helpers outright; the old _has_switch_ref/_switch_placement were deleted in the same change, nothing duplicated remained

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-12T17:57:33+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

one shared fetch_placement called by all three targets and run start; the fixture edits are test-only; nothing to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-11-12T17:57:33+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

artifact_root is the one helper every converted site calls; worktree_of is shared by plan_ops and plan_cmd; the commit reroute is two small functions on the existing seam

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t4 created=2026-11-12T17:57:33+00:00 phase=3 -->
### no-refactor-p3-t4 · discovery · no-refactor-because P3.T4 (phase 3)

atomic_push sits beside push and reuses run_git/_git/FORCE_FLAGS; push_cmd gained one dispatch helper; nothing left to merge

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t5 created=2026-11-12T17:57:33+00:00 phase=3 -->
### no-refactor-p3-t5 · discovery · no-refactor-because P3.T5 (phase 3)

init --quiet is one function over git plumbing; render_init gained a placement argument instead of a second renderer

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t6 created=2026-11-12T17:57:33+00:00 phase=3 -->
### no-refactor-p3-t6 · discovery · no-refactor-because P3.T6 (phase 3)

a scenario script, its one-line wiring, docs and the row move; no code to clean

<!-- fr:journal kind=review scope=plan id=review-phase-3 created=2026-11-12T20:49:49+00:00 phase=3 -->
### review-phase-3 · review · Phase 3 (quiet) review, range 42f8384b8..317d6b75e (phase 3)

Reviewer adfe80570b07de75c (opus) raised eleven findings, all in scope. p3-r1 was reproduced end to end (a git add -A commit plus fr push put fr paths on origin's feature branch under quiet). Ten were fixed by the fixer at 79e6272ab..fabd2a27f; p3-r2 is closed by resolving the misclassified implement finding as this plan's debt, fixed in the same range.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-12T20:49:49+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · Unconverted writers leak fr files into the product tree under quiet (phase 3)

init_cmd, isolation/scaffold, ops/gate, isolation/rename and ~40 root-joined artifact paths bypassed the resolver, so a git add -A commit and fr push carried fr paths to origin with exit 0.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-12T20:49:49+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · quiet-unconverted-writers was misclassified as out of scope (phase 3)

The unconverted writers are this plan's debt (R23), not a pre-existing defect.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-12T20:49:49+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · placement-quiet at ci overstated its evidence (phase 3)

The row's acceptance text claimed more than the scenario and unit levels proved.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-11-12T20:49:49+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · registry.iter_paths_of globs only repo_root (phase 3)

Migrate and validate never saw artifacts in the fr worktree.

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-11-12T20:49:49+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · A missing placement key skips the sticky check (phase 3)

A marker or state written before quiet existed bypassed the sticky-placement refusal.

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-11-12T20:49:49+00:00 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · Feature-id collision check compares live branches only (phase 3)

Two branches mapping to one feature id across clones were not caught.

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-11-12T20:49:49+00:00 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · fr run start lacks --no-fetch and names the wrong remedy (phase 3)

The unreachable-origin refusal named up's flag for a command that had none.

<!-- fr:journal kind=finding scope=plan id=p3-r8 created=2026-11-12T20:49:49+00:00 phase=3 state=open review_scope=in -->
### p3-r8 · finding [open] (reviewer: in scope) · The shared fr worktree has no lock (phase 3)

Concurrent rerouted commits or pushes from two workspaces could interleave.

<!-- fr:journal kind=finding scope=plan id=p3-r9 created=2026-11-12T20:49:49+00:00 phase=3 state=open review_scope=in -->
### p3-r9 · finding [open] (reviewer: in scope) · A pre-existing local fr branch is adopted without an ancestry check (phase 3)

An unrelated local fr branch would be used as the artifact branch.

<!-- fr:journal kind=finding scope=plan id=p3-r10 created=2026-11-12T20:49:49+00:00 phase=3 state=open review_scope=in -->
### p3-r10 · finding [open] (reviewer: in scope) · The apply --to refusal has side effects (phase 3)

It called space_for, creating the fr worktree before refusing.

<!-- fr:journal kind=finding scope=plan id=p3-r11 created=2026-11-12T20:49:49+00:00 phase=3 state=open review_scope=in -->
### p3-r11 · finding [open] (reviewer: in scope) · The scenario's deletion check is weak (phase 3)

Deleting origin's fr branch was not exercised as the spec's refusal case.

<!-- fr:journal kind=decision scope=plan id=quiet-placement-bound-vs-repo-config created=2026-11-12T20:49:49+00:00 phase=3 -->
### quiet-placement-bound-vs-repo-config · decision · Under quiet, only fr's artifacts move; repo configuration stays on the product branch uncommitted (phase 3)

Placement-bound means everything under docs/superpowers/** and docs/acceptance/** except the repo-config kinds (workflows, verifications, models.yaml, trackers.yaml, plan-config.yaml). Everything else fr writes (.devcontainer profiles, .claude/agents, .claude/rules, .gitignore, CI workflows, the README badge, .fr/, scripts/validate-plans.sh) is repo configuration; under quiet fr writes it but never commits it, because R23 forbids a chore(fr) commit on a product branch. Commands that can only act on the product branch (fr archive, fr debt archive-pr, fr ops gate, branch rename) refuse with exit 2 before writing.

<!-- fr:journal kind=decision scope=plan id=quiet-migration-own-feature-only created=2026-11-12T20:49:49+00:00 phase=3 -->
### quiet-migration-own-feature-only · decision · Under quiet, a migration rewrites and commits only the caller's own feature root (phase 3)

Raised by an automated security review of the p3-r4 fix. The root whose OWNER names the current branch is migrated and committed; other features' stale artifacts are reported and migrate when their own workspace next runs fr. validate artifacts still checks every root. Keeps R23's one-feature-per-commit and never rewrites another live workspace's files (8dca20601).

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-12T20:49:49+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: Unconverted writers leak fr files into the product tree under quiet (phase 3)

79e6272ab: writers route through artifact_root/paths.below, a tripwire forbids raw-root joins, QuietProductWriteError exits 2, placement-quiet.sh asserts origin carries no fr path or chore(fr) subject after git add -A and fr push.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-12T20:49:49+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: quiet-unconverted-writers was misclassified as out of scope (phase 3)

Reclassified as this plan's debt; quiet-unconverted-writers is resolved fixed by the p3-r1 work.

<!-- fr:journal kind=finding scope=plan id=quiet-unconverted-writers-resolved created=2026-11-12T20:49:49+00:00 phase=3 state=fixed resolves=quiet-unconverted-writers -->
### quiet-unconverted-writers-resolved · finding [fixed] · resolves quiet-unconverted-writers: Writers not yet on artifact_root are refused under quiet instead of writing to the fr branch (phase 3)

Fixed in 79e6272ab with p3-r1.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-12T20:49:49+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: placement-quiet at ci overstated its evidence (phase 3)

d74938af9: acceptance text made true, edge and migrate tests added as unit levels.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-11-12T20:49:49+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: registry.iter_paths_of globs only repo_root (phase 3)

63b174f6d: iter_paths_of walks every feature root; 8dca20601 restricts migration commits to the caller's own root.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-11-12T20:49:49+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: A missing placement key skips the sticky check (phase 3)

71cc6cdaf: a missing placement key counts as repo, so the sticky refusal fires.

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-11-12T20:49:49+00:00 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: Feature-id collision check compares live branches only (phase 3)

bc9042248: features/<id>/OWNER records the branch; space_for refuses a foreign owner.

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-11-12T20:49:49+00:00 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: fr run start lacks --no-fetch and names the wrong remedy (phase 3)

440a69b39: fr run start --no-fetch; the refusal names the remedy of the refusing command.

<!-- fr:journal kind=finding scope=plan id=p3-r8-resolved created=2026-11-12T20:49:49+00:00 phase=3 state=fixed resolves=p3-r8 -->
### p3-r8-resolved · finding [fixed] · resolves p3-r8: The shared fr worktree has no lock (phase 3)

cd57c673d: fr-worktree.lock held around rerouted commits and fr push, bounded wait, in-progress operations reported.

<!-- fr:journal kind=finding scope=plan id=p3-r9-resolved created=2026-11-12T20:49:49+00:00 phase=3 state=fixed resolves=p3-r9 -->
### p3-r9-resolved · finding [fixed] · resolves p3-r9: A pre-existing local fr branch is adopted without an ancestry check (phase 3)

52ee4b338 (+ quiet.py part in 440a69b39): unrelated local fr refused; init --quiet refuses while a local fr exists.

<!-- fr:journal kind=finding scope=plan id=p3-r10-resolved created=2026-11-12T20:49:49+00:00 phase=3 state=fixed resolves=p3-r10 -->
### p3-r10-resolved · finding [fixed] · resolves p3-r10: The apply --to refusal has side effects (phase 3)

1f8ae4539: apply --to decides from read_switch alone, before any worktree is created.

<!-- fr:journal kind=finding scope=plan id=p3-r11-resolved created=2026-11-12T20:49:49+00:00 phase=3 state=fixed resolves=p3-r11 -->
### p3-r11-resolved · finding [fixed] · resolves p3-r11: The scenario's deletion check is weak (phase 3)

79e6272ab: the scenario deletes origin's fr and asserts run start and run status refuse naming both placements.

<!-- fr:journal kind=decision scope=plan id=stealth-run-start-new-workspace-only created=2026-11-13T00:16:49+00:00 phase=4 -->
### stealth-run-start-new-workspace-only · decision · run start --stealth records stealth only for a workspace it enters; an existing one must already be stealth on that ref (phase 4)

R24 says run start may choose stealth, R23 says a workspace never changes placement. `fr run
start --stealth <ref>` therefore records stealth when it enters isolation itself (case 3 of
ensure_run_workspace) and, in an existing workspace, requires the state/marker to record
stealth on the same tracking ref, refusing otherwise with the up command to use.

<!-- fr:journal kind=decision scope=plan id=stealth-product-head-is-the-pushed-head created=2026-11-13T00:16:49+00:00 phase=4 -->
### stealth-product-head-is-the-pushed-head · decision · The state records the PUSHED product head (refs/remotes/origin/<branch>), in <run-id>.stealth.json (phase 4)

"Code is pushed before state, and the state records the product head it describes" is held
by recording only pushed code: every run write (start, advance, resolve) rewrites
`<runs dir>/<run-id>.stealth.json` with the target remote, branch and origin/<branch>'s sha,
committed with the step. It is not a cursor field (no kind changes) and not *.yaml, so no
locator reads it as a cursor. "Redo the last step's bookkeeping" on resume is re-recording
that head for the branch as fetched, committed and pushed like any state write; idempotent.

<!-- fr:journal kind=decision scope=plan id=stealth-privacy-at-the-push-seam created=2026-11-13T00:16:49+00:00 phase=4 -->
### stealth-privacy-at-the-push-seam · decision · The privacy verdict is required by commit_and_push itself, not only by its callers (phase 4)

Raised by the coordinator's security relay: `fr settings init --stealth` skipped the guard.
Beside the fix in init, `stealth.commit_and_push` calls `check_privacy(ref, target_remote)`
before committing (cached per process), so no future caller can push state to a tracking
repo more visible than its target. A local path counts as private; an unreadable visibility
refuses.

<!-- fr:journal kind=decision scope=plan id=stealth-reachability-once-per-process created=2026-11-13T00:16:49+00:00 phase=4 -->
### stealth-reachability-once-per-process · decision · space_for checks the tracking repo reachable once per process; up, run start and every push check it again (phase 4)

R24 fail-fast: `stealth_space` runs `git ls-remote` for the tracking ref the first time a
process resolves a stealth space, so any fr write refuses before writing when the tracking
repo is gone; `up`, `run start` and settings init check it uncached, and the CAS push is
itself the per-write check (a failure there is fatal, StealthPushError, exit 2, with the
tracking worktree reset to its pre-commit HEAD).

<!-- fr:journal kind=discovery scope=plan id=stealth-red-order created=2026-11-13T00:16:49+00:00 phase=4 -->
### stealth-red-order · discovery · Most of stealth.py was written before its tests; RED taken by disabling each task's code (phase 4)

fr/placement/stealth.py was drafted in one sitting ahead of tasks 3-5. RED was taken honestly
per task: T1 (5 of 9 failed before servable/more_visible/_repo_file), T3 (with the commit
seam's stealth branch disabled 4 of 8 failed; the 4 passing were fail-fast checks already
in up), T4 (the two privacy-relay tests failed with the guard removed), T5 (all 5 failed
with run_cmd/isolation_cmd/apply_cmd stashed). The implementation was restored byte for byte.

<!-- fr:journal kind=discovery scope=plan id=relative-root-worktree-path created=2026-11-13T00:16:49+00:00 phase=4 -->
### relative-root-worktree-path · discovery · quiet.worktree_path("." ) named ~/.cache/fr/worktrees/fr; fixed by resolving the root (phase 4)

`fr isolation up` from the cwd passes Path("."), whose common dir is the relative `.git`, so
the repo name was empty. Found by the resume test on a second host; quiet had the same latent
bug. Both quiet.worktree_path and stealth.worktree_path/target_dir now resolve first.

<!-- fr:journal kind=discovery scope=plan id=record-home-message-outside-checkout created=2026-11-13T00:16:49+00:00 phase=4 -->
### record-home-message-outside-checkout · discovery · resolve --record's "not in this run's records dir" refusal crashed (ValueError) when the run lives outside the checkout (phase 4)

`home.relative_to(repo_root)` raised under quiet and stealth; it now prints the path relative
when inside the checkout, absolute otherwise (`_shown_path`).

<!-- fr:journal kind=discovery scope=plan id=stealth-full-suite-caught-workspace-read created=2026-11-13T00:16:49+00:00 phase=4 -->
### stealth-full-suite-caught-workspace-read · discovery · The first full suite caught ensure_run_workspace reading state.placement on a stub without it (phase 4)

test_run_workspace's reuse test stubs the state with only `worktree`; the stealth check read
`placement` unconditionally. It now reads the recorded placement only for a stealth request
(91b550eee); the full suite was re-run after the fix.

<!-- fr:journal kind=finding scope=plan id=stealth-init-skipped-privacy created=2026-11-13T00:16:49+00:00 phase=4 state=open review_scope=in -->
### stealth-init-skipped-privacy · finding [open] (reviewer: in scope) · fr settings init --stealth pushed into the tracking repo without the privacy guard (phase 4)

Security relay from the coordinator: init_stealth ran parse_ref -> check_reachable ->
target_dir -> ensure_worktree -> commit_and_push and never check_privacy, so it could push a
target's settings and identity into a tracking repo more visible than the target (R24).

<!-- fr:journal kind=finding scope=plan id=stealth-init-skipped-privacy-resolved created=2026-11-13T00:16:49+00:00 phase=4 state=fixed resolves=stealth-init-skipped-privacy -->
### stealth-init-skipped-privacy-resolved · finding [fixed] · resolves stealth-init-skipped-privacy: fr settings init --stealth pushed into the tracking repo without the privacy guard (phase 4)

init_stealth calls check_privacy before cloning or pushing, and commit_and_push itself refuses
without a privacy verdict. Tests: test_init_stealth_refuses_a_public_tracking_repo_for_a_private_target
(exit 2, no worktree, tracking ref unmoved) and test_the_push_seam_itself_refuses_without_a_privacy_verdict;
both failed with the guard removed.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-11-13T00:16:49+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

new module fr/placement/stealth.py; the targets share one fetch_placement and one _tracking_entry, the CLI one _stealth_request; nothing duplicated to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t2 created=2026-11-13T00:16:49+00:00 phase=4 -->
### no-refactor-p4-t2 · discovery · no-refactor-because P4.T2 (phase 4)

one _stealth source in the loader beside _quiet, one data rule in RULES, render_init gained a placement instead of a second renderer

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t3 created=2026-11-13T00:16:49+00:00 phase=4 -->
### no-refactor-p4-t3 · discovery · no-refactor-because P4.T3 (phase 4)

the stealth commit is one branch of the existing commit seam (commit_and_push), reusing gitseam.push_ref_cas and the fr-worktree lock; no parallel path left to merge

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t4 created=2026-11-13T00:16:49+00:00 phase=4 -->
### no-refactor-p4-t4 · discovery · no-refactor-because P4.T4 (phase 4)

more_visible sits beside leak_risk; check_privacy is the one guard, called by enter, init --stealth and the push seam

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t5 created=2026-11-13T00:16:49+00:00 phase=4 -->
### no-refactor-p4-t5 · discovery · no-refactor-because P4.T5 (phase 4)

the product-head write is one _RunWrites hook; resume is prepare/finish around the existing up; the quiet-only refusals now share outside_repo

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t6 created=2026-11-13T00:16:49+00:00 phase=4 -->
### no-refactor-p4-t6 · discovery · no-refactor-because P4.T6 (phase 4)

skills, mirrors, a scenario, docs and the row move; no code to clean

<!-- fr:journal kind=review scope=plan id=review-phase-4 created=2026-11-13T02:30:09+00:00 phase=4 -->
### review-phase-4 · review · Phase 4 (stealth) review, range c730b11b7..b224b27cf (phase 4)

Reviewer a69ecb483d71aace6 (opus) returned "not ready" with nine in-scope findings, most reproduced in scratch repos (a CAS overwrite of another host's state, a refused commit that exited 0, fr agents delivered to the target origin). All nine were fixed at 9b012fd4d..66f4529f2, together with three automated security-review follow-ups (NUL-safe, case-folded fr-path check on fr push; forge writes refused at the client layer; visibility asked only of the remote URL's own host and backend).

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-11-13T02:30:09+00:00 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · Stealth push force-with-lease without ancestry check; ensure_worktree ignores a failed fast-forward (phase 4)

A diverged tracking clone force-overwrote another writer's state (reproduced).

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-11-13T02:30:09+00:00 phase=4 state=open review_scope=in -->
### p4-r2 · finding [open] (reviewer: in scope) · A commit refused in the tracking clone was a warning with exit 0 (phase 4)

The cursor moved locally while the tracking ref did not, against R24 (reproduced with fr run advance).

<!-- fr:journal kind=finding scope=plan id=p4-r3 created=2026-11-13T02:30:09+00:00 phase=4 state=open review_scope=in -->
### p4-r3 · finding [open] (reviewer: in scope) · fr init agents and scaffolds wrote fr files into the target under stealth (phase 4)

git add -A plus fr push delivered .claude/agents to the target origin (reproduced).

<!-- fr:journal kind=finding scope=plan id=p4-r4 created=2026-11-13T02:30:09+00:00 phase=4 state=open review_scope=in -->
### p4-r4 · finding [open] (reviewer: in scope) · Re-running fr isolation up on a stealth workspace demanded scripts/validate-plans.sh on the product branch (phase 4)

space_for saw the tracking repo's plans.

<!-- fr:journal kind=finding scope=plan id=p4-r5 created=2026-11-13T02:30:09+00:00 phase=4 state=open review_scope=in -->
### p4-r5 · finding [open] (reviewer: in scope) · fr apply --yes gated the forge against the tracking clone (phase 4)

forge.issues and labels read as on, so issues would reach the target forge.

<!-- fr:journal kind=finding scope=plan id=p4-r6 created=2026-11-13T02:30:09+00:00 phase=4 state=open review_scope=in -->
### p4-r6 · finding [open] (reviewer: in scope) · The uncommitted-edit veto ignored the tracking clone (phase 4)

The migration gate could commit a half-edited artifact there.

<!-- fr:journal kind=finding scope=plan id=p4-r7 created=2026-11-13T02:30:09+00:00 phase=4 state=open review_scope=in -->
### p4-r7 · finding [open] (reviewer: in scope) · Visibility could never be read for self-hosted or scp-style targets (phase 4)

_forge_visibility built https://host:path and picked GitHub.

<!-- fr:journal kind=finding scope=plan id=p4-r8 created=2026-11-13T02:30:09+00:00 phase=4 state=open review_scope=in -->
### p4-r8 · finding [open] (reviewer: in scope) · more_visible treated an unknown target visibility as public (phase 4)

Fail-open for a public tracking repo.

<!-- fr:journal kind=finding scope=plan id=p4-r9 created=2026-11-13T02:30:09+00:00 phase=4 state=open review_scope=in -->
### p4-r9 · finding [open] (reviewer: in scope) · Stealth refusals in fr acceptance init named placement quiet and R23 (phase 4)

Wrong placement in the message.

<!-- fr:journal kind=decision scope=plan id=stealth-gitea-unreadable created=2026-11-13T02:30:09+00:00 phase=4 -->
### stealth-gitea-unreadable · decision · A Gitea target or tracking repo is unreadable for the privacy guard, so stealth refuses it (phase 4)

The tea client cannot be pinned to the remote URL's host, so fr cannot be sure which forge answered the visibility question. R24's guard fails closed on unreadable visibility; an explicit Gitea path is follow-up work, not this plan's.

<!-- fr:journal kind=decision scope=plan id=stealth-forge-guard-at-client created=2026-11-13T02:30:09+00:00 phase=4 -->
### stealth-forge-guard-at-client · decision · Under stealth, forge writes are refused at the client layer, except the one minimal draft PR (phase 4)

fr/placement/forge_guard.py wraps every client from client_for and client_for_backend, so a new command cannot skip the R24 guard; commands keep their own earlier refusals for a better message. Stealth is decided from the checkout and the process cwd, so a triage or release forge write started inside a stealth workspace is refused too.

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-11-13T02:30:09+00:00 phase=4 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: Stealth push force-with-lease without ancestry check; ensure_worktree ignores a failed fast-forward (phase 4)

9b012fd4d: push requires ancestry (replays onto the seen tip); stealth.sync() under fr_worktree_lock fetches, fast-forwards, rebases unpushed commits or refuses.

<!-- fr:journal kind=finding scope=plan id=p4-r2-resolved created=2026-11-13T02:30:09+00:00 phase=4 state=fixed resolves=p4-r2 -->
### p4-r2-resolved · finding [fixed] · resolves p4-r2: A commit refused in the tracking clone was a warning with exit 0 (phase 4)

90e6b5ed8, 151f9ad56: any non-committed stealth outcome raises StealthPushError (exit 2) after restoring only this call's files; rollback is a soft reset, never reset --hard; other features' pending files are ignored; row note and explainers corrected.

<!-- fr:journal kind=finding scope=plan id=p4-r3-resolved created=2026-11-13T02:30:09+00:00 phase=4 state=fixed resolves=p4-r3 -->
### p4-r3-resolved · finding [fixed] · resolves p4-r3: fr init agents and scaffolds wrote fr files into the target under stealth (phase 4)

99f6c64e5, 2870a7b98: repo-config writers refuse under stealth before writing; fr push refuses commits carrying fr-owned paths, read with diff-tree -z and core.quotePath=false, case-folded; the scenario asserts the target origin holds no fr path.

<!-- fr:journal kind=finding scope=plan id=p4-r4-resolved created=2026-11-13T02:30:09+00:00 phase=4 state=fixed resolves=p4-r4 -->
### p4-r4-resolved · finding [fixed] · resolves p4-r4: Re-running fr isolation up on a stealth workspace demanded scripts/validate-plans.sh on the product branch (phase 4)

1d3926be1: the existing-worktree check counts only product-tree plans, for quiet and stealth.

<!-- fr:journal kind=finding scope=plan id=p4-r5-resolved created=2026-11-13T02:30:09+00:00 phase=4 state=fixed resolves=p4-r5 -->
### p4-r5-resolved · finding [fixed] · resolves p4-r5: fr apply --yes gated the forge against the tracking clone (phase 4)

2870a7b98: fr apply --yes refuses under stealth; forge policy read from the cwd workspace; forge_guard refuses every write but create_pr; tests show zero write calls.

<!-- fr:journal kind=finding scope=plan id=p4-r6-resolved created=2026-11-13T02:30:09+00:00 phase=4 state=fixed resolves=p4-r6 -->
### p4-r6-resolved · finding [fixed] · resolves p4-r6: The uncommitted-edit veto ignored the tracking clone (phase 4)

06276a412: the veto covers the tracking clone.

<!-- fr:journal kind=finding scope=plan id=p4-r7-resolved created=2026-11-13T02:30:09+00:00 phase=4 state=fixed resolves=p4-r7 -->
### p4-r7-resolved · finding [fixed] · resolves p4-r7: Visibility could never be read for self-hosted or scp-style targets (phase 4)

600e05500, ab698827d, 7fe6442f7: scp/ssh remotes parsed; the checkout's raw host must equal the URL's host; a SaaS host must be asked by its own backend; Gitea unreadable.

<!-- fr:journal kind=finding scope=plan id=p4-r8-resolved created=2026-11-13T02:30:09+00:00 phase=4 state=fixed resolves=p4-r8 -->
### p4-r8-resolved · finding [fixed] · resolves p4-r8: more_visible treated an unknown target visibility as public (phase 4)

99e7d92c2: unknown target visibility is private, unknown tracking visibility public.

<!-- fr:journal kind=finding scope=plan id=p4-r9-resolved created=2026-11-13T02:30:09+00:00 phase=4 state=fixed resolves=p4-r9 -->
### p4-r9-resolved · finding [fixed] · resolves p4-r9: Stealth refusals in fr acceptance init named placement quiet and R23 (phase 4)

6ffbbf8c2: the messages name placement stealth and R24.

<!-- fr:journal kind=decision scope=plan id=merged-heads-and-cache created=2026-11-13T04:40:53+00:00 phase=5 -->
### merged-heads-and-cache · decision · A feature's heads are its branch's live refs, else the head its last merged record verified, else stealth's recorded product heads (phase 5)

R17's clause needs "the code branch's head, recorded with the feature". The feature
path names its branch in OWNER; its heads are `refs/heads/<b>` and
`refs/remotes/origin/<b>` in the product repo, and every one must be reachable from
the default ref (unpushed work after a merge is not merged). With neither ref (the
branch was deleted after its merge), the head the last `merged.yaml` record carries,
else every `product_head` in the feature's `<run-id>.stealth.json` files. The record
is `- merged: <sha>` plus `head: <sha>`, appended; it is a cache hit only when its sha
is on the default ref's first-parent history, every head is its ancestor, and none
is an ancestor of the first-parent commit before it. Order is that commit's position
(binary search over the first-parent list), ties by feature id. A record never makes
a feature merged: even its head is re-verified on every read.

<!-- fr:journal kind=decision scope=plan id=archive-outside-repo-branch-only created=2026-11-13T04:40:53+00:00 phase=5 -->
### archive-outside-repo-branch-only · decision · Under quiet and stealth only `fr archive --branch` runs; plan-dir, --all and --sweep-only refuse naming it (phase 5)

R25: archive moves nothing outside `repo`. `fr archive --branch <b>` fetches like the
repo path, requires the branch to resolve, refuses an unmerged branch (exit 2,
nothing written), writes nothing when an agreeing record exists, else appends one
record and commits it on the placement's branch: quiet in the fr worktree under its
lock, then a plain `fr` push (`atomic_push(code=False)`; a refused push leaves the
commit for `fr push`, exit 2); stealth through `stealth.commit_and_push` (privacy
guard, CAS push, rollback). The move-based forms refuse before writing, naming
`--branch`. Close-out's plan sweep and `fr debt` read merged status through
`merged_features`: a plan of a merged feature with no agreeing record is archivable
with `fr archive --branch <b>`, and one with an agreeing record counts as archived.

<!-- fr:journal kind=decision scope=plan id=quiet-cross-feature-amendments created=2026-11-13T04:40:53+00:00 phase=5 -->
### quiet-cross-feature-amendments · decision · Under quiet and stealth a row another merged feature defines changes by amendment, validated against the cross-feature fold (phase 5)

The scenario needs feature b to amend feature a's row. The record writer
(`record/apply.py`) refused a feature with no fragment folder, treated no row as
merged (`default_ref_fold` is None outside repo) and validated the written fragments
alone, so the amendment named an unknown row. Outside repo it now proceeds when any
feature root has fragments (the folder is made by the first write), takes rows the
fold knows but this branch's fragments do not define as merged (so `set-status`
writes an amendment, R16), takes the repo identity from the fold, and validates with
`fold.fold_outside_with` (this branch's fragments replaced by the ones being written).

<!-- fr:journal kind=discovery scope=plan id=merge-fallout-vk-removal created=2026-11-13T04:40:53+00:00 phase=5 -->
### merge-fallout-vk-removal · discovery · Merging origin/main (#1424) left this branch on VK_REPO_ROOT and isolation's removed DEFAULT_BRANCH (phase 5)

Five placement tests failed before any phase 5 change: main renamed VK_REPO_ROOT to
FR_REPO_ROOT and made `fr isolation up --branch` required, removing DEFAULT_BRANCH,
which `_prepare_resume` still named (a NameError on `up --resume`), and the tests
then read the caller's cwd, a live workspace. Fixed in 9205ca8b3: FR_REPO_ROOT in
settings_cmd, validate-plans.sh (both copies) and 15 test modules; `--branch`
optional only with `--resume` (a usage error otherwise, as main's test pins); two
quiet_up tests now chdir into their sandbox. The first full suite then caught main's
new `fr/artifacts/plan_vk_version.py` spelling its archive locator as a literal (the
artifact-path tripwire); it is `repo_glob("plan-archived", ...)` now (28a534b17).

<!-- fr:journal kind=discovery scope=plan id=p5-red-order created=2026-11-13T04:40:53+00:00 phase=5 -->
### p5-red-order · discovery · merged.py was drafted before its tests; RED taken by holding the module out (phase 5)

fr/placement/merged.py was written ahead of tests/unit/test_placement_merged.py. RED
was taken with the module held aside (collection fails on the import) and, with it
restored, the five fold tests failed on the unchanged fold. Tasks 2 and 3 were RED
first (8 archive/sweep/debt tests, then the scenario on the amend refusal, the
cross-feature amend test, and the debt-dating test).

<!-- fr:journal kind=finding scope=plan id=p5-debt-stale-quiet-fr-history created=2026-11-13T04:40:53+00:00 phase=5 state=open review_scope=out -->
### p5-debt-stale-quiet-fr-history · finding [open] (reviewer: out of scope) · fr debt's staleness under quiet reads plan activity from the product history, which holds no fr file (phase 5)

For a quiet or stealth plan, `_last_commit(repo_root, ref, plans/<name>)` asks the
product's git history, where no plan lives (R23), so the only activity is the code
branch's (now named through OWNER, 3645eb29a). A plan whose bookkeeping moved on
`fr` while its code branch sat idle reads as stale. Reading the fr worktree's (or
tracking branch's) history for the feature path would fix it; it is debt's
staleness, not merged status, so outside this phase.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t1 created=2026-11-13T04:40:53+00:00 phase=5 -->
### no-refactor-p5-t1 · discovery · no-refactor-because P5.T1 (phase 5)

new module fr/placement/merged.py; the fold change split _fold into _fold (git tip) and _fold_from (shared), so repo and quiet/stealth run one fold body; nothing duplicated left

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t2 created=2026-11-13T04:40:53+00:00 phase=5 -->
### no-refactor-p5-t2 · discovery · no-refactor-because P5.T2 (phase 5)

the archive record reuses the commit seams as they are (commit_paths in the fr worktree under its lock, atomic_push for quiet, stealth.commit_and_push); the sweep's quiet branch is one function beside plan_sweep, and debt reads its new maps with the repo path as default

<!-- fr:journal kind=review scope=plan id=review-phase-5 created=2026-11-13T05:47:39+00:00 phase=5 -->
### review-phase-5 · review · Phase 5 (merged status) review, range 6bb2acb..f5efed268 (phase 5)

Reviewer ad1ee57ed98179b38 (opus) raised eight in-scope findings, four reproduced in scratch repos (a branch fresh from main reading merged, a squash merge never detected, a deleted branch un-merging, a forged record trusted). All eight were fixed at 11a227edb..47b96ff63; the full suite passed (15552 passed) after the last code commit.

<!-- fr:journal kind=finding scope=plan id=p5-r1 created=2026-11-13T05:47:39+00:00 phase=5 state=open review_scope=in -->
### p5-r1 · finding [open] (reviewer: in scope) · A feature branch fresh from the default ref read as merged (phase 5)

Its head was an ancestor of main before any work, so its rows entered every matrix and fr archive would record it merged (reproduced).

<!-- fr:journal kind=finding scope=plan id=p5-r2 created=2026-11-13T05:47:39+00:00 phase=5 state=open review_scope=in -->
### p5-r2 · finding [open] (reviewer: in scope) · Squash and rebase merges were never detected (phase 5)

Only ancestry was tested, so the merge styles this repo and many stealth targets use never read as merged (reproduced).

<!-- fr:journal kind=finding scope=plan id=p5-r3 created=2026-11-13T05:47:39+00:00 phase=5 state=open review_scope=in -->
### p5-r3 · finding [open] (reviewer: in scope) · Merged status depended on host-local refs and was not monotone (phase 5)

A branch deleted after merge read unmerged on another host, and a commit pushed after the merge un-merged it (reproduced).

<!-- fr:journal kind=finding scope=plan id=p5-r4 created=2026-11-13T05:47:39+00:00 phase=5 state=open review_scope=in -->
### p5-r4 · finding [open] (reviewer: in scope) · With the branch gone, a merged record's head was trusted (phase 5)

A stale or forged merged: record decided status alone, against R17's cache-is-never-the-truth (reproduced).

<!-- fr:journal kind=finding scope=plan id=p5-r5 created=2026-11-13T05:47:39+00:00 phase=5 state=open review_scope=in -->
### p5-r5 · finding [open] (reviewer: in scope) · Merged features' fragments were read live from the fr worktree (phase 5)

Later amendments applied at once and in-place edits of merged rows were accepted, so R16 went unenforced under quiet.

<!-- fr:journal kind=finding scope=plan id=p5-r6 created=2026-11-13T05:47:39+00:00 phase=5 state=open review_scope=in -->
### p5-r6 · finding [open] (reviewer: in scope) · Remote branch heads hard-coded origin (phase 5)

A repo whose default ref lives on another remote read no heads.

<!-- fr:journal kind=finding scope=plan id=p5-r7 created=2026-11-13T05:47:39+00:00 phase=5 state=open review_scope=in -->
### p5-r7 · finding [open] (reviewer: in scope) · A quiet archive whose push was refused later reported already recorded with exit 0 (phase 5)

The record stayed local and unpushed while the rerun claimed success.

<!-- fr:journal kind=finding scope=plan id=p5-r8 created=2026-11-13T05:47:39+00:00 phase=5 state=open review_scope=in -->
### p5-r8 · finding [open] (reviewer: in scope) · Debt staleness and close-out read plan history from the product branch (phase 5)

Under quiet and stealth the plan lives in fr or tracking history, so every plan read stale. Supersedes p5-debt-stale-quiet-fr-history.

<!-- fr:journal kind=decision scope=plan id=merged-base-file created=2026-11-13T05:47:39+00:00 phase=5 -->
### merged-base-file · decision · BASE is written beside OWNER by a feature root's first fr commit (phase 5)

Its value is the merge base of HEAD with the default ref, else HEAD, which can only undercount a feature's own commits. A root without BASE is merged only through the forge, with a notice.

<!-- fr:journal kind=decision scope=plan id=merged-heads-file created=2026-11-13T05:47:39+00:00 phase=5 -->
### merged-heads-file · decision · Under quiet, fr push appends the pushed head to the feature root's HEADS file in the same atomic push (phase 5)

HEADS is append-only and written only for claimed roots. Stealth keeps product_head in stealth.json as its recorded head and gets no HEADS file. Archive adds the heads it verified, including a forge PR's head.

<!-- fr:journal kind=decision scope=plan id=merged-status-rule created=2026-11-13T05:47:39+00:00 phase=5 -->
### merged-status-rule · decision · Merged by git when any recorded or live head is on the default ref and past BASE; else the forge's merged PR; else unmerged (phase 5)

The position is the earliest introducing first-parent commit, and status is monotone. A forge PR counts only when its merge commit is on the default ref's first-parent line and not inside BASE.

<!-- fr:journal kind=decision scope=plan id=merged-forge-read created=2026-11-13T05:47:39+00:00 phase=5 -->
### merged-forge-read · decision · The merged-PR read is a forge read, reached only from fr archive --branch and fr acceptance status (phase 5)

It is allowed under stealth (a read). The fold, close-out and debt never read the forge; a squash merge reaches the fold through archive's pr: record, corroborated by owned HEADS. Fork PRs and PRs with another head name are ignored; a local-path origin has no forge.

<!-- fr:journal kind=decision scope=plan id=merged-no-git-fallback created=2026-11-13T05:47:39+00:00 phase=5 -->
### merged-no-git-fallback · decision · No patch-id or tree-equivalence fallback for squash detection (phase 5)

Matching content could mark an unmerged feature merged, so without the forge a squash merge reads unmerged and fr says the forge is needed and why it was not read.

<!-- fr:journal kind=decision scope=plan id=merged-freeze-by-time created=2026-11-13T05:47:39+00:00 phase=5 -->
### merged-freeze-by-time · decision · A merged feature's fragments are frozen at its last pushed fr commit at or before the merge commit's committer time (phase 5)

Computed on every read from origin/fr or the tracking upstream, not stored in the record. Clock skew between hosts is a known limit.

<!-- fr:journal kind=finding scope=plan id=p5-r1-resolved created=2026-11-13T05:47:39+00:00 phase=5 state=fixed resolves=p5-r1 -->
### p5-r1-resolved · finding [fixed] · resolves p5-r1: A feature branch fresh from the default ref read as merged (phase 5)

b8f366e6e: BASE recorded beside OWNER; merged only with a head past BASE on the default ref.

<!-- fr:journal kind=finding scope=plan id=p5-r2-resolved created=2026-11-13T05:47:39+00:00 phase=5 state=fixed resolves=p5-r2 -->
### p5-r2-resolved · finding [fixed] · resolves p5-r2: Squash and rebase merges were never detected (phase 5)

b8f366e6e: forge merged-PR read (MergedPrs protocol, ClientMergedPrs over GhClient), merge commit checked on the first-parent line; plain message when unmerged.

<!-- fr:journal kind=finding scope=plan id=p5-r3-resolved created=2026-11-13T05:47:39+00:00 phase=5 state=fixed resolves=p5-r3 -->
### p5-r3-resolved · finding [fixed] · resolves p5-r3: Merged status depended on host-local refs and was not monotone (phase 5)

b8f366e6e: HEADS recorded by fr push; status reads live refs, HEADS and stealth product_head, monotone; archive works for a deleted branch.

<!-- fr:journal kind=finding scope=plan id=p5-r4-resolved created=2026-11-13T05:47:39+00:00 phase=5 state=fixed resolves=p5-r4 -->
### p5-r4-resolved · finding [fixed] · resolves p5-r4: With the branch gone, a merged record's head was trusted (phase 5)

b8f366e6e: a merged: record supplies no head; a forge-merge record counts offline only when an owned head and the first-parent line corroborate it.

<!-- fr:journal kind=finding scope=plan id=p5-r5-resolved created=2026-11-13T05:47:39+00:00 phase=5 state=fixed resolves=p5-r5 -->
### p5-r5-resolved · finding [fixed] · resolves p5-r5: Merged features' fragments were read live from the fr worktree (phase 5)

b8f366e6e: merged fragments read from the pushed fr commit frozen at the merge; outside_merged_row_edits refuses in-place edits under quiet and stealth.

<!-- fr:journal kind=finding scope=plan id=p5-r6-resolved created=2026-11-13T05:47:39+00:00 phase=5 state=fixed resolves=p5-r6 -->
### p5-r6-resolved · finding [fixed] · resolves p5-r6: Remote branch heads hard-coded origin (phase 5)

b8f366e6e: heads read from remote_of(default ref).

<!-- fr:journal kind=finding scope=plan id=p5-r7-resolved created=2026-11-13T05:47:39+00:00 phase=5 state=fixed resolves=p5-r7 -->
### p5-r7-resolved · finding [fixed] · resolves p5-r7: A quiet archive whose push was refused later reported already recorded with exit 0 (phase 5)

b8f366e6e: a cache hit with an unpushed record pushes it under the lock, or exits 2 naming it.

<!-- fr:journal kind=finding scope=plan id=p5-r8-resolved created=2026-11-13T05:47:39+00:00 phase=5 state=fixed resolves=p5-r8 -->
### p5-r8-resolved · finding [fixed] · resolves p5-r8: Debt staleness and close-out read plan history from the product branch (phase 5)

b8f366e6e: close-out records each plan's resolved directory; debt dates quiet and stealth plans from fr history.

<!-- fr:journal kind=finding scope=plan id=p5-debt-stale-quiet-fr-history-resolved created=2026-11-13T05:47:39+00:00 phase=5 state=fixed resolves=p5-debt-stale-quiet-fr-history -->
### p5-debt-stale-quiet-fr-history-resolved · finding [fixed] · resolves p5-debt-stale-quiet-fr-history: fr debt's staleness under quiet reads plan activity from the product history, which holds no fr file (phase 5)

Superseded by p5-r8, fixed at b8f366e6e.

<!-- fr:journal kind=decision scope=plan id=p6-direct-checks-first created=2026-11-13T09:31:58+00:00 phase=6 -->
### p6-direct-checks-first · decision · _fr_is_enabled and frEnabled run the direct checks before asking fr, so fr can only add a yes (phase 6) (phase 6)

Order is profile, plans dir, then the quiet switch (origin remote plus refs/remotes/origin/fr:settings.yaml says placement: quiet) and the marker's placement (quiet or stealth), and only then `fr settings paths --shell|--json` (placement quiet/stealth, or an existing FR_PLANS_DIR). A missing, failing or garbled fr therefore never turns a direct yes into a no. The output is never eval'd: two keys are read by name.

<!-- fr:journal kind=decision scope=plan id=p6-fr-resolution-trusts-absolute-path-entries created=2026-11-13T09:31:58+00:00 phase=6 -->
### p6-fr-resolution-trusts-absolute-path-entries · decision · The plugin resolves fr from absolute PATH entries only and spawns the file it checked (security relay, phase 6) (phase 6)

src/fr.ts skips empty or relative PATH entries (checked against the plugin's cwd but run from the repo toplevel, so a planted fr in the edited repo could run in the gate's decision path), returns the realpath of the checked file, and marker.ts spawns exactly that. No trusted fr means the direct fallback checks, never a weaker gate. The plugin does not consume FR_HARNESS_FR (pin.ts only exports it), so there was no pinned path to require absolute. Bun test: a relative-entry fr is never chosen or spawned.

<!-- fr:journal kind=decision scope=plan id=p6-nag-asks-fr-only-for-placement-repos created=2026-11-13T09:31:58+00:00 phase=6 -->
### p6-nag-asks-fr-only-for-placement-repos · decision · The acceptance nag asks fr for FR_ACCEPTANCE_DIR only when the placement is quiet or stealth (phase 6) (phase 6)

The cheap early exit must spawn no fr for a plain repo (test_p2_r6). So the nag detects quiet/stealth directly (the library's _fr_placement_enabled, nag.ts placementEnabled) and only then asks fr settings paths for the acceptance dir; otherwise the checkout's docs/acceptance, marked fr-paths-fallback.

<!-- fr:journal kind=discovery scope=plan id=p6-bun-bare-spawn-uses-startup-path created=2026-11-13T09:31:58+00:00 phase=6 -->
### p6-bun-bare-spawn-uses-startup-path · discovery · A bare-name spawn from bun answered from the startup PATH, so tests could not substitute fr (phase 6) (phase 6)

Stub fr on a modified process.env.PATH was ignored; the real fr ran. resolveFr resolves from the PATH at call time to an absolute file, which is also what the security fix needs.

<!-- fr:journal kind=discovery scope=plan id=p6-red-by-stash-and-order created=2026-11-13T09:31:58+00:00 phase=6 -->
### p6-red-by-stash-and-order · discovery · RED for T1 taken by stashing the library change (7 failed); T2/T3 REDs were taken against missing exports and an unmarked scan (phase 6) (phase 6)

T1: 7 of the new tests failed without the library change. T2: tests import exports (frPaths, placementEnabled, resetFrPaths, warnIfFrUnresolved) that did not exist, so they failed by construction before the code existed. The scenario's RED was not separately captured: a `git stash push -- <committed path>` stashed nothing and its pop applied an unrelated older stash, which I removed (only an untracked debug journal file landed; the stash entry is untouched).

<!-- fr:journal kind=finding scope=plan id=p6-stray-stash-entry created=2026-11-13T09:31:58+00:00 phase=6 state=open review_scope=out -->
### p6-stray-stash-entry · finding [open] (reviewer: out of scope) · stash@{0} on this repo belongs to another branch (fix/opencode-edit-gate-closed) and is untouched (phase 6) (phase 6)

Left as found; it holds version bumps and an unrelated OpenCode gate WIP. Not part of this feature.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t1 created=2026-11-13T09:31:58+00:00 phase=6 -->
### no-refactor-p6-t1 · discovery · no-refactor-because P6.T1 (phase 6)

the private fr_enabled copy in fr-worktree-create.sh was replaced by the library's one _fr_is_enabled; nothing else duplicated

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t2 created=2026-11-13T09:31:58+00:00 phase=6 -->
### no-refactor-p6-t2 · discovery · no-refactor-because P6.T2 (phase 6)

guard.ts's frEnabled became a re-export of marker.ts's, so there is one definition; nothing left to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t3 created=2026-11-13T09:31:58+00:00 phase=6 -->
### no-refactor-p6-t3 · discovery · no-refactor-because P6.T3 (phase 6)

tripwire helpers are shared by the shell and TypeScript scans; the scenario and parity text need no cleanup

<!-- fr:journal kind=decision scope=plan id=p6-plans-test-always created=2026-11-13T10:06:11+00:00 phase=6 decided_by=agent -->
### p6-plans-test-always · decision · The plans-dir test runs whether or not fr resolves (phase 6)

Spec §3.E says the OpenCode plugin falls back to the plans test only when `fr` is absent. Both engines (bash `_fr_is_enabled`, TS `frEnabled`) run it unconditionally, before asking `fr`. Kept deliberately (review p6-r7): the plans test can only ADD an fr-enabled answer, so running it always is the fail-closed reading. Running it only when `fr` is absent would let a failing, slow, garbled or lying `fr` turn a repo that has a plans dir in its checkout into 'not fr-enabled' and open the edit gate. The spec is not edited.

<!-- fr:journal kind=review scope=plan id=review-phase-6 created=2026-11-13T10:39:18+00:00 phase=6 -->
### review-phase-6 · review · Phase 6 (hooks, OpenCode plugin, Hermes) review, range 6a400f6..ae7bf18de (phase 6)

Reviewer ae531c0ff80f9ed22 (opus) returned not ready with nine in-scope findings, four reproduced (a repo-planted fr run by the bash edit hook, a non-canonical quiet switch failing open without fr, a 9x slower plain-repo decision, a hook creating the fr branch and worktree). All nine were fixed at 53d0569a6..77435bb1c; the full suite (15817 passed) and bun test (285 pass) ran after the last code commit. Running the new scenario from the workspace mutated it (HEAD switched to main, a seed commit on local main, a push to origin started); the reviewer killed the push before anything reached the remote and restored every ref, verified by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p6-r1 created=2026-11-13T10:39:18+00:00 phase=6 state=open review_scope=in -->
### p6-r1 · finding [open] (reviewer: in scope) · The bash library spawned fr settings paths, untimed, on every decision in every plain repo (phase 6)

Measured about 70 ms to 610 ms per edit or terminal decision.

<!-- fr:journal kind=finding scope=plan id=p6-r2 created=2026-11-13T10:39:18+00:00 phase=6 state=open review_scope=in -->
### p6-r2 · finding [open] (reviewer: in scope) · The bash fr lookup honoured relative PATH entries; a repo-planted bin/fr ran in the edit hook (phase 6)

Reproduced; a new code-execution path the TypeScript side already refused.

<!-- fr:journal kind=finding scope=plan id=p6-r3 created=2026-11-13T10:39:18+00:00 phase=6 state=open review_scope=in -->
### p6-r3 · finding [open] (reviewer: in scope) · A non-canonical spelling of the quiet switch was not fr-enabled when fr was absent or refused (phase 6)

Quoted, commented, flow or indented placement: quiet let a base-clone edit through (reproduced).

<!-- fr:journal kind=finding scope=plan id=p6-r4 created=2026-11-13T10:39:18+00:00 phase=6 state=open review_scope=in -->
### p6-r4 · finding [open] (reviewer: in scope) · Hooks called fr settings paths, which under quiet creates the fr branch and worktree (phase 6)

The session-start nag did it for every quiet repo (reproduced).

<!-- fr:journal kind=finding scope=plan id=p6-r5 created=2026-11-13T10:39:18+00:00 phase=6 state=open review_scope=in -->
### p6-r5 · finding [open] (reviewer: in scope) · placement-fr-enabled.sh mutated whatever repo it ran in (phase 6)

Run from the workspace it committed onto local main and started a push to origin.

<!-- fr:journal kind=finding scope=plan id=p6-r6 created=2026-11-13T10:39:18+00:00 phase=6 state=open review_scope=in -->
### p6-r6 · finding [open] (reviewer: in scope) · The tripwire's fr-paths-fallback exemption was self-asserting and unpinned (phase 6)

Any new hard-coded path passed by carrying the marker; _ts_code stripped // inside strings.

<!-- fr:journal kind=finding scope=plan id=p6-r7 created=2026-11-13T10:39:18+00:00 phase=6 state=open review_scope=in -->
### p6-r7 · finding [open] (reviewer: in scope) · The plans test runs always, not only when fr is absent (spec 3.E) (phase 6)

Safer than the wording; record the deviation.

<!-- fr:journal kind=finding scope=plan id=p6-r8 created=2026-11-13T10:39:18+00:00 phase=6 state=open review_scope=in -->
### p6-r8 · finding [open] (reviewer: in scope) · The nag's no-process-spawn contract became false (phase 6)

placementEnabled spawned git twice before the early exit, in both engines.

<!-- fr:journal kind=finding scope=plan id=p6-r9 created=2026-11-13T10:39:18+00:00 phase=6 state=open review_scope=in -->
### p6-r9 · finding [open] (reviewer: in scope) · The plugin's frPaths inherited FR_REPO_ROOT (phase 6)

fr could answer for another repo than the toplevel judged.

<!-- fr:journal kind=finding scope=plan id=p6-relative-path-git-and-bare-fr created=2026-11-13T10:39:18+00:00 phase=6 state=open review_scope=out -->
### p6-relative-path-git-and-bare-fr · finding [open] (reviewer: out of scope) · The git lookup and two bare fr spawns still trust relative PATH entries (phase 6)

fr_git_resolve, git.ts onPath, fr-worktree-create.sh and pin.ts predate this branch; tracked by derio-net/super-fr#1429.

<!-- fr:journal kind=decision scope=plan id=p6-r3-canonical-word created=2026-11-13T10:39:18+00:00 phase=6 -->
### p6-r3-canonical-word · decision · A valid fr-branch switch is one column-0 line placement: <word>; fr refuses any other spelling (phase 6)

The hooks read placement: repo, or no placement line, as repo and everything else, stealth included, as fr-enabled, so fr and the hooks agree on what a switch is and the hooks fail closed on the rest.

<!-- fr:journal kind=decision scope=plan id=p6-r3-text-scan created=2026-11-13T10:39:18+00:00 phase=6 -->
### p6-r3-text-scan · decision · Neither hook engine parses YAML; a live line naming placement counts as naming the key (phase 6)

Such a line inside another value gives a harmless false enabled, never a false not-enabled.

<!-- fr:journal kind=decision scope=plan id=p6-r1-git-kept created=2026-11-13T10:39:18+00:00 phase=6 -->
### p6-r1-git-kept · decision · The filesystem ref check only gates the fr spawn and the nag; the edit gate's switch read still uses git (phase 6)

A wrong filesystem answer (a GIT_DIR override, say) can therefore never make a repo not enabled.

<!-- fr:journal kind=decision scope=plan id=p6-r2-pin-identity created=2026-11-13T10:39:18+00:00 phase=6 -->
### p6-r2-pin-identity · decision · FR_HARNESS_FR is used as the fr to run only when it is an absolute path to an executable file (phase 6)

It normally holds an identity string; otherwise absolute PATH entries decide.

<!-- fr:journal kind=decision scope=plan id=p6-r4-no-create created=2026-11-13T10:39:18+00:00 phase=6 -->
### p6-r4-no-create · decision · fr settings paths --no-create computes paths without creating anything, and every hook uses it (phase 6)

Under stealth it also skips the reachability check and sync and does not refuse a missing tracking worktree. validate-plans.sh, a plan validator rather than a hook, keeps the creating form.

<!-- fr:journal kind=decision scope=plan id=p6-r5-fresh-fixture created=2026-11-13T10:39:18+00:00 phase=6 -->
### p6-r5-fresh-fixture · decision · Placement scenarios refuse unless run at the toplevel of a repo with no commits and no remote (phase 6)

That is how test_scenarios.py and fr verification walk hand a scenario its directory.

<!-- fr:journal kind=finding scope=plan id=p6-r1-resolved created=2026-11-13T10:39:18+00:00 phase=6 state=fixed resolves=p6-r1 -->
### p6-r1-resolved · finding [fixed] · resolves p6-r1: The bash library spawned fr settings paths, untimed, on every decision in every plain repo (phase 6)

9c76f07d3, 141a2545d: enabled from direct checks only; fr asked only when an origin/fr ref is on the filesystem, bounded by FR_PATHS_TIMEOUT; a plain repo spawns no fr (tested).

<!-- fr:journal kind=finding scope=plan id=p6-r2-resolved created=2026-11-13T10:39:18+00:00 phase=6 state=fixed resolves=p6-r2 -->
### p6-r2-resolved · finding [fixed] · resolves p6-r2: The bash fr lookup honoured relative PATH entries; a repo-planted bin/fr ran in the edit hook (phase 6)

9c76f07d3, 141a2545d: fr resolved from an absolute FR_HARNESS_FR path or absolute PATH entries only, exact path spawned, in the decision library and both nags; planted relative-entry fr ignored (tested in both engines).

<!-- fr:journal kind=finding scope=plan id=p6-r3-resolved created=2026-11-13T10:39:18+00:00 phase=6 state=fixed resolves=p6-r3 -->
### p6-r3-resolved · finding [fixed] · resolves p6-r3: A non-canonical spelling of the quiet switch was not fr-enabled when fr was absent or refused (phase 6)

53d0569a6 (fr refuses non-canonical switch spellings), 9c76f07d3, 141a2545d (hooks treat anything but placement: repo as enabled); every spelling tested with fr absent.

<!-- fr:journal kind=finding scope=plan id=p6-r4-resolved created=2026-11-13T10:39:18+00:00 phase=6 state=fixed resolves=p6-r4 -->
### p6-r4-resolved · finding [fixed] · resolves p6-r4: Hooks called fr settings paths, which under quiet creates the fr branch and worktree (phase 6)

53d0569a6, 9c76f07d3, 141a2545d: fr settings paths --no-create, used by every hook; no branch or worktree created (tested).

<!-- fr:journal kind=finding scope=plan id=p6-r5-resolved created=2026-11-13T10:39:18+00:00 phase=6 state=fixed resolves=p6-r5 -->
### p6-r5-resolved · finding [fixed] · resolves p6-r5: placement-fr-enabled.sh mutated whatever repo it ran in (phase 6)

2b4f7e481: scenario_require_fresh_repo guards all five placement scenarios (tested).

<!-- fr:journal kind=finding scope=plan id=p6-r6-resolved created=2026-11-13T10:39:18+00:00 phase=6 state=fixed resolves=p6-r6 -->
### p6-r6-resolved · finding [fixed] · resolves p6-r6: The tripwire's fr-paths-fallback exemption was self-asserting and unpinned (phase 6)

71285b8f6: exempt lines pinned in FALLBACK_LINES; string-aware _ts_code.

<!-- fr:journal kind=finding scope=plan id=p6-r7-resolved created=2026-11-13T10:39:18+00:00 phase=6 state=fixed resolves=p6-r7 -->
### p6-r7-resolved · finding [fixed] · resolves p6-r7: The plans test runs always, not only when fr is absent (spec 3.E) (phase 6)

2b05e1e92: decision p6-plans-test-always records the safer deviation; code unchanged, spec not edited.

<!-- fr:journal kind=finding scope=plan id=p6-r8-resolved created=2026-11-13T10:39:18+00:00 phase=6 state=fixed resolves=p6-r8 -->
### p6-r8-resolved · finding [fixed] · resolves p6-r8: The nag's no-process-spawn contract became false (phase 6)

9c76f07d3, 141a2545d: both nags look only when a marker or an origin/fr ref is on the filesystem; comments corrected; tested.

<!-- fr:journal kind=finding scope=plan id=p6-r9-resolved created=2026-11-13T10:39:18+00:00 phase=6 state=fixed resolves=p6-r9 -->
### p6-r9-resolved · finding [fixed] · resolves p6-r9: The plugin's frPaths inherited FR_REPO_ROOT (phase 6)

141a2545d: frPaths spawns with FR_REPO_ROOT set to the toplevel; tested.

<!-- fr:journal kind=finding scope=plan id=p6-relative-path-git-and-bare-fr-resolved created=2026-11-13T10:39:18+00:00 phase=6 state=open resolves=p6-relative-path-git-and-bare-fr out_of_scope=true -->
### p6-relative-path-git-and-bare-fr-resolved · finding [out-of-scope] · resolves p6-relative-path-git-and-bare-fr: The git lookup and two bare fr spawns still trust relative PATH entries (phase 6)

Predates this branch; tracked by derio-net/super-fr#1429.

<!-- fr:journal kind=finding scope=plan id=p6-stray-stash-entry-resolved created=2026-11-13T10:39:18+00:00 phase=6 state=fixed resolves=p6-stray-stash-entry -->
### p6-stray-stash-entry-resolved · finding [fixed] · resolves p6-stray-stash-entry: stash@{0} on this repo belongs to another branch (fix/opencode-edit-gate-closed) and is untouched (phase 6) (phase 6)

Verified by the orchestrator: the worktree is clean, the unrelated stash entry is intact, and the one stray untracked file was removed.

<!-- fr:journal kind=decision scope=plan id=p7-move-groups created=2026-11-13T11:48:29+00:00 phase=7 -->
### p7-move-groups · decision · A move out of repo groups artifacts into features by run branch, else by spec slug (moved/<key>) (phase 7)

Repo artifacts carry no feature. A run's cursor, records and usage go to the run's own
branch (feature id = its slug); a spec, its plans (via _meta.yaml spec:), journals and
fragment go to `moved/<spec-slug>`; a debug journal to `moved/debug-<slug>`; anything
else to `moved/repo`. Each group's head is the newest first-parent commit of the default
ref touching its files, its BASE that commit's first parent; HEADS and a `merged:` record
name the head. Verify catches any case the grouping cannot reproduce.

<!-- fr:journal kind=decision scope=plan id=p7-move-backdated-fr-commits created=2026-11-13T11:48:29+00:00 phase=7 -->
### p7-move-backdated-fr-commits · decision · Each copied feature's fr commit carries its head's committer date (phase 7)

merged.frozen_commit reads a merged feature's fragments from the last pushed fr commit
at or before its merge commit's time. A copy made now would be after every merge, so no
fragment would count as merged. Each feature is therefore one commit (R23: one feature
path per commit) dated at its head, built with plumbing in a private index (no checkout
touched), pushed plainly. Phase 5's freeze rule is unchanged.

<!-- fr:journal kind=decision scope=plan id=p7-move-copy-pushes-before-switch created=2026-11-13T11:48:29+00:00 phase=7 -->
### p7-move-copy-pushes-before-switch · decision · Copy pushes the fr branch without the switch; verify reads it as a placement; switch adds settings.yaml (phase 7)

The quiet fold reads what was pushed (origin/fr), so copy pushes `fr` with no
settings.yaml (no switch, the repo stays repo) and verify folds that space explicitly
(fold_of_space). Switch is the one commit adding `placement: quiet`. Leaving quiet
writes `placement: repo` by a new commit. Into repo the copy is a pushed branch
(chore/fr-placement-move-to-repo) that lands by PR; the switch pauses (exit 0, "paused")
until its files are on the default ref. Out of quiet only merged features are copied,
at their frozen commit; unmerged ones are live branches' and move with migrate-branch.

<!-- fr:journal kind=decision scope=plan id=p7-remove-pushes-a-branch created=2026-11-13T11:48:29+00:00 phase=7 -->
### p7-remove-pushes-a-branch · decision · Remove pushes the removal branch (never the default branch) and prints fr pr create (phase 7)

Out of repo, remove builds chore/fr-placement-move-to-<to> off the default ref with the
copied files deleted, pushes that branch plainly (a PR needs it on the remote), writes
the PR body under the git common dir and prints `git switch <branch> && fr pr create`.
No PR is opened and the default branch is never pushed.

<!-- fr:journal kind=decision scope=plan id=p7-stealth-whole-repo-one-way created=2026-11-13T11:48:29+00:00 phase=7 -->
### p7-stealth-whole-repo-one-way · decision · A whole-repo move to stealth is one-way; a stealth run comes back with --run (phase 7)

Stealth is chosen per run (R24), so after a whole move to stealth no repo-side state
says "stealth". The move puts every feature in the tracking repo (privacy guard and CAS
push through commit_and_push), its switch step only turns quiet off when the source was
quiet, and it prints `fr isolation up --stealth`. `--run <id>`, in a stealth workspace,
moves that run to the repo's current placement (repo or quiet); its verify is files and
validation (an unmerged run has no fold of its own to compare).

<!-- fr:journal kind=decision scope=plan id=p7-drift-detection created=2026-11-13T11:48:29+00:00 phase=7 -->
### p7-drift-detection · decision · The gate checks marker-vs-switch drift only (filesystem); push, deliver and validate also check the branch tree (phase 7)

marker_drift reads the marker and the switch ref from the filesystem (no process
without both). The gate asks it before every non-exempt command, ignoring
FR_SKIP_MIGRATION and CI (it migrates nothing), and lets `fr placement` through (it is
the remedy; for a drifted tree the rest of the gate is skipped). branch_drift (git:
placement-bound paths changed since the merge base, under quiet or stealth) is added by
fr push, deliver (_deliver_placement_gate) and the validate CLI, which is how CI sees it.
The validate check sits in commands/validate_cmd.py, not artifacts/validate.py, so the
move's own validation over exported trees is not affected. sticky_refusal now names
migrate-branch.

<!-- fr:journal kind=decision scope=plan id=p7-security-feature-id created=2026-11-13T11:48:29+00:00 phase=7 -->
### p7-security-feature-id · decision · One checked feature id (paths.checked_feature_id) and one inside() check for every move write and unlink (security finding) (phase 7)

A run cursor's branch is repo content. paths.unsafe_branch holds check-ref-format's
rules without a process, and checked_feature_id refuses an id that is not one
[A-Za-z0-9._-] segment or is all dots. quiet.check_feature_id (so quiet, stealth and
merged spaces), archive --branch, migrate-branch and the move use it; the move also runs
`git check-ref-format --branch` on each synthesised owner. move.inside() refuses any
write or unlink leaving its feature root, and the stealth stale pass is limited to that
root. Tests: crafted `..`/`../../escape` branches refused with exit 2 naming the branch,
nothing written.

<!-- fr:journal kind=decision scope=plan id=p7-security-no-symlinks created=2026-11-13T11:48:29+00:00 phase=7 -->
### p7-security-no-symlinks · decision · Moves and migrate-branch read sources from git and never follow a symlink (security finding) (phase 7)

Sources are read with ls-tree/cat-file, never the working tree; a 120000 (symlink) or
160000 (gitlink) entry among the copied paths refuses, naming it. Every write and unlink
goes through move.inside(), which also refuses when any component from the root down is
a symlink (lstat). Tests: a symlinked fragment pointing outside the repo is refused and
its contents reach no destination; a symlinked directory on the target side is refused
and nothing is written through it.

<!-- fr:journal kind=discovery scope=plan id=p7-scenario-first-run-flake created=2026-11-13T11:48:29+00:00 phase=7 -->
### p7-scenario-first-run-flake · discovery · One early scenario run reported no state file after the interruption; four later runs passed (phase 7)

The first passing build of the scenario followed a run that failed "no state file after
the interruption" (exit 2 from the move). Not reproduced in four consecutive runs; the
failure message now prints the move's output if it recurs.

<!-- fr:journal kind=finding scope=plan id=p7-quiet-to-stealth-live-branches created=2026-11-13T11:48:29+00:00 phase=7 state=open review_scope=out -->
### p7-quiet-to-stealth-live-branches · finding [open] (reviewer: out of scope) · After a quiet -> stealth whole move, live quiet workspaces migrate to repo, not stealth (phase 7)

migrate-branch follows the switch; once quiet is off the switch says repo, so a live
quiet workspace's branch is pulled back into the repo layout rather than into the
tracking repo. Moving a live run into stealth needs a per-run stealth entry that R24
leaves to `fr isolation up --stealth`; not addressed here.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p7-t1 created=2026-11-13T11:48:29+00:00 phase=7 -->
### no-refactor-p7-t1 · discovery · no-refactor-because P7.T1 (phase 7)

new module fr/placement/move.py; the one fold change is a space parameter on _outside_fold (fold_of_space), so the move's destination fold runs the same body as every quiet/stealth reader

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p7-t2 created=2026-11-13T11:48:29+00:00 phase=7 -->
### no-refactor-p7-t2 · discovery · no-refactor-because P7.T2 (phase 7)

new module fr/placement/drift.py; the gate, fr push, deliver and validate each call its one refuse(), and migrate-branch reuses commit_paths, _push_placement and atomic_push rather than a second push path

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p7-t3 created=2026-11-13T11:48:29+00:00 phase=7 -->
### no-refactor-p7-t3 · discovery · no-refactor-because P7.T3 (phase 7)

scenario, row amendment and docs only; nothing to fold

<!-- fr:journal kind=decision scope=plan id=p7-r3-return-copy-structural created=2026-11-13T12:23:51+00:00 phase=7 -->
### p7-r3-return-copy-structural · decision · The copy back into repo is recognised structurally, option (b) (phase 7)

Under quiet, `branch_drift` accepts a branch whose added fr files are a subset of, and whose tree holds exactly, the merged features' files `fr` holds (the same `Ctx.flat()` reading the move copies from), byte for byte. Rejected (a): the switch lives on `fr`, not the product branch, so the copy branch cannot carry the flip, and any repo-side evidence would be self-asserted. Rejected (c): a trailer anyone can write. The structural test lets nothing through that `fr` does not already hold as merged history. It reads `fr` through the fr worktree, created in CI when absent, only on a branch that already carries fr files.

<!-- fr:journal kind=decision scope=plan id=p7-r1-recopy created=2026-11-13T12:23:52+00:00 phase=7 -->
### p7-r1-recopy · decision · A source that moved after the copy is copied again, never refused (phase 7)

At verify and at switch the move compares a digest of the source (the default ref's placement-bound tree, or the merged features' flat content from `fr`) with the one recorded at copy; a difference resets the move to copy (idempotent by content), at most 3 times per invocation, then refuses naming the re-run. Into repo, the re-copy is one more commit on the move's own copy branch (only when the state's copy_sha is its ancestor).

<!-- fr:journal kind=decision scope=plan id=p7-r4-dest-validation created=2026-11-13T12:23:54+00:00 phase=7 -->
### p7-r4-dest-validation · decision · Verify validates the destination feature roots one by one, plus a bookkeeping lint (phase 7)

Each destination feature root (OWNER/BASE/HEADS/merged.yaml included) is laid out and validated with `validate_repo` per root, which is how `iter_paths_of` reaches kinds under quiet and stealth; the destination may report no issue the source lacks and check no fewer artifacts. `bookkeeping_problems` checks the four files as their readers need them, and the bytes must equal what the move synthesised.

<!-- fr:journal kind=decision scope=plan id=p7-r5-artifact-only created=2026-11-13T12:23:55+00:00 phase=7 -->
### p7-r5-artifact-only · decision · Copies keep placement-bound paths with no .git* component, and refuse anything else (phase 7)

`move.foreign` is `not placement_bound(rel)` or any `.git*` path component; every direction into repo refuses such a path (exit 2, nothing written), and copies into fr or a tracking repo filter the repo side and refuse on the fr side.

<!-- fr:journal kind=decision scope=plan id=p7-r7-ci-refs created=2026-11-13T12:23:57+00:00 phase=7 -->
### p7-r7-ci-refs · decision · In CI, drift refuses a shallow checkout or one without the default ref; no network probe (phase 7)

With a remote configured, a shallow clone or an unresolvable default ref refuses under a CI marker and warns elsewhere; a non-shallow checkout with the default ref and no origin/fr means no switch exists. This repo's validate-artifacts job now checks out with fetch-depth: 0.

<!-- fr:journal kind=finding scope=plan id=p7-quiet-to-stealth-live-branches-resolved created=2026-11-13T12:24:12+00:00 phase=7 state=fixed resolves=p7-quiet-to-stealth-live-branches -->
### p7-quiet-to-stealth-live-branches-resolved · finding [fixed] · resolves p7-quiet-to-stealth-live-branches: After a quiet -> stealth whole move, live quiet workspaces migrate to repo, not stealth (phase 7)

fixed with review finding p7-r6 in b0f803ae2 and 65b6a59bd: a quiet-to-stealth move refuses while any quiet feature is unmerged (at start and at the switch), and migrate-branch refuses to write into a stealth-bound repo's branch

<!-- fr:journal kind=decision scope=plan id=p7-r5-git-like-spellings created=2026-11-13T12:29:22+00:00 phase=7 -->
### p7-r5-git-like-spellings · decision · p7-r5 refuses .git-like components as git's verify_path reads them, on top of the case-sensitive allowlist (phase 7)

Extends decision p7-r5-artifact-only after a security review: `placement_bound` stays the allowlist, matched exactly and case-sensitively, and `move.git_like` adds a refusal for any component that is `.git*` once NFC-normalised, stripped of HFS-ignorable codepoints and trailing dots/spaces, and casefolded, or that is an NTFS short name (`git~1`, `gitmod~1`, `gi<hex4>~n`). Ordinary artifacts that merely name git (`...-gitops-design.md`) stay allowed.

<!-- fr:journal kind=decision scope=plan id=p7-r5-git-names-exact created=2026-11-13T13:04:54+00:00 phase=7 -->
### p7-r5-git-names-exact · decision · git_like refuses exactly .git, .gitmodules and .gitattributes, not every .git* name (phase 7)

Narrows decision p7-r5-git-like-spellings: a `.git*` prefix also refused `.gitkeep`, a plain placeholder the acceptance tree carries, which the move then left on the default branch. The refused set is the names git acts on in a tree (`.git`, `.gitmodules`, `.gitattributes`) and their NTFS short names, each after NFC, HFS-ignorable removal, trailing dot/space stripping and casefolding.

<!-- fr:journal kind=decision scope=plan id=p7-r5-ntfs-streams created=2026-11-13T13:09:58+00:00 phase=7 -->
### p7-r5-ntfs-streams · decision · p7-r5 refuses any path component holding a colon, and .gitignore with its short name (phase 7)

Extends decisions p7-r5-artifact-only, p7-r5-git-like-spellings and p7-r5-git-names-exact after a second security review: a component containing `:` is refused outright (NTFS alternate data streams such as `.git::$INDEX_ALLOCATION` and `.gitattributes:s` resolve to the real names, and no fr artifact name needs a colon). The refused git names are `.git`, `.gitmodules`, `.gitattributes` and `.gitignore`, plus `git~N`, `gitmod~N`, `gitatt~N`, `gitign~N` and the hashed `gi<hex4>~N` forms, compared after NFC, HFS-ignorable removal, trailing dot/space stripping and casefolding. `.gitkeep` stays allowed because fr's acceptance tree carries `docs/acceptance/features/.gitkeep`. The case-sensitive `placement_bound` allowlist remains the primary gate.

<!-- fr:journal kind=review scope=plan id=review-phase-7 created=2026-11-13T13:43:33+00:00 phase=7 -->
### review-phase-7 · review · Phase 7 (placement moves and drift) review, range 91fc8ddc9..da9e43d35 (phase 7)

Reviewer a15b49e54527c00f8 (opus) returned not ready with seven in-scope findings and one spec-level one, three reproduced (a resumed move losing a feature merged meanwhile, a move killed between the switch commit and its push stuck for good, drift refusing the move's own PRs and deadlocking quiet to repo). It confirmed no force push, nothing pushed to the default branch, synthesised merged records that cannot mark an unmerged feature merged, and the feature-id and symlink fixes. All seven were fixed at 65b6a59bd..dc8382478 with two automated security follow-ups (case-insensitive and NTFS-stream .git spellings); the full suite (15909 passed) ran after the last code commit.

<!-- fr:journal kind=finding scope=plan id=p7-r1 created=2026-11-13T13:43:33+00:00 phase=7 state=open review_scope=in -->
### p7-r1 · finding [open] (reviewer: in scope) · A move resumed after the default ref moved lost the features merged meanwhile (phase 7)

source_sha was pinned at copy and never re-checked (reproduced: a gamma row missing from the quiet fold).

<!-- fr:journal kind=finding scope=plan id=p7-r2 created=2026-11-13T13:43:33+00:00 phase=7 state=open review_scope=in -->
### p7-r2 · finding [open] (reviewer: in scope) · A step killed between its commit and its push could not be completed by a re-run (phase 7)

The switch re-committed from origin/fr and failed for good; migrate-branch left commits unpushed (reproduced for the switch).

<!-- fr:journal kind=finding scope=plan id=p7-r3 created=2026-11-13T13:43:33+00:00 phase=7 state=open review_scope=in -->
### p7-r3 · finding [open] (reviewer: in scope) · branch_drift refused the move's own removal and copy-to-repo branches in CI (phase 7)

Deletions counted as drift; the move from quiet to repo deadlocked (reproduced).

<!-- fr:journal kind=finding scope=plan id=p7-r4 created=2026-11-13T13:43:33+00:00 phase=7 state=open review_scope=in -->
### p7-r4 · finding [open] (reviewer: in scope) · Verify's validation leg compared identical bytes (phase 7)

The destination layout and its synthesised bookkeeping were never validated, against R27.

<!-- fr:journal kind=finding scope=plan id=p7-r5 created=2026-11-13T13:43:33+00:00 phase=7 state=open review_scope=in -->
### p7-r5 · finding [open] (reviewer: in scope) · migrate-branch and --run copied any path from fr or the tracking repo into the product branch (phase 7)

A planted workflow or .gitattributes would be committed and pushed.

<!-- fr:journal kind=finding scope=plan id=p7-r6 created=2026-11-13T13:43:33+00:00 phase=7 state=open review_scope=in -->
### p7-r6 · finding [open] (reviewer: in scope) · A quiet-to-stealth move left live quiet branches to migrate-branch, which pushed their fr files to the target (phase 7)

Against R24; supersedes the executor's out-of-scope p7-quiet-to-stealth-live-branches.

<!-- fr:journal kind=finding scope=plan id=p7-r7 created=2026-11-13T13:43:33+00:00 phase=7 state=open review_scope=in -->
### p7-r7 · finding [open] (reviewer: in scope) · Drift detection failed open silently in a CI checkout without origin/fr or the default ref (phase 7)

A shallow checkout checked nothing.

<!-- fr:journal kind=finding scope=plan id=p7-r8 created=2026-11-13T13:43:33+00:00 phase=7 state=open review_scope=out -->
### p7-r8 · finding [open] (reviewer: out of scope) · migrate-branch's own removal commit leaves fr files and chore(fr) commits in branch history (phase 7)

Follows from R28's wording against R23/R24; a spec decision, tracked by derio-net/super-fr#1430.

<!-- fr:journal kind=finding scope=plan id=p7-r1-resolved created=2026-11-13T13:43:33+00:00 phase=7 state=fixed resolves=p7-r1 -->
### p7-r1-resolved · finding [fixed] · resolves p7-r1: A move resumed after the default ref moved lost the features merged meanwhile (phase 7)

65b6a59bd: the copy records its source digest; verify and switch re-copy when it moved (bounded, then refuse naming the re-run); the removal branch covers the final copy.

<!-- fr:journal kind=finding scope=plan id=p7-r2-resolved created=2026-11-13T13:43:33+00:00 phase=7 state=fixed resolves=p7-r2 -->
### p7-r2-resolved · finding [fixed] · resolves p7-r2: A step killed between its commit and its push could not be completed by a re-run (phase 7)

65b6a59bd, b0f803ae2: the switch decides from the local fr and pushes an existing switch commit; migrate-branch pushes pending commits and records repo only when nothing is unpushed; kill tests inside each step.

<!-- fr:journal kind=finding scope=plan id=p7-r3-resolved created=2026-11-13T13:43:33+00:00 phase=7 state=fixed resolves=p7-r3 -->
### p7-r3-resolved · finding [fixed] · resolves p7-r3: branch_drift refused the move's own removal and copy-to-repo branches in CI (phase 7)

b0f803ae2: --diff-filter=d; the copy branch into repo recognised structurally against the merged features on fr (decision p7-r3-return-copy-structural).

<!-- fr:journal kind=finding scope=plan id=p7-r4-resolved created=2026-11-13T13:43:33+00:00 phase=7 state=fixed resolves=p7-r4 -->
### p7-r4-resolved · finding [fixed] · resolves p7-r4: Verify's validation leg compared identical bytes (phase 7)

65b6a59bd: verify validates each destination feature root plus a bookkeeping check whose bytes must equal what the move synthesised; a corrupted merged.yaml fails verify.

<!-- fr:journal kind=finding scope=plan id=p7-r5-resolved created=2026-11-13T13:43:33+00:00 phase=7 state=fixed resolves=p7-r5 -->
### p7-r5-resolved · finding [fixed] · resolves p7-r5: migrate-branch and --run copied any path from fr or the tracking repo into the product branch (phase 7)

65b6a59bd, b0f803ae2, 016cf4e3f, bb102f5df, 5a8ed3b2c: only placement_bound paths copied, exact and case-sensitive; .git-like components refused as git's verify_path reads them (case, HFS-ignorables, NTFS short names, any colon), in every direction.

<!-- fr:journal kind=finding scope=plan id=p7-r6-resolved created=2026-11-13T13:43:33+00:00 phase=7 state=fixed resolves=p7-r6 -->
### p7-r6-resolved · finding [fixed] · resolves p7-r6: A quiet-to-stealth move left live quiet branches to migrate-branch, which pushed their fr files to the target (phase 7)

65b6a59bd, b0f803ae2: quiet-to-stealth refuses while any quiet feature is unmerged (checked before state and at switch); _into_repo refuses a stealth workspace and a move to stealth in progress.

<!-- fr:journal kind=finding scope=plan id=p7-r7-resolved created=2026-11-13T13:43:33+00:00 phase=7 state=fixed resolves=p7-r7 -->
### p7-r7-resolved · finding [fixed] · resolves p7-r7: Drift detection failed open silently in a CI checkout without origin/fr or the default ref (phase 7)

b0f803ae2, c6ec70d17: in CI a shallow checkout or a missing default ref refuses naming fetch-depth: 0, elsewhere a warning; the validate-artifacts job fetches full history.

<!-- fr:journal kind=finding scope=plan id=p7-r8-resolved created=2026-11-13T13:43:33+00:00 phase=7 state=open resolves=p7-r8 out_of_scope=true -->
### p7-r8-resolved · finding [out-of-scope] · resolves p7-r8: migrate-branch's own removal commit leaves fr files and chore(fr) commits in branch history (phase 7)

Follows from R28's wording, not this code; plan 3 may not change a requirement. Tracked by derio-net/super-fr#1430 for a spec decision.

<!-- fr:journal kind=lens scope=plan id=lens-security-1 created=2026-11-13T13:44:06+00:00 lens=security -->
### lens-security-1 · lens · Stealth and quiet are privacy guarantees enforced by new hooks, a forge guard and file movers; every phase drew security findings, so the whole diff is reviewed once for cross-phase gaps

<!-- fr:journal kind=review scope=plan id=lens-review-security created=2026-11-13T14:36:14+00:00 -->
### lens-review-security · review · Security lens review of the whole feature, f90986ffb..HEAD

Reviewer ab68c1818d5096289 (opus) reviewed the whole diff through the security lens, added by the orchestrator (lens-security-1) because quiet and stealth are privacy guarantees enforced by new hooks, a forge guard and file movers. It found the forge guard, privacy check, hook fr resolution and settings-paths quoting clean, and raised two cross-phase findings (one reproduced) plus a non-security deliver crash under quiet and stealth. All three were fixed at 9f8f44764, 2d50806b5 and 4bb686fdb; the full suite (15923 passed) ran after the last code commit.

<!-- fr:journal kind=finding scope=plan id=l-security-r1 created=2026-11-13T14:36:14+00:00 state=open review_scope=in -->
### l-security-r1 · finding [open] (reviewer: in scope) · The stealth fr-path push check scanned only the first-parent range

A merged side branch that added then removed an fr file pushed its contents to the target's history (reproduced).

<!-- fr:journal kind=finding scope=plan id=l-security-r2 created=2026-11-13T14:36:14+00:00 state=open review_scope=in -->
### l-security-r2 · finding [open] (reviewer: in scope) · OWNER from the fr branch was printed unvalidated into fr archive --branch suggestions

Whoever can push to fr could plant a shell command in the closeout, debt and status output.

<!-- fr:journal kind=finding scope=plan id=lens-pr-body-quiet created=2026-11-13T14:36:14+00:00 state=open review_scope=in -->
### lens-pr-body-quiet · finding [open] (reviewer: in scope) · deliver raised ValueError under quiet and stealth with forge.pr_body minimal

The PR-body path lies outside the product checkout there; no test covered it.

<!-- fr:journal kind=decision scope=plan id=lens-push-scan-separate-ranges created=2026-11-13T14:36:14+00:00 -->
### lens-push-scan-separate-ranges · decision · The fr-path push scan and the R13/R14 commit checks use separate commit ranges

commits_the_push_adds lists every commit the push sends (no --first-parent), excluding the remote's tips read live with ls-remote and refusing when they cannot be read; unpushed stays first-parent for the subject and squash rules. Quiet has no push-time fr-path scan (R23 is enforced where fr commits), so it had no such gap.

<!-- fr:journal kind=decision scope=plan id=lens-bookkeeping-untrusted created=2026-11-13T14:36:14+00:00 -->
### lens-bookkeeping-untrusted · decision · OWNER, BASE, HEADS and stealth state read from fr or tracking are untrusted input

Unsafe owners are dropped with a notice that never echoes them, shas must be full hex, and every printed command shell-quotes the branch, since git allows characters a shell interprets.

<!-- fr:journal kind=finding scope=plan id=l-security-r1-resolved created=2026-11-13T14:36:14+00:00 state=fixed resolves=l-security-r1 -->
### l-security-r1-resolved · finding [fixed] · resolves l-security-r1: The stealth fr-path push check scanned only the first-parent range

9f8f44764: commits_the_push_adds scans every pushed commit against live remote tips; regression tests for the merged add-then-remove, a stale tracking ref and an unreadable remote.

<!-- fr:journal kind=finding scope=plan id=l-security-r2-resolved created=2026-11-13T14:36:14+00:00 state=fixed resolves=l-security-r2 -->
### l-security-r2-resolved · finding [fixed] · resolves l-security-r2: OWNER from the fr branch was printed unvalidated into fr archive --branch suggestions

2d50806b5: owner_of validates with unsafe_branch, BASE/HEADS/product_head must be full shas, archive_branch_command shell-quotes; tests in test_placement_bookkeeping_untrusted.py.

<!-- fr:journal kind=finding scope=plan id=lens-pr-body-quiet-resolved created=2026-11-13T14:36:14+00:00 state=fixed resolves=lens-pr-body-quiet -->
### lens-pr-body-quiet-resolved · finding [fixed] · resolves lens-pr-body-quiet: deliver raised ValueError under quiet and stealth with forge.pr_body minimal

4bb686fdb: _deliver_pr_gate names the render with _shown_path and commits it through the run-writes seam; tested under quiet and stealth.
