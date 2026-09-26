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

<!-- fr:journal kind=review scope=plan id=rp1-review created=2026-09-26T08:37:34 phase=1 -->
### rp1-review · review · Independent code review of phase 1: 3 findings (1 HIGH in, 1 MEDIUM in, 1 LOW out) (phase 1)

Dispatched reviewer (separate context, not the implementer) over dff6586e against spec §3.B/§7.9
and plan 01.yaml. Extraction sound; uv.lock rewrite byte-stable; no version value changed.
Raised: silent skip of missing single-instance surfaces (HIGH), tautological glob-derived test
expectations (MEDIUM), table-unaware first-match TOML regex (LOW, pre-existing).

<!-- fr:journal kind=finding scope=plan id=rp1-f1 created=2026-09-26T08:37:34 phase=1 state=open review_scope=in -->
### rp1-f1 · finding [open] (reviewer: in scope) · HIGH: version_surfaces() silently skips a missing marketplace.json / opencode package.json, weakening --check (phase 1)

scripts/version_surfaces.py guarded both with `.exists()`, so a lost manifest dropped out of
--check and write_version and still printed "ok". The old bump-version.py read both unconditionally.

<!-- fr:journal kind=finding scope=plan id=rp1-f2 created=2026-09-26T08:37:34 phase=1 state=open review_scope=in -->
### rp1-f2 · finding [open] (reviewer: in scope) · MEDIUM: tests re-derive expectations with the module's own globs and member predicate (phase 1)

tests/unit/test_version_surfaces.py rebuilt `expected` with the same globs and duplicated
`_is_member`, so a shared bug would pass silently.

<!-- fr:journal kind=finding scope=plan id=rp1-f3 created=2026-09-26T08:37:34 phase=1 state=open review_scope=out -->
### rp1-f3 · finding [open] (reviewer: out of scope) · LOW: write_version's TOML rewrite uses a table-unaware first-match regex (phase 1)

scripts/version_surfaces.py `_TOML_VERSION_RE` matches the first `version =` line in any table.
Identical to the pre-existing bump-version.py VERSION_RE/write_toml, relocated verbatim.

<!-- fr:journal kind=finding scope=plan id=rp1-f1-resolved created=2026-09-26T08:37:34 phase=1 state=fixed resolves=rp1-f1 -->
### rp1-f1-resolved · finding [fixed] · resolves rp1-f1: HIGH: version_surfaces() silently skips a missing marketplace.json / opencode package.json, weakening --check (phase 1)

`_required()` now fails loudly (SystemExit "version surface <path> is missing") for marketplace.json,
the OpenCode package.json and uv.lock; the temp-repo fixture writes them; a parametrized test pins
each missing file failing.

<!-- fr:journal kind=finding scope=plan id=rp1-f2-resolved created=2026-09-26T08:37:34 phase=1 state=fixed resolves=rp1-f2 -->
### rp1-f2-resolved · finding [fixed] · resolves rp1-f2: MEDIUM: tests re-derive expectations with the module's own globs and member predicate (phase 1)

The coverage test and the uv member set are hand-enumerated (11 files; 6 members), with a comment
saying why; the loud-failure and registry-exclusion tests still exercise the real parser.

<!-- fr:journal kind=finding scope=plan id=rp1-f3-resolved created=2026-09-26T08:37:34 phase=1 state=open resolves=rp1-f3 out_of_scope=true -->
### rp1-f3-resolved · finding [out-of-scope] · resolves rp1-f3: LOW: write_version's TOML rewrite uses a table-unaware first-match regex (phase 1)

Not caused by this change: the same regex and count=1 substitution lived in bump-version.py before
phase 1 moved it. Every current pyproject has [project].version before any other table.
