# Journal: 2026-09-29-derive-fr-version-ceiling

<!-- fr:journal kind=repro scope=debug id=5eb1dfd320dc created=2026-09-29T19:44:38+00:00 -->
### 5eb1dfd320dc · repro · 5.0.0 refuses the plans it writes: 414 failed + 8 errors

On the merged tree at 5.0.0 (61922adb), `uv run pytest -q --no-cov -n auto` gives 414 failed, 8 errors. New plans get `fr_version: >=3.0.0,<5.0.0`; parse raises PlanSchemaError "requires fr_version >=3.0.0,<5.0.0 but installed is 5.0.0". The repo own plan 2026-07-09-multi-backend-git-host-adapters is stranded the same way (fixed by `fr migrate artifacts --yes`).

<!-- fr:journal kind=ruled-out scope=debug id=5924fd26c61e created=2026-09-29T19:44:40+00:00 -->
### 5924fd26c61e · ruled-out · Parser gate is wrong

parser._enforce_fr_version compares INSTALLED_FR_VERSION (package metadata) against the declared spec. It is correct; refusing a plan whose ceiling excludes the installed major is its job.
