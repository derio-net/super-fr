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
