# Journal: 2026-09-29-derive-fr-version-ceiling

<!-- fr:journal kind=repro scope=debug id=5eb1dfd320dc created=2026-09-29T19:44:38+00:00 -->
### 5eb1dfd320dc · repro · 5.0.0 refuses the plans it writes: 414 failed + 8 errors

On the merged tree at 5.0.0 (61922adb), `uv run pytest -q --no-cov -n auto` gives 414 failed, 8 errors. New plans get `fr_version: >=3.0.0,<5.0.0`; parse raises PlanSchemaError "requires fr_version >=3.0.0,<5.0.0 but installed is 5.0.0". The repo own plan 2026-07-09-multi-backend-git-host-adapters is stranded the same way (fixed by `fr migrate artifacts --yes`).

<!-- fr:journal kind=ruled-out scope=debug id=5924fd26c61e created=2026-09-29T19:44:40+00:00 -->
### 5924fd26c61e · ruled-out · Parser gate is wrong

parser._enforce_fr_version compares INSTALLED_FR_VERSION (package metadata) against the declared spec. It is correct; refusing a plan whose ceiling excludes the installed major is its job.

<!-- fr:journal kind=root-cause scope=debug id=5de7704c6e9b created=2026-09-29T19:44:42+00:00 -->
### 5de7704c6e9b · root-cause · New-plan ceiling is a literal, not derived from the installed major

The `<5.0.0` ceiling was set as a literal in 4.0.0 (#442) and repeated in plan_cmd.py (DEFAULT/WORKFLOW/SCOPE_FR_VERSION), migrate.py:282, plan_ops.py:813 and three self-review hints. Nothing recomputes it when the major moves. artifacts/fr_version.widen_ceiling already derives `<{major+1}.0.0` for EXISTING plans, so the formula exists twice. Constraint on the fix: scripts/floors.py FLOOR_RE finds `>=X,<Y` in string literals to check floors name the predicted release; f-string constants would hide SCOPE_FR_VERSION floors from check-change-fragment and release.py.

<!-- fr:journal kind=finding scope=debug id=fix-derived-ceiling created=2026-09-29T20:23:33+00:00 state=fixed -->
### fix-derived-ceiling · finding [fixed] · Derive the ceiling once; parse error never advises a downgrade

fr.version_floor.ceiling_for/CEILING_VERSION are the one derivation, used by DEFAULT/WORKFLOW/SCOPE_FR_VERSION, migrate, split plans, five self-review hints (one said <4.0.0) and widen_ceiling. parser._installed_has_outgrown routes a stale plan to `fr migrate artifacts --yes`. scripts/floors.py accepts a derived ceiling so floors stay release-checked. Pinned by tests/unit/test_fr_version_ceiling.py (default, --workflow and files/estimate_lines create paths parse at the installed fr; two tripwires). Commits 644d177b, c2780cda.

<!-- fr:journal kind=finding scope=debug id=review-gt-bound created=2026-09-29T20:23:35+00:00 state=fixed -->
### review-gt-bound · finding [fixed] · Review: '>' bound on the installed version was told to run migrate

>5.0.0 under 5.0.0 got "run fr migrate artifacts --yes", which treats > as a floor and does nothing. Now says upgrade. Test first (RED), fixed in c2780cda.

<!-- fr:journal kind=finding scope=debug id=review-scoped-out created=2026-09-29T20:23:37+00:00 state=open -->
### review-scoped-out · finding [open] · Review: explicit --fr-version unchecked; dev installs outside every spec

Pre-existing, not caused by this fix. Tracked in derio-net/super-fr#855.

<!-- fr:journal kind=review scope=debug id=2d827aa899f2 created=2026-09-29T20:23:54+00:00 -->
### 2d827aa899f2 · review · Independent adversarial review: no blockers; 1 minor fixed, 2 minors deferred (#855), 1 nit fixed

A separate read-only reviewer attacked the floors.py regex (3.11 vs 3.12 tokenization, fallback path, Counter keying), _installed_has_outgrown, import-time CEILING_VERSION, remaining literals, create/migrate contract and test strength. Raised: MINOR-1 (> bound on installed, fixed), MINOR-2 (dev installs, deferred #855), MINOR-3 (explicit --fr-version unchecked, deferred #855), NIT-1 (tripwire blind to shortened <5, fixed with a raw-text scan). Points 1,3,4,5 held. Full suite after fixes: 7571 passed, 0 failed.

<!-- fr:journal kind=finding scope=debug id=review-scoped-out-resolved created=2026-09-29T20:24:11+00:00 state=open resolves=review-scoped-out tracked_by=derio-net/super-fr#855 -->
### review-scoped-out-resolved · finding [deferred → derio-net/super-fr#855] · resolves review-scoped-out: Review: explicit --fr-version unchecked; dev installs outside every spec

Pre-existing gaps, not caused by this fix.
