# Journal: 2026-10-02-release-confidence

<!-- fr:journal kind=repro scope=debug id=36d3b8f56a65 created=2026-10-02T16:40:54+00:00 -->
### 36d3b8f56a65 · repro · Batch release-confidence (#854, #855, #681): three version-confidence gaps reproduced

- #854: release.py stages the bump, verifies only WHICH lines changed (verify_staged), commits and pushes with GITHUB_TOKEN; no test ever runs at the new number before push. 5.0.0 shipped ~415 red.
- #855.1: in a scratch repo on fr 5.0.1, `fr plan create --slug toy --fr-version '>=4.20.0,<5.0.0'` fails create's own re-parse AFTER writing; leaves plans/toy/, journals/plans/toy.md and the validator wrapper staged, uncommitted.
- #855.2: `Version('5.0.1.dev0') in SpecifierSet('>=4,<6')` is False on packaging 25.0 and True on 26.0 (the lock). fr declares packaging>=24, so the result depends on whichever packaging the install resolved. Sites: parser._installed_has_outgrown, parser._enforce_fr_version, artifacts.fr_version.widen_ceiling (x3).
- #681: version_surfaces accepts only a literal `[project]` header; check-change-fragment.py usage line invokes system python3.

<!-- fr:journal kind=root-cause scope=debug id=b280ddfd52c4 created=2026-10-02T16:40:55+00:00 -->
### b280ddfd52c4 · root-cause · Version-dependent behaviour is checked against a version other than the one that will run it

One class, three sites: the release checks the diff, not the code running at the bumped number (#854); plan create checks an explicit fr_version only against OLDER fr, never the installed one, and only after writing (#855.1); membership tests leave pre-release handling to the library default, which moved between packaging 25 and 26 (#855.2). #681 is the batch's chore lane (release-script hygiene), not this cause; the brief batched it knowingly.

<!-- fr:journal kind=ruled-out scope=debug id=f31ec21494d1 created=2026-10-02T16:46:33+00:00 -->
### f31ec21494d1 · ruled-out · A curated version-sensitive test subset for the release job

The issue offered 'the suite, or a fast subset'. Rejected: a hand-picked subset is a literal list that goes stale as the code moves, the exact class of the <5.0.0 ceiling. The full suite costs ~10 min per release (4 CI shards x 2-3 min); release.yml gets budget_seconds: 900 in .github/ci-budget.yaml instead.

<!-- fr:journal kind=finding scope=debug id=release-confidence-fix created=2026-10-02T16:46:34+00:00 state=fixed -->
### release-confidence-fix · finding [fixed] · Staged-tree suite before push; create pre-flight; one pre-release-aware membership test; [project] spellings

- #854: release.py Commands.test = _run_staged_tests: probes importlib.metadata.version('fr') == new under uv run --locked, then the whole suite; check_staged_suite raises before push() (commit still local, main/tags untouched). Pinned by test_release_script.py (red path, ordering, no-release no-op, race retest, default runner) and test_release_workflow.py (header, budget).
- #855.1: plan_ops._preflight_fr_version_error refuses before any write; pinned by test_an_explicit_constraint_excluding_the_installed_fr_writes_nothing (tree + git status unchanged).
- #855.2: fr.version_floor.admits (prereleases=True) at all five parser/widen_ceiling sites; pinned under an emulated packaging-25 default plus a src tripwire against bare membership tests.
- #681: _PROJECT_HEADER_RE allows inner whitespace; _DOTTED_VERSION_RE rewrites root-table project.version; usage lines read 'uv run --no-project python'.

<!-- fr:journal kind=finding scope=debug id=major-release-stale-own-plans created=2026-10-02T17:06:20+00:00 state=open -->
### major-release-stale-own-plans · finding [open] · Simulated 6.0.0 release: the new gate refuses it (2 red); the repo's own live plans go stale at a major

Ran the real _run_staged_tests on a scratch clone bumped to 6.0.0: probe reported 6.0.0, 7607 passed, 2 failed in test_install_opencode_agents.py. Both pass at the clone's pre-bump commit. Cause: live plans carry <6.0.0, the migration gate refuses install.sh's 'fr models apply' (cwd = repo), '|| true' hides it. A separate root cause from this batch, so not fixed here; filed as super-fr#861. The tree stayed clean after the full suite (git status empty), which settles the review's retry/untracked-files question.
