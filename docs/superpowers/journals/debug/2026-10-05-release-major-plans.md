# Journal: 2026-10-05-release-major-plans

<!-- fr:journal kind=repro scope=debug id=ce4c7a3181dd created=2026-10-05T20:39:20+00:00 -->
### ce4c7a3181dd · repro · A major release leaves this repo's live plans stale; install.sh's fr models apply is refused

From super-fr#861: a scratch clone bumped to 6.0.0 (bump + consumed fragment, committed) fails 2 of test_install_opencode_agents.py under release._run_staged_tests; both pass at the pre-bump commit. Static: the one live plan, docs/superpowers/plans/2026-07-09-multi-backend-git-host-adapters/_meta.yaml, carries fr_version '>=3.12.0,<6.0.0', which does not admit 6.0.0, so the CLI-entry migration gate refuses the non-interactive 'fr models apply' behind install.sh's '|| true'.
