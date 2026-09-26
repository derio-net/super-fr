# Journal: 2026-09-26-version-bump-churn

<!-- fr:journal kind=decision scope=plan id=plan-phase-shape created=2026-09-26T08:15:24 -->
### plan-phase-shape · decision · Six phases - skeleton surface list, PR gate, release workflow, acceptance, docs/config, manual live release

Acceptance (P4) depends only on the skeleton so it is independent of the release machinery.
The live first release is back-loaded as a [manual] phase; the PR ships it unimplemented.
Invariant for every phase: no version value changes (spec §4) - this PR's own gate proves rule 2.

<!-- fr:journal kind=decision scope=plan id=p1-surface-locators created=2026-09-26T08:24:56 phase=1 -->
### p1-surface-locators · decision · Surface locators are project.version, version, plugins[i].version, package[<name>].version (phase 1)

scripts/version_surfaces.py returns frozen Surface(file, locator, value); file is repo-relative POSIX.
uv.lock members are [[package]] blocks whose source has an editable or virtual key (6 here, incl.
super-fr-workspace via editable "."); fr-opencode-plugin is not a uv member, so it has no lock line.
Optional surfaces (marketplace.json, opencode package.json, uv.lock) are skipped when absent so the
module works on tmp repos; the root pyproject is required. write_version rewrites uv.lock textually
per [[package]] block (member version line only) and preserves JSON indent (2 for package.json, 4 else).

<!-- fr:journal kind=discovery scope=plan id=p1-write-version-byte-stable created=2026-09-26T08:24:56 phase=1 -->
### p1-write-version-byte-stable · discovery · write_version is byte-stable at the current version and moves exactly 17 lines on a bump (phase 1)

Checked in a scratch git copy of the tracked manifests + uv.lock: writing 4.23.0 left the tree clean;
writing 9.9.9 changed 11 files / 17 lines (6 uv.lock member lines), no registry package touched.
bump-version.py --check now lists 17 surfaces (was 11) and stays green.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-26T08:24:56 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

tests only; the one cleanup (a tuple-assert ruff flagged F631 and a hand-rolled frozen check) was folded into pytest.raises(FrozenInstanceError) before commit

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-09-26T08:24:56 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

the glob helpers and per-file writers moved wholesale into scripts/version_surfaces.py, so nothing duplicated remained in bump-version.py; the label formatting was collapsed to one regex in P1.T3.S2
