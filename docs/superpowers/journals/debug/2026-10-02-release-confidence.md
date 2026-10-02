# Journal: 2026-10-02-release-confidence

<!-- fr:journal kind=repro scope=debug id=36d3b8f56a65 created=2026-10-02T16:40:54+00:00 -->
### 36d3b8f56a65 · repro · Batch release-confidence (#854, #855, #681): three version-confidence gaps reproduced

- #854: release.py stages the bump, verifies only WHICH lines changed (verify_staged), commits and pushes with GITHUB_TOKEN; no test ever runs at the new number before push. 5.0.0 shipped ~415 red.
- #855.1: in a scratch repo on fr 5.0.1, `fr plan create --slug toy --fr-version '>=4.20.0,<5.0.0'` fails create's own re-parse AFTER writing; leaves plans/toy/, journals/plans/toy.md and the validator wrapper staged, uncommitted.
- #855.2: `Version('5.0.1.dev0') in SpecifierSet('>=4,<6')` is False on packaging 25.0 and True on 26.0 (the lock). fr declares packaging>=24, so the result depends on whichever packaging the install resolved. Sites: parser._installed_has_outgrown, parser._enforce_fr_version, artifacts.fr_version.widen_ceiling (x3).
- #681: version_surfaces accepts only a literal `[project]` header; check-change-fragment.py usage line invokes system python3.
