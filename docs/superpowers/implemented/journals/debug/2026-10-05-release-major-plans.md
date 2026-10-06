# Journal: 2026-10-05-release-major-plans

<!-- fr:journal kind=repro scope=debug id=ce4c7a3181dd created=2026-10-05T20:39:20+00:00 -->
### ce4c7a3181dd · repro · A major release leaves this repo's live plans stale; install.sh's fr models apply is refused

From super-fr#861: a scratch clone bumped to 6.0.0 (bump + consumed fragment, committed) fails 2 of test_install_opencode_agents.py under release._run_staged_tests; both pass at the pre-bump commit. Static: the one live plan, docs/superpowers/plans/2026-07-09-multi-backend-git-host-adapters/_meta.yaml, carries fr_version '>=3.12.0,<6.0.0', which does not admit 6.0.0, so the CLI-entry migration gate refuses the non-interactive 'fr models apply' behind install.sh's '|| true'.

<!-- fr:journal kind=root-cause scope=debug id=ebfd094ccb5f created=2026-10-05T20:39:24+00:00 -->
### ebfd094ccb5f · root-cause · The release commit can carry only version lines, so nothing widens the live plans' derived ceiling at a major

release.py's make_release_commit runs bump-version.py, git rm's fragments and verify_staged allows nothing but version_surfaces lines. A plan's fr_version ceiling is <(major+1).0.0 (version_floor.ceiling_for), so a major bump moves the installed fr past every live plan's ceiling, and the widen-fr-version-ceiling repair (fr migrate artifacts) is never run on the release tree. The first commit at the new major therefore has stale artifacts; the #858 pre-push suite catches it via install.sh's gated 'fr models apply'.

<!-- fr:journal kind=ruled-out scope=debug id=d1181a64e79b created=2026-10-05T20:39:26+00:00 -->
### d1181a64e79b · ruled-out · Exempting 'fr models apply' from the migration gate

Issue #861 question 2. Rejected as THE fix: it silences the one symptom the suite saw while every live plan still refuses to parse at the new major (dispatch, fr plan, the gate for every other command). The stale artifacts are the cause; the exemption would be a separate argument to the pinned READ_ONLY_COMMANDS list, not this batch's.

<!-- fr:journal kind=ruled-out scope=debug id=20865383cd50 created=2026-10-05T20:39:29+00:00 -->
### 20865383cd50 · ruled-out · Widening in a PR before the major

Issue #861 option 1. A pre-major PR cannot write <N+2.0.0: the ceiling is derived from the installed fr, and an fr at N cannot widen past N+1. It would also need a human to remember before every major; the release is the only actor that knows the number.

<!-- fr:journal kind=finding scope=debug id=release-major-plans-fix created=2026-10-05T20:53:51+00:00 state=fixed -->
### release-major-plans-fix · finding [fixed] · The release migrates artifacts at the new number; verify_staged admits exactly a widened live-plan ceiling

- scripts/release.py: Commands.migrate = _run_migrate ('uv run --locked fr migrate artifacts --yes', after bump-version.py, before git add -A); a failure raises ReleaseError before any commit. verify_staged admits docs/superpowers/plans/<slug>/_meta.yaml (M) only when its single changed line is fr_version with the same key/quoting/floor and every '<'/'<=' bound replaced by '<{new major+1}.0.0' (_plan_ceiling_widened).
- Failing test first (4eee453ea): test_release_script.py - major widens the live plan, minor is a no-op, failed migrate refuses, a floor / wrong-ceiling / other-line plan edit refuses, an archived plan edit refuses, and the default command's argv/failure tail.
- Live proof on a scratch clone: the real make_release_commit at 6.0.0 (real bump-version.py + fr migrate) committed the plan at '>=3.12.0,<7.0.0' and verify_staged accepted it. test_install_opencode_agents.py: 9 passed; reverting only the plan's ceiling reproduced #861's 2 failures. Full suite at 6.0.0: 8466 passed, 105 skipped. fr validate artifacts: 12 checked, all valid.

<!-- fr:journal kind=review scope=debug id=3f0267243d2a created=2026-10-05T20:57:55+00:00 -->
### 3f0267243d2a · review · Independent review: no blocking issues; two allowlist fixes and a test gap, all fixed

Low-medium: _plan_ceiling_widened compared raw text against the repair's PEP 440-normalised specifiers, so '>= 4.20' would have been refused (fail-closed). Fixed: pieces compared whitespace-free. Low: a narrowing ceiling (<9 -> <6) was admitted. Fixed: every old ceiling's major must be below the new one. Test gap: the fake migrate never exercised the real repair's output. Fixed: a parametrized test runs fr.artifacts.fr_version.widen (quotes, spacing, <=, !=) and feeds its lines to the allowlist; negatives cover narrowing, trail, added ceiling, quoting, other key, two lines, added/deleted plan files. Not acted on: the shared ---/+++ header filter (pre-existing idiom, unreachable by the migration); 'any migrate failure blocks every release' is fail-closed by design and named in the refusal. Re-simulated the real 6.0.0 release commit after the fixes: plan at '>=3.12.0,<7.0.0', accepted.
