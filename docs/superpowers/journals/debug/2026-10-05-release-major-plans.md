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
