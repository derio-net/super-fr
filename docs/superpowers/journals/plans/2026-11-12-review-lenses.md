<!-- fr:journal-schema=3 -->
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
