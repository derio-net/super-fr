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
