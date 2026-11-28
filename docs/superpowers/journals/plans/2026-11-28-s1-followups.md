<!-- fr:journal-schema=4 -->
# Journal: 2026-11-28-s1-followups

<!-- fr:journal kind=decision scope=plan id=p1-movers-scope created=2026-11-28T10:01:21+00:00 phase=1 -->
### p1-movers-scope · decision · Movers read the old forms through a context scope, fr.config.movers.moving() (phase 1)

The migration reads the quiet placement through `outside_repo` -> `quiet._read`, the
same reader that must refuse an old-only switch past the gate (R4). R3 needs the
migration (and `fr settings init --quiet` creating fr-config from the old switch, whose
`refuse_repo_config` and `fr_message` read the placement too) to keep reading it. A
parameter could not reach those nested readers, so a ContextVar scope does:
`fr.config.movers.moving()` / `@mover`, applied to `plan_migrations`, `is_stale`,
`run_migrations`, `commit_migration`, the CLI-entry `ensure_artifacts_current`, and the
`settings init --quiet` path. Readers ask `transition.refuses_old_read()` (= refusing
and not moving); writers and the old-copy refusals ask `transition.keeps_old_copy()`.
`fr.config.movers` imports nothing of fr's, because `fr.config.transition` needs
`fr.settings` and importing it from `fr.artifacts.runner` closed an import cycle.
`space.old_path(root, kind)` is the mover helper for the plan-config readers in
`fr repos sync` and `fr repair` (plan P1.T2.S2).

<!-- fr:journal kind=discovery scope=plan id=p1-settings-paths-reads-no-config created=2026-11-28T10:01:21+00:00 phase=1 -->
### p1-settings-paths-reads-no-config · discovery · `fr settings paths` reads no configuration file, so it cannot be the exit-2 surface for an old plan-config (phase 1)

Plan P1.T2.S1 asked that `fr settings paths` exit 2 with only the old plan-config
present. `paths_answers` prints `config_kind_path` locations and never calls
`located`; making it refuse would also break `validate-plans.sh`, which falls back to
the repo literals on a paths refusal and is to read `FR_OLD_PATHS_ENDED` from it
(phase 2). The old plan-config's only readers are movers (repos sync, repair, the
migration). The CLI exit-2 test therefore uses a reader command, `fr models resolve`,
over an old `docs/superpowers/models.yaml`; `located(root, "plan-config")` and
`located(root, "profiles")` raising TransitionError are pinned directly.

<!-- fr:journal kind=discovery scope=plan id=p1-init-on-a-complete-new-switch created=2026-11-28T10:01:21+00:00 phase=1 -->
### p1-init-on-a-complete-new-switch · discovery · Past the gate `fr settings init` on a new switch with no old copy refuses as already initialised, not with a half-written refusal (phase 1)

Plan P1.T3.S1 said init --quiet/--stealth on a repo holding the new switch and no old
copy "succeed". Past the gate that repo is fully initialised, so init gives its usual
"origin already has `fr-config`" / "never overwrites" refusal (exit 2) and never the
half-written refusal naming `fr settings sync`; a fresh repo's init succeeds and writes
only the new file. The tests pin that.

<!-- fr:journal kind=discovery scope=plan id=p1-shipped-commands-traceback created=2026-11-28T10:01:21+00:00 phase=1 -->
### p1-shipped-commands-traceback · discovery · `fr workflow check --all` and `fr verification list/check --all` let a resolver error escape as a traceback (phase 1)

The spec assumed each kind's commands already map their error to exit 2. `lenses list`
did; `workflow check --all` (discovery) and `verification list`/`check --all` did not:
a WorkflowError/StrategyError from the shipped-dirs walk exited 1 with a traceback.
Both now print the error and exit 2 (R6).

<!-- fr:journal kind=decision scope=plan id=p1-s1-open-mark created=2026-11-28T10:01:21+00:00 phase=1 -->
### p1-s1-open-mark · decision · An `s1_open` mark pins a module of S1 transition-behaviour tests to the pre-9.2 side (phase 1)

`tests/conftest.py::_s1_transition_side` drops any inherited `FR_OLD_PATHS` from every
test and, for a test marked `s1_open` (registered in pyproject), monkeypatches
`fr.config.transition.refusing` to False; a test that wants the ended side patches it
itself afterwards. Applied to the modules that test the transition itself:
test_config_legacy_paths, test_config_legacy_by_tip, test_migration_config_kinds,
test_placement_quiet, test_settings_quiet, test_settings_stealth, test_config_change_pr,
test_placement_stealth_writes (plus test_shipped_defaults_resolve's own `clean`
fixture). With fr.__version__ forced to 9.2.0 in process (a local -p plugin), those
modules and this phase's new tests pass: 222 passed. The mark cannot reach an `fr`
subprocess.

<!-- fr:journal kind=finding scope=plan id=p1-old-form-fixtures-red-at-9-2 created=2026-11-28T10:01:21+00:00 phase=1 state=open review_scope=in -->
### p1-old-form-fixtures-red-at-9-2 · finding [open] (reviewer: in scope) · About 58 more test modules build fixtures in old forms and turn red once fr is 9.2 (R10) (phase 1)

Run with the gate ended (FR_OLD_PATHS=refuse, before the conftest started dropping it)
over the 111 test files that name an old form, 755 tests failed or errored in 66
files. The eight transition modules above are now pinned; the rest are ordinary tests
whose fixtures happen to use an old form, so they are not transition-behaviour tests
and should move their fixtures to the new forms rather than be pinned: a quiet repo
built from the old switch only (`push_fr_branch` / `_quiet`, ~200 failures:
test_run_cli 237, test_isolation 115, test_run_binding_guard, test_run_workspace,
test_usage_capture, test_placement_quiet_up, test_placement_move*, ...), a repo
workflow at `docs/superpowers/workflows` (58), profiles at
`.devcontainer/fr-profiles.yaml` (25: test_tracking_none, test_services_resolve,
test_init_scaffold, test_migration_profiles_services, ...), `docs/superpowers/models.yaml`
and `verifications`, and the per-kind FR_SHIPPED_*_DIR sites (#1700, already phase 4's
P4 task with its tripwire). No phase of the plan owns the old-form fixture rewrite;
until it lands a release into 9.2 turns these red. Reproduce: a pytest plugin that sets
`fr.__version__ = "9.2.0"`, run with `-p`.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-28T10:01:21+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

the gate is one new module of three small functions and two error classes; nothing pre-existed to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-28T10:01:21+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the change is one early refusal and a constant help line in sync_cmd, plus a regenerated block; nothing to simplify

<!-- fr:journal kind=discovery scope=plan id=p1-fr-ended-option created=2026-11-28T13:09:01+00:00 phase=1 -->
### p1-fr-ended-option · discovery · pytest --fr-ended runs the suite past S1's gate; a test of the old forms is marked s1_open or s1_open_subprocess (phase 1)

tests/conftest.py adds `--fr-ended`: every test not marked `s1_open` runs with `fr.__version__` patched to 9.2.0 and `FR_OLD_PATHS=refuse` in the environment (so an fr subprocess is past the gate too); an `s1_open` test keeps its in-process gate open but gets the same environment, so one that drives an fr subprocess on the open side shows up and is marked `s1_open_subprocess` (skipped once the gate has ended or under --fr-ended). Proof run for review fix p1-old-form-fixtures-red-at-9-2: `uv run pytest tests -q --no-cov -n 6 -p no:randomly --fr-ended` gave 43 failed, 96 errors in 23 files, 19968 passed (1:42:53); those files were fixed and rerun on both sides (with and without --fr-ended) until green. Helpers: tests/unit/test_placement_quiet.push_quiet_switch / quiet_repo_both (both switches in step), tests/unit/config_paths.profiles_file, tests/unit/shipped_env.defaults_root (FR_SHIPPED_DEFAULTS_DIR for a flat per-kind dir). For phase 4: the scenario work can force the ended side the same way (FR_OLD_PATHS=refuse), and the per-kind FR_SHIPPED_*_DIR test sites already moved (only tests/unit/test_shipped_defaults_resolve.py and tests/unit/test_run_evidence_walk.py's literal string still name them), so the R14 tripwire should pass as soon as it lands.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-28T14:22:41+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · fr migrate artifacts reads the old switch before its mover scope opens (phase 1)

`migrate_cmd.py:203` calls `require_migrated_layout` (`common.py:94` -> `quiet._read`) outside
`transition.moving()`, so past the gate a repo whose switch is only the old one is refused and told
to run the command it is running. The other movers (`fr repair`, `fr repos sync`) had the same shape.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-28T14:22:41+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · past the gate the settings-location stamp stays 1, so every command is refused (phase 1)

`config/migrate.py:216-226` stamps the old switch 2 only while its bytes equal the fr-config copy. Past
the gate the old copy is never rewritten, so after the first fr-config change the stamp stays 1,
`_create_space` refuses (`config_migration.py:215-222`) and `trigger.py:757-770` refuses every command.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-28T14:22:41+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · docstrings still promise the old settings copy without 'before fr 9.2' (phase 1)

`space.py:279-282`, `settings_cmd.py:63-66, 122-126, 249-253` and the user-facing
`config_migration.py:231-232` description promise the old copy is kept in step with no qualifier (R4).

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-11-28T14:22:41+00:00 phase=1 -->
### p1-review-1 · review · phase 1 review: three in-scope findings (p1-r1, p1-r2, p1-r3), all fixed (phase 1)

Reviewer ab27c72758b4ecafc (feature-dev:code-reviewer, claude-opus-5-5) reviewed the phase 1 diff
044bc18ee..0ad25840b against R1-R6 and R10. Findings p1-r1, p1-r2, p1-r3, all in scope. It suggested
the errors lens, already on the feature. The open implement-phase finding
p1-old-form-fixtures-red-at-9-2 was fixed in the same round.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-28T14:22:41+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: fr migrate artifacts reads the old switch before its mover scope opens (phase 1)

9f66412c9: `fr migrate artifacts`, `fr repair` and `fr repos sync` open the mover scope at their CLI
entry; `ensure_space` is a mover (421b9b5a6). CliRunner tests on the ended side in
tests/unit/test_config_space_transition.py.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-28T14:22:41+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: past the gate the settings-location stamp stays 1, so every command is refused (phase 1)

421b9b5a6: past the gate `settings_stamp` counts the old switch as current once fr-config holds a
settings file. Test in tests/unit/test_settings_old_copy_transition.py, red with the fix stashed.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-28T14:22:41+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: docstrings still promise the old settings copy without 'before fr 9.2' (phase 1)

421b9b5a6: the docstrings and the settings-location description say "before fr 9.2", with a test.

<!-- fr:journal kind=finding scope=plan id=p1-old-form-fixtures-red-at-9-2-resolved created=2026-11-28T14:22:41+00:00 phase=1 state=fixed resolves=p1-old-form-fixtures-red-at-9-2 -->
### p1-old-form-fixtures-red-at-9-2-resolved · finding [fixed] · resolves p1-old-form-fixtures-red-at-9-2: About 58 more test modules build fixtures in old forms and turn red once fr is 9.2 (R10) (phase 1)

c99c4a13d, 3270370a6, e94edc898: fixtures moved to the new forms, old-form behaviour tests marked
s1_open / s1_open_subprocess, and `pytest --fr-ended` (tests/conftest.py) runs the suite past the gate.
The --fr-ended run found 139 red in 23 files; those files then passed on both sides (discovery
p1-fr-ended-option). CI on 1da6bd65c: all seven test shards green (docs-check red until phase 4).
