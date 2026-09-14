# Journal: 2026-06-15-infisical-secret-provider

<!-- fr:journal kind=discovery scope=plan id=no-refactor-P5.T3 created=2026-09-14T16:37:45 phase=5 -->
### no-refactor-P5.T3 · discovery · no-refactor-because P5.T3 (phase 5)

P5.T3 changes skill prose, regenerated mirrors, matrix rows, version manifests and the full gate run. It adds no production code, so there is nothing to refactor; the code tasks P5.T1 and P5.T2 keep their refactor steps.

<!-- fr:journal kind=finding scope=plan id=june-C1-shell-injection created=2026-09-14T16:40:11 phase=4 state=fixed -->
### june-C1-shell-injection · finding [fixed] · C1 (critical): exec_wrap interpolated project_id/env/path into sh -lc unquoted (phase 4)

fr-profiles.yaml is PR-reachable. Fixed in 92a3d8a with shlex.quote on all three values plus a metacharacter-path test; survived the 4.x rebase (secrets.py).

<!-- fr:journal kind=finding scope=plan id=june-C2-token-lingers created=2026-09-14T16:40:12 phase=4 state=open -->
### june-C2-token-lingers · finding [open] · C2 (critical): the minted token lingered in the token-file until down (phase 4)

Fix in 92a3d8a had two halves: SecretProvider.post_exec (survived, secrets.py) and the Target wrapping exec in try/finally to call it (dropped — lived in local.py, which the rebase took from main). Re-implemented by P5.T1.S2; verified by test_exec_clears_token_after_run / _on_abort.

<!-- fr:journal kind=finding scope=plan id=june-I1-defensive-unlink created=2026-09-14T16:40:14 phase=4 state=open -->
### june-I1-defensive-unlink · finding [open] · I1: down must clear the token even when the worktree profile config is unreadable (phase 4)

provider_for falls back to env-file on an unreadable config, so provider cleanup would be skipped. The 92a3d8a defensive unlink lived in local.py and was dropped by the rebase. With per-exec files (P5.T2) it becomes: the devcontainer _teardown_container removes host_token_dir(repo, profile) unconditionally.

<!-- fr:journal kind=finding scope=plan id=june-I2-no-remote-env created=2026-09-14T16:40:15 phase=4 state=open -->
### june-I2-no-remote-env · finding [open] · I2: an infisical exec must add no --remote-env (argv-visible on the host) (phase 4)

test_exec_secret_uses_no_remote_env is carried but red until the wiring returns in P5.T1.S2.

<!-- fr:journal kind=finding scope=plan id=june-I3-install-stderr created=2026-09-14T16:40:16 phase=4 state=fixed -->
### june-I3-install-stderr · finding [fixed] · I3: the Infisical CLI install swallowed stderr (phase 4)

Fixed in 92a3d8a (INFISICAL_INSTALL keeps stderr); survived the rebase (scaffold.py).

<!-- fr:journal kind=finding scope=plan id=june-M1-mint-error-stdout created=2026-09-14T16:40:17 phase=4 state=fixed -->
### june-M1-mint-error-stdout · finding [fixed] · M1: a mint failure could echo stdout, which holds the token (phase 4)

Fixed in 92a3d8a (error surfaces stderr only); survived the rebase (secrets.py _subprocess_mint).

<!-- fr:journal kind=discovery scope=plan id=p5-down-verifies-worktree-removal created=2026-09-14T16:49:19 phase=5 -->
### p5-down-verifies-worktree-removal · discovery · 4.x down verifies git worktree remove, so the carried bare-dir down fixture raises after cleanup ran (phase 5)

The Phase 3 test_down_runs_provider_cleanup built IsolationState over a plain tmp directory (no git). In 4.x _down_worktree_tail raises IsolationError when git worktree remove fails and the path still exists, so the test failed even though provider.cleanup had already run. Rewrote it as test_up_and_down_run_provider_up_prepare_and_cleanup over a real repo + worktree (make_repo + up via FakeRunner), which also proves up_prepare fires at up. Any fixture that reaches down in 4.x needs a real linked worktree.
