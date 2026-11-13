<!-- fr:journal-schema=4 -->
# Journal: 2026-11-12-review-lenses

<!-- fr:journal kind=decision scope=plan id=plan-shape created=2026-11-12T17:18:58+00:00 -->
### plan-shape · decision · Four agentic phases, one per group of requirements; no manual phase

Phase 1 the lens set (R1-R3, skeleton), phase 2 adding lenses and path rules (R4-R7), phase 3 the lens-review step and its evidence gate (R8-R11, R13), phase 4 the PR section, skills, agents and docs (R12, R14). Phases 2 and 3 are hard: two artifact migrations, and the evidence gate every review step uses. Nothing is manual: every row is proven by a scenario on a candidate build.

<!-- fr:journal kind=discovery scope=plan id=p1-no-fr-yaml-strict-loader created=2026-11-12T19:13:34+00:00 phase=1 -->
### p1-no-fr-yaml-strict-loader · discovery · fr._yaml has no strict loader; the model reuses the artifacts one (phase 1)

The plan said `fr._yaml`'s strict loader, but `fr/_yaml.py` only dumps. The duplicate-key
refusing loader is `fr.artifacts.structure._StrictLoader`; `fr/lenses/model.py` imports it, so a
repeated key in `.fr/lenses.yaml` is refused as it is for registered artifacts.

<!-- fr:journal kind=discovery scope=plan id=p1-no-verifications-sync-script created=2026-11-12T19:13:34+00:00 phase=1 -->
### p1-no-verifications-sync-script · discovery · No verifications sync script exists; the lenses one follows sync-agents-data.py (phase 1)

`scripts/sync-verifications-data.py` does not exist (the verifications copy is a plain `cp`).
`scripts/sync-lenses-data.py` is modelled on `scripts/sync-agents-data.py` (no flag writes,
`--check` verifies, also removes a stale copy).

<!-- fr:journal kind=discovery scope=plan id=p1-wheel-needs-no-glob created=2026-11-12T19:13:34+00:00 phase=1 -->
### p1-wheel-needs-no-glob · discovery · No pyproject glob needed for the wheel copy (phase 1)

`packages/fr/pyproject.toml` builds `packages = ["src/fr"]`, which carries every file under
the package, so `fr/lens_manifests/*.yaml` ships without a glob (verifications has none either).
The copy is named `lens_manifests` (not `lenses`) so it is not a Python package beside `fr/lenses/`.

<!-- fr:journal kind=discovery scope=plan id=p1-install-guard-is-a-new-file created=2026-11-12T19:13:34+00:00 phase=1 -->
### p1-install-guard-is-a-new-file · discovery · The install drift guard is tests/unit/test_install_copies_lenses.py (phase 1)

No existing guard covers verifications, so a small lenses-specific file pins that the marketplace
rsync excludes nothing lens-related and that `shipped_lens_dir()` finds the four.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-12T19:13:34+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

Task 3 is data files, a sync script and tripwires; nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-12T19:13:34+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

The command module is three thin handlers over resolve/check; nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-11-12T19:13:34+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

A scenario script, a doc paragraph and a row move; nothing to clean.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-12T19:26:37+00:00 phase=1 -->
### review-p1 · review · Phase 1 review: R1-R3 met, four small in-scope defects, all fixed (phase 1)

A separate reviewer read the phase's diff against spec R1-R3. It confirmed the id
grammar, the config keys, every `check` condition, the read-only exemption, the
shipped briefs' closing sentence, the wheel copy and its guard, install coverage
and the scenario. It judged the `_StrictLoader` import acceptable
(`fr/isolation/scaffold.py` imports the same name). Four findings, all in scope.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-12T19:26:37+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · shipped_lenses() does not check a manifest's file stem against its lens id (phase 1)

`fr/lenses/resolve.py`: a copied manifest that kept another lens's id replaced
that lens in the dict silently. `fr/verification/resolve.py` refuses the same case.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-12T19:26:37+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · list/show crash on an unreadable config; check crashes on a malformed shipped manifest (phase 1)

`load_config` and `shipped_lenses` read files bare, so an undecodable
`.fr/lenses.yaml` gave `list` and `show` a traceback where exit 2 is documented;
`check_config` read the shipped set outside its `try`.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-12T19:26:37+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · a config that disables a shipped lens and also defines it passes check (phase 1)

Contradictory input accepted silently. (The reviewer also said the result is
labelled `repo`; it is labelled `repo (replaces shipped)`, so that part is wrong.)

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-12T19:26:37+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · PathRule.paths accepts blank glob strings (phase 1)

An empty or whitespace glob parsed; R6 would consume it in phase 2.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-12T19:26:37+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: shipped_lenses() does not check a manifest's file stem against its lens id (phase 1)

`shipped_lenses` raises `LensError` when `path.stem != lens.id`; test `test_a_shipped_manifest_named_for_another_lens_is_refused`.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-12T19:26:37+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: list/show crash on an unreadable config; check crashes on a malformed shipped manifest (phase 1)

`fr.lenses.model.read_text` turns OSError/UnicodeDecodeError into `LensError`; `load_config` and `shipped_lenses` use it and `check_config` reads both inside one `try`. Tests: `test_an_undecodable_config_is_a_lens_error`, `test_an_undecodable_file_is_one_problem`, `test_a_malformed_shipped_manifest_is_a_problem_not_a_crash`, `test_an_undecodable_config_makes_list_and_show_exit_2_without_a_traceback`.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-12T19:26:37+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: a config that disables a shipped lens and also defines it passes check (phase 1)

`check_config` reports `the file disables and also defines <id>`; covered by a new `test_one_named_problem_each` case.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-12T19:26:37+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: PathRule.paths accepts blank glob strings (phase 1)

`PathRule` refuses a blank glob; two new `test_parse_config_refuses` cases.

<!-- fr:journal kind=discovery scope=plan id=p2-one-kind-tokens-table created=2026-11-12T21:42:59+00:00 phase=2 -->
### p2-one-kind-tokens-table · discovery · input, lens and step share one table-driven validator (P2.T1.S3) (phase 2)

`JournalEntry._one_kind_tokens` reads `_ONE_KIND_TOKENS` (token -> kind, optional scope,
reason), replacing the inline `input` check; the `input` error text is unchanged, so the
existing `match="`input` is only valid"` tests still hold.

<!-- fr:journal kind=discovery scope=plan id=p2-lens-retry-is-a-no-op created=2026-11-12T21:42:59+00:00 phase=2 -->
### p2-lens-retry-is-a-no-op · discovery · an identical lens addition is a no-op, so a retried apply does not mint lens-<id>-2 (phase 2)

fr numbers lens entries by counting the journal's entries for that lens, so a retry of an
interrupted apply would otherwise add a second entry. `_lens_entry` returns nothing when an
entry with the same lens, reason, body, step and phase already exists. Consequence: re-adding
the very same reason from the command line is also a no-op; a different reason is kept.

<!-- fr:journal kind=discovery scope=plan id=p2-head-rules-from-working-tree created=2026-11-12T21:42:59+00:00 phase=2 -->
### p2-head-rules-from-working-tree · discovery · the branch's path rules are read from the working tree, like every other lens setting (phase 2)

`fr.lenses.rules.head_config_text` reads `.fr/lenses.yaml` from the working tree (as
`load_config` does for `disable` and definitions); the base's copy is `git show
<default-ref>:.fr/lenses.yaml`. With no default ref, HEAD's rules are in force but there is
no base to diff against, so `lens_set` applies no rule and says so in `warnings`. Outside a
git checkout there is no base; a git refusal inside one is a `LensError`, never "no rules".

<!-- fr:journal kind=discovery scope=plan id=p2-feature-diff-shared created=2026-11-12T21:42:59+00:00 phase=2 -->
### p2-feature-diff-shared · discovery · feature_merge_base and feature_diff were written shared from the start (P2.T3.S3) (phase 2)

`fr.proportionality.feature_merge_base` / `feature_diff` are the one diff definition; `_run`
and `fr.lenses.accumulate` both call them, and `tests/unit/test_proportionality*.py` pass
unchanged.

<!-- fr:journal kind=discovery scope=plan id=p2-cli-lens-refusals created=2026-11-12T21:42:59+00:00 phase=2 -->
### p2-cli-lens-refusals · discovery · fr journal add --kind lens refuses --scope debug and --id (phase 2)

A lens is read from the run's spec and plan journals only, so `--scope debug` is refused, and
`--id` is refused because fr assigns `lens-<id>-<n>`. `--lens` on any other kind is refused.
A step record's `{kind: lens}` item refuses `id` and `step` the same way (the model).

<!-- fr:journal kind=discovery scope=plan id=p2-rows-unwired-with-ci-scenarios created=2026-11-12T21:42:59+00:00 phase=2 -->
### p2-rows-unwired-with-ci-scenarios · discovery · both rows moved to unwired although their scenarios already run in CI (phase 2)

`review-lenses-accumulate` and `review-lenses-path-rules` carry unit and int refs and their
scenarios are registered in `tests/integration/test_scenarios.py`; they stay `unwired` as the
brief asked, until phase 3 adds the lens-review cases the acceptance text names.

<!-- fr:journal kind=discovery scope=plan id=p2-empty-r1-records-dir created=2026-11-12T21:42:59+00:00 phase=2 -->
### p2-empty-r1-records-dir · discovery · an empty untracked docs/superpowers/runs/r1.records/ was already in the worktree (phase 2)

Dated before this phase started and holding nothing, so git ignores it. Not caused by this
phase's runs (every new test here builds its repo under tmp_path); worth a look if it
reappears after a suite run.

<!-- fr:journal kind=discovery scope=plan id=p2-suite-slow-under-shared-load created=2026-11-12T21:42:59+00:00 phase=2 -->
### p2-suite-slow-under-shared-load · discovery · the full suite took 42 minutes here; a first run hit its 50-minute bound at 99% (phase 2)

Another worktree's full suite ran on the host at the same time. The first run was killed
by its own `timeout 3000` with no failure printed; the rerun (bound 5400 s) passed and is
the evidence named below. CI's sharded run is unaffected.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-12T21:42:59+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

The lens branch in apply.py is one helper (_lens_entry) beside the existing loop, and the CLI path reuses the engine through the one-entry record; nothing duplicated to fold.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-11-12T21:42:59+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

The status command is two small formatters over lens_set; the scenarios share one sourced fixture (_lens_fixture.sh) already; nothing to clean.

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-11-12T22:00:53+00:00 phase=2 -->
### review-p2 · review · Phase 2 review: migrations sound; the lens set failed open in four ways, all fixed (phase 2)

A separate reviewer read the phase's diff against spec R4-R7 and the
artifact-versioning rule. Confirmed sound: the journal 3->4 and record 11->12
hops, their wiring and hop-by-hop chain tests, the loosened older tests (no guard
lost), the fr-stamped `step=`, and that a `lens` entry cannot be resolved. Six
findings, all in scope; p2-r1 to p2-r4 were reproduced by the reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-12T22:00:53+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · lens_set drops a rule-required lens the branch disabled, with only a warning (phase 2)

`fr/lenses/accumulate.py`: a branch committing `disable: [security]` escaped a
default-branch rule requiring `security`; only `fr lenses check` objected.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-12T22:00:53+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · a remote with no readable default ref or merge-base applies no path rule (phase 2)

A single-ref or shallow checkout made `lens_set` return no rule lens with a
warning, so the base's rules were void.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-12T22:00:53+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · with no remote, the branch's own rules never apply (phase 2)

No ref meant no diff, so no rule matched, against spec 3.A.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-12T22:00:53+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · base_config_text reads any git-show failure as no file (phase 2)

`fr/lenses/rules.py`: an unreadable ref or blob dropped the base's rules silently.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-12T22:00:53+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · both phase-2 rows are set to unwired though their refs run in CI (phase 2)

The reviewer also said the path-rules row's text describes the old design; the
fragment already carries the `reword` amendment, so that part is wrong.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-11-12T22:00:53+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · fr journal add --kind lens commits and prints the placeholder id (phase 2)

The commit subject named `lens-<id>` and a deduplicated repeat printed "added".

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-12T22:00:53+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: lens_set drops a rule-required lens the branch disabled, with only a warning (phase 2)

`lens_set_for` raises `LensError` naming the rule, lens and file; test `test_a_branch_cannot_disable_a_lens_a_rule_requires_for_its_diff`. Spec 3.B states it.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-12T22:00:53+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: a remote with no readable default ref or merge-base applies no path rule (phase 2)

`default_ref` refuses a remote with no default branch ref here and `_changed` refuses a missing merge-base; tests `test_a_remote_with_no_default_ref_here_is_refused`, `test_a_branch_with_no_merge_base_is_refused`. Spec 3.A states it.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-12T22:00:53+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: with no remote, the branch's own rules never apply (phase 2)

With no remote every rule in force applies (`rules.every_rule`), with a warning and no file; test `test_with_no_remote_every_rule_of_the_branch_applies`. Spec 3.A states it.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-12T22:00:53+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: base_config_text reads any git-show failure as no file (phase 2)

`base_config_text` asks `git ls-tree` first: a readable ref with no file is None, any failed read is a `LensError`; tests in `test_lenses_rules.py`.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-12T22:00:53+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: both phase-2 rows are set to unwired though their refs run in CI (phase 2)

Both rows moved to `not-implemented` with a note naming the partial CI evidence; phase 3 moves them to `ci`. The reword half is refuted: the amendment was already there.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-11-12T22:00:53+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: fr journal add --kind lens commits and prints the placeholder id (phase 2)

The subject uses `fr.record.apply.next_lens_id`; a repeat prints `already recorded`. Tests `test_the_same_lens_and_reason_twice_says_so_and_names_no_placeholder`, `test_the_commit_subject_names_the_assigned_id`.

<!-- fr:journal kind=discovery scope=plan id=p3-needs-without-journal-plan created=2026-11-13T00:25:26+00:00 phase=3 -->
### p3-needs-without-journal-plan · discovery · lens-review ships with needs: [spec, plan]: the spec's journal:plan in needs is a cycle with review-phase (phase 3)

Spec §3.C's snippet (and the plan's test) give `needs: [spec, plan, journal:plan]`.
`review-phase` also needs and emits `journal:plan`, so `fr workflow check` reports
`cycle detected in needs/emits: lens-review -> review-phase -> lens-review` for both
shipped shapes. The step ships `needs: [spec, plan]` with a manifest comment;
`spec-review` is the precedent (it emits `journal:spec` and needs only `[spec]`).
The step still reads the plan journal's lens entries through `lens_set`. Spec §3.C's
snippet should be amended to match (the orchestrator's call; not edited here).

<!-- fr:journal kind=discovery scope=plan id=p3-feature-target-needs-review-evidence created=2026-11-13T00:25:26+00:00 phase=3 -->
### p3-feature-target-needs-review-evidence · discovery · the feature target applies to every flat journal:plan step; the lens set is computed only for one that declares review evidence (phase 3)

The light shape's `plan` step emits `journal:plan` and declares only `single-phase`;
giving it the feature target made its resolve compute a lens set and read the plan
journal (refused: no plan recorded yet). `_reviews_the_feature(step, target)` (feature
target AND any of review/reviewer/findings/lenses declared) gates the lens machinery.

<!-- fr:journal kind=discovery scope=plan id=p3-adoption-owes-lens-review created=2026-11-13T00:25:26+00:00 phase=3 -->
### p3-adoption-owes-lens-review · discovery · adoption never infers lens-review done; a plain adopt with an open PR now lands on lens-review, not deliver (phase 3)

`build_run_state` inferred every step before an open PR's `deliver` cursor as done,
lens-review included, with no evidence. `_owed_before` moves the cursor back to a step
declaring `lenses` that the superseded run had not done, with a note. This also changes
a plain adopt over an open PR: `test_run_adopt.py`'s open-PR test now expects
`lens-review` (renamed, deliberately).

<!-- fr:journal kind=discovery scope=plan id=p3-this-runs-reshape created=2026-11-13T00:25:26+00:00 phase=3 -->
### p3-this-runs-reshape · discovery · this branch's run needed only fr run reshape --yes: added lens-review, nothing lost (phase 3)

With lens-review in the shipped manifest the run drifted (`fr run status` warned).
`fr run reshape 2026-11-12-feat-code-quality-steps` previewed `added: lens-review`;
`--yes` wrote it in commit 535eb88a2 with the cursor still on `implement` and every
unit kept. No adopt --supersede was needed.

<!-- fr:journal kind=discovery scope=plan id=p3-skill-and-explainer-sections created=2026-11-13T00:25:26+00:00 phase=3 -->
### p3-skill-and-explainer-sections · discovery · fr-goal SKILL.md and the fr-goal explainer got a short 7a. lens-review section ahead of phase 4 (phase 3)

`tests/integration/test_fr_goal_shape.py`'s narration tripwire fails a manifest step the
skill does not narrate, and `fr docs check` flagged the fr-goal explainer. Both got a
short `### 7a. lens-review` section; the tripwire's header regex now accepts a lettered
step so `### 8. deliver` (cited as §8 by prose and tests) keeps its number. Mirrors
regenerated (sync-opencode, sync-hermes). Phase 4 (R14) owns the full skill prose and
the operator page. index.md and why-fr.md got reviewed-stamp bumps only. The skill
is at its 120-line cap: the section was paid for by joining three soft-wrapped lines
of single paragraphs (§6 twice, §8 once), which renders identically; phase 4 has no
free lines left in it.

<!-- fr:journal kind=discovery scope=plan id=p3-acceptance-check-origin-main-rows created=2026-11-13T00:25:26+00:00 phase=3 -->
### p3-acceptance-check-origin-main-rows · discovery · fr acceptance check --no-fetch reports 18 ERRORs, all for rows origin/main gained after this branch's base (phase 3)

origin/main merged the vk-compat removal (#1424, archived #1425) and v7.0.0-rc.1
after this branch's merge-base; the fold reads those fragments, whose specs and tests
this branch does not have (`2026-11-12-remove-vk-compat`, `test_vk_compat_removed.py`,
`test_migration_plan_vk_version.py`). None is a row of this feature. Merging
origin/main into the branch should clear them; not done here (single-writer phase).

<!-- fr:journal kind=discovery scope=plan id=p3-no-remote-examined-files created=2026-11-13T00:25:26+00:00 phase=3 -->
### p3-no-remote-examined-files · discovery · with no remote there is no diff: a lens reviewer's examined files are checked to exist in the checkout (phase 3)

`LensSet` now carries `merge_base` and `changed` (None with no remote). The returns
check compares `examined:` against `changed`; with no remote it checks each named file
is a file in the checkout, and the brief's note says there is no diff.

<!-- fr:journal kind=discovery scope=plan id=p3-lens-findings-any-phase created=2026-11-13T00:25:26+00:00 phase=3 -->
### p3-lens-findings-any-phase · discovery · lens findings are gated by id grammar whatever their phase tag (phase 3)

The feature target's findings are every plan-journal finding whose id matches
`l-<lens>-r<k>`, phase tag or not (fail-closed); the record writes them `global: true`
by convention and the refusal's fix line says `--global`.

<!-- fr:journal kind=discovery scope=plan id=p3-resolve-tests-red-checked-after created=2026-11-13T00:25:26+00:00 phase=3 -->
### p3-resolve-tests-red-checked-after · discovery · the task-3 resolve tests were first run after the gate existed; red confirmed by reverting run_cmd.py (phase 3)

tests/unit/test_lenses_review_resolve.py was written before the gate code but first
executed after it. Restoring HEAD's run_cmd.py made 20 of its 22 tests fail; the two
that pass are refusals that hold either way (lenses= passed; open finding with an
unreadable session). The file was then restored.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-13T00:25:26+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

The brief is one thin _lens_review_brief over fr.lenses.review.lens_review_brief, and the owed-evidence rule is one helper (owed_evidence) the template and the resolve both read; nothing duplicated to fold.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t4 created=2026-11-13T00:25:26+00:00 phase=3 -->
### no-refactor-p3-t4 · discovery · no-refactor-because P3.T4 (phase 3)

Two small fixes (adoption's _owed_before, one reshape message); no second copy of anything was written.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t5 created=2026-11-13T00:25:26+00:00 phase=3 -->
### no-refactor-p3-t5 · discovery · no-refactor-because P3.T5 (phase 3)

The three scenarios share _lens_fixture.sh, whose lens_base / lens_review_repo split was made while writing them; the AGENTS.md lines and the row moves have nothing to clean.

<!-- fr:journal kind=review scope=plan id=review-p3 created=2026-11-13T00:39:53+00:00 phase=3 -->
### review-p3 · review · Phase 3 review: no bypass in the shipped shapes; a custom shape's flat step was weakened, fixed (phase 3)

A separate reviewer attacked the lens-review gate (R8-R11, R13). Sound on the
shipped shapes: fewer reviewers than lenses, one id for two lenses, a wrong-lens
block, a file outside the diff, an early dispatch, a caller-passed `lenses`, an
unreadable set, adopt/reshape skipping the step. It reproduced the needs cycle
the executor reported. Seven findings, all in scope, all fixed.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-13T00:39:53+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · any flat journal:plan step with review evidence got the feature target (phase 3)

A repo shape's flat step `{emits: [journal:plan], evidence: [findings]}` used to be
refused (no target) and now resolved with non-lens plan findings open.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-13T00:39:53+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · fr-goal skill says the last review-phase resolve opens deliver; light list omits lens-review (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-13T00:39:53+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · spec 3.C still shows needs: [spec, plan, journal:plan], a cycle (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-11-13T00:39:53+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · five refusals or branches of the lens-review gate had no test (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-11-13T00:39:53+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · the record template shows reviewer: <id>, not the <lens>=<id> map (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-11-13T00:39:53+00:00 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · _verify_reviewer inlines the dispatch walk _dispatches_since claims to own (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-11-13T00:39:53+00:00 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · a file repeated in examined: inflates the lens's examined count (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-13T00:39:53+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: any flat journal:plan step with review evidence got the feature target (phase 3)

`_evidence_target` gives the feature target only to a step that declares `lenses`; any other flat journal:plan step keeps the no-target refusal. Test: test_a_flat_plan_journal_step_without_lenses_is_not_a_feature_review.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-13T00:39:53+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: fr-goal skill says the last review-phase resolve opens deliver; light list omits lens-review (phase 3)

SKILL.md section 8 names lens-review's resolve as what opens deliver; the light shape's step list includes lens-review; both mirrors re-synced.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-13T00:39:53+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: spec 3.C still shows needs: [spec, plan, journal:plan], a cycle (phase 3)

Spec 3.C amended to needs: [spec, plan], with the cycle and the lenses-declares-the-target rule stated.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-11-13T00:39:53+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: five refusals or branches of the lens-review gate had no test (phase 3)

Tests added: an uncomputable set at resolve (done and failed), a review entry older than the step, a named reviewer with no readable return, and `_owed_before` when the superseded run did the lens review.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-11-13T00:39:53+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: the record template shows reviewer: <id>, not the <lens>=<id> map (phase 3)

The template's owed line shows reviewer as "<lens>=<dispatch-id>,<lens>=<dispatch-id>" on a step declaring lenses.

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-11-13T00:39:53+00:00 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: _verify_reviewer inlines the dispatch walk _dispatches_since claims to own (phase 3)

`_verify_reviewer` calls `_dispatches_since`.

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-11-13T00:39:53+00:00 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: a file repeated in examined: inflates the lens's examined count (phase 3)

`parse_review_lens` de-duplicates examined files, keeping order. Test: test_a_file_named_twice_is_examined_once.

<!-- fr:journal kind=discovery scope=plan id=p4-skill-sentence-placement created=2026-11-13T03:20:46+00:00 phase=4 -->
### p4-skill-sentence-placement · discovery · the three capped skills carry the lens sentence inside an existing line, never a new one (phase 4)

fr-brainstorming (119), fr-plan (120) and fr-execute (119) cannot take a paragraph
without passing 120 lines. The sentence is appended to an existing line's end (a bullet
in brainstorming and execute, the Integration line in fr-plan), and fr-goal's section 6
gained one sentence inside its existing paragraph telling the orchestrator to pass the
suggestion sentence to phase reviewers and never lens text. Section 7a already held the
lens-review dispatch, so no new section or renumbering was needed.

<!-- fr:journal kind=discovery scope=plan id=p4-agents-kind-bumped-to-5 created=2026-11-13T03:20:46+00:00 phase=4 -->
### p4-agents-kind-bumped-to-5 · discovery · both agent edits moved the agents kind to 5; a scenario and a test pinned 4 (phase 4)

Followed AGENTS.md's agents procedure (sync-agents-data, current_version 5,
CANONICAL_SHA256 and PINNED_AT_VERSION, rerender_migration(4, 5), `fr migrate artifacts`
for .claude/agents). tests/unit/test_agents_artifact.py and
tests/scenarios/cloud-triage-repo-agents.sh named version 4 literally; both moved to 5
(the scenario only failed in the full suite).

<!-- fr:journal kind=discovery scope=plan id=p4-visual-evidence-tests-flake-in-full-suite created=2026-11-13T03:20:46+00:00 phase=4 -->
### p4-visual-evidence-tests-flake-in-full-suite · discovery · tests/unit/test_run_evidence_visual.py failed one test in two of three full-suite runs, none alone (phase 4)

Runs 2 and 3 each failed a different test in that file (a read stamp the unit's window
did not cover); the file passed alone, repeated, in parallel, and the third full run
was green (15414 passed). Not touched by this phase; looks wall-clock-tight (a transcript
stamp is the cursor stamp plus 2.5 s, so a resolve faster than that falls outside the
window). Worth its own issue.

<!-- fr:journal kind=discovery scope=plan id=p4-pr-section-uses-live-set created=2026-11-13T03:20:46+00:00 phase=4 -->
### p4-pr-section-uses-live-set · discovery · the PR table's rows come from the live lens set, the counts from the lenses evidence (phase 4)

`_review_lenses` recomputes `lens_set` (so why and the config-change line read the
branch as it stands) and takes only the per-lens file count from the lens-review unit's
`lenses` evidence; an unresolved or unreadable count reads "not observable". A run with
no `lens-review` step on its cursor renders "This run predates review lenses.".

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t2 created=2026-11-13T03:20:46+00:00 phase=4 -->
### no-refactor-p4-t2 · discovery · no-refactor-because P4.T2 (phase 4)

prose and generated mirrors only; each sentence is one appended clause, nothing to restructure

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t3 created=2026-11-13T03:20:46+00:00 phase=4 -->
### no-refactor-p4-t3 · discovery · no-refactor-because P4.T3 (phase 4)

a new page plus two stamp and link edits; nothing to restructure

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t4 created=2026-11-13T03:20:46+00:00 phase=4 -->
### no-refactor-p4-t4 · discovery · no-refactor-because P4.T4 (phase 4)

a scenario script, a registration and a status move; nothing to restructure

<!-- fr:journal kind=review scope=plan id=review-p4 created=2026-11-13T03:25:05+00:00 phase=4 -->
### review-p4 · review · Phase 4 review: agents bump, mirrors, guide and skill text sound; the PR section misreported two cases, fixed (phase 4)

A separate reviewer read the phase's diff against spec R12 and R14. Sound: every
step of the agents 4->5 procedure, the three mirror checks, `fr docs check`, the
guide against the code, the empty-set sentence, the LensError path. Four findings
(three in scope, one out), all fixed.

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-11-13T03:25:05+00:00 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · lens table cells are not escaped: a pipe in a reason breaks the table (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-11-13T03:25:05+00:00 phase=4 state=open review_scope=in -->
### p4-r2 · finding [open] (reviewer: in scope) · a lens review that has not run, or a lens added after it, renders as not observable (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r3 created=2026-11-13T03:25:05+00:00 phase=4 state=open review_scope=in -->
### p4-r3 · finding [open] (reviewer: in scope) · lens sentences appended onto unrelated bullets in three skills; two suggestion formats (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r4 created=2026-11-13T03:25:05+00:00 phase=4 state=open review_scope=out -->
### p4-r4 · finding [open] (reviewer: out of scope) · lens_set's warnings (a disabled journalled lens, no remote) are not shown in the PR section (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-11-13T03:25:05+00:00 phase=4 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: lens table cells are not escaped: a pipe in a reason breaks the table (phase 4)

`_cell` escapes a pipe and folds whitespace in every cell of the lens table. Tests: test_a_pipe_in_a_reason_stays_inside_its_cell, test_a_cell_is_one_line.

<!-- fr:journal kind=finding scope=plan id=p4-r2-resolved created=2026-11-13T03:25:05+00:00 phase=4 state=fixed resolves=p4-r2 -->
### p4-r2-resolved · finding [fixed] · resolves p4-r2: a lens review that has not run, or a lens added after it, renders as not observable (phase 4)

`_lens_examined`: "not reviewed yet" (with a line under the table) while lens-review is not done, "not reviewed" for a lens absent from the evidence, "not observable" only for `unobserved`. Two tests.

<!-- fr:journal kind=finding scope=plan id=p4-r3-resolved created=2026-11-13T03:25:05+00:00 phase=4 state=fixed resolves=p4-r3 -->
### p4-r3-resolved · finding [fixed] · resolves p4-r3: lens sentences appended onto unrelated bullets in three skills; two suggestion formats (phase 4)

The sentence is its own bullet in fr-brainstorming, fr-execute and fr-plan (all at the 120-line cap); fr-goal's phase-reviewer suggestion uses the spec reviewer's `suggested lenses:` format. Mirrors re-synced.

<!-- fr:journal kind=finding scope=plan id=p4-r4-resolved created=2026-11-13T03:25:05+00:00 phase=4 state=fixed resolves=p4-r4 -->
### p4-r4-resolved · finding [fixed] · resolves p4-r4: lens_set's warnings (a disabled journalled lens, no remote) are not shown in the PR section (phase 4)

Cheap and in the same function, so fixed here: each `lens_set` warning is printed as a `Note:` line under the section, including under the empty-set sentence. Test: test_a_lens_the_repo_disabled_is_named_under_the_section.

<!-- fr:journal kind=lens scope=plan id=lens-security-1 created=2026-11-13T03:29:27+00:00 lens=security -->
### lens-security-1 · lens · the feature adds an evidence gate and reads repo-controlled YAML and reviewer returns: look for a way a resolve passes unreviewed

<!-- fr:journal kind=lens scope=plan id=lens-errors-1 created=2026-11-13T03:29:31+00:00 lens=errors -->
### lens-errors-1 · lens · every unreadable input (lens config, default ref, session transcript) must refuse or be noted, never read as an empty set
