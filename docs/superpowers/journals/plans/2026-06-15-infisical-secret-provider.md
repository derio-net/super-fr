# Journal: 2026-06-15-infisical-secret-provider

<!-- fr:journal kind=discovery scope=plan id=no-refactor-P5.T3 created=2026-09-14T16:37:45 phase=5 -->
### no-refactor-P5.T3 · discovery · no-refactor-because P5.T3 (phase 5)

P5.T3 changes skill prose, regenerated mirrors, matrix rows, version manifests and the full gate run. It adds no production code, so there is nothing to refactor; the code tasks P5.T1 and P5.T2 keep their refactor steps.

<!-- fr:journal kind=finding scope=plan id=june-C1-shell-injection created=2026-09-14T16:40:11 phase=4 state=fixed -->
### june-C1-shell-injection · finding [fixed] · C1 (critical): exec_wrap interpolated project_id/env/path into sh -lc unquoted (phase 4)

fr-profiles.yaml is PR-reachable. Fixed in 92a3d8a with shlex.quote on all three values plus a metacharacter-path test; survived the 4.x rebase (secrets.py).

<!-- fr:journal kind=finding scope=plan id=june-C2-token-lingers created=2026-09-14T16:40:12 phase=4 state=fixed -->
### june-C2-token-lingers · finding [fixed] · C2 (critical): the minted token lingered in the token-file until down (phase 4)

Fix in 92a3d8a had two halves: SecretProvider.post_exec (survived, secrets.py) and the Target wrapping exec in try/finally to call it (dropped — lived in local.py, which the rebase took from main). Re-implemented by P5.T1.S2; verified by test_exec_clears_token_after_run / _on_abort. Fixed in phase 5 (272c00a + b397a96): `LocalWorktreeDevcontainerTarget.exec` runs the devcontainer exec inside `try/finally: provider.post_exec(ctx)`, and with per-exec files post_exec unlinks the token — proven by tests/unit/test_secrets_wiring.py::test_exec_clears_token_after_run and ::test_exec_clears_token_on_abort (the token dir holds exactly one file during the run and is empty after, on return and on abort).

<!-- fr:journal kind=finding scope=plan id=june-I1-defensive-unlink created=2026-09-14T16:40:14 phase=4 state=fixed -->
### june-I1-defensive-unlink · finding [fixed] · I1: down must clear the token even when the worktree profile config is unreadable (phase 4)

provider_for falls back to env-file on an unreadable config, so provider cleanup would be skipped. The 92a3d8a defensive unlink lived in local.py and was dropped by the rebase. With per-exec files (P5.T2) it becomes: the devcontainer _teardown_container removes host_token_dir(repo, profile) unconditionally. Fixed in phase 5 (b397a96): `_teardown_container` → `_cleanup_secrets` calls `remove_token_dir(host_token_dir(repo, profile))` after the best-effort, never-blocking provider cleanup — proven by tests/unit/test_secrets_wiring.py::test_down_removes_token_dir_even_when_profile_config_is_unreadable[missing|corrupt], which uses the real provider_for.

<!-- fr:journal kind=finding scope=plan id=june-I2-no-remote-env created=2026-09-14T16:40:15 phase=4 state=fixed -->
### june-I2-no-remote-env · finding [fixed] · I2: an infisical exec must add no --remote-env (argv-visible on the host) (phase 4)

test_exec_secret_uses_no_remote_env is carried but red until the wiring returns in P5.T1.S2. Fixed in phase 5 (272c00a): `exec` emits `--remote-env` only for `wrap.exec_env`, which is empty for the infisical wrap (the token rides the bind-mounted per-exec file) — proven by tests/unit/test_secrets_wiring.py::test_exec_secret_uses_no_remote_env and ::test_exec_with_secret_prefixes_infisical_run_and_hides_token.

<!-- fr:journal kind=finding scope=plan id=june-I3-install-stderr created=2026-09-14T16:40:16 phase=4 state=fixed -->
### june-I3-install-stderr · finding [fixed] · I3: the Infisical CLI install swallowed stderr (phase 4)

Fixed in 92a3d8a (INFISICAL_INSTALL keeps stderr); survived the rebase (scaffold.py).

<!-- fr:journal kind=finding scope=plan id=june-M1-mint-error-stdout created=2026-09-14T16:40:17 phase=4 state=fixed -->
### june-M1-mint-error-stdout · finding [fixed] · M1: a mint failure could echo stdout, which holds the token (phase 4)

Fixed in 92a3d8a (error surfaces stderr only); survived the rebase (secrets.py _subprocess_mint).

<!-- fr:journal kind=discovery scope=plan id=p5-down-verifies-worktree-removal created=2026-09-14T16:49:19 phase=5 -->
### p5-down-verifies-worktree-removal · discovery · 4.x down verifies git worktree remove, so the carried bare-dir down fixture raises after cleanup ran (phase 5)

The Phase 3 test_down_runs_provider_cleanup built IsolationState over a plain tmp directory (no git). In 4.x _down_worktree_tail raises IsolationError when git worktree remove fails and the path still exists, so the test failed even though provider.cleanup had already run. Rewrote it as test_up_and_down_run_provider_up_prepare_and_cleanup over a real repo + worktree (make_repo + up via FakeRunner), which also proves up_prepare fires at up. Any fixture that reaches down in 4.x needs a real linked worktree.

<!-- fr:journal kind=finding scope=plan id=review-p5-I1 created=2026-09-14T17:41:01 phase=5 state=fixed -->
### review-p5-I1 · finding [fixed] · I1: token dir was shared by every workspace of one (repo, profile) (phase 5)

host_token_dir(repo, profile) was one directory for all worktrees on a profile, so down or a gc merged-reap of workspace A removed workspace B in-flight tokens and the directory B live container bind-mounts. Fix: the scaffold mounts ${localEnv:HOME}/.cache/fr/run-tokens/<repo>/<profile>/${localWorkspaceFolderBasename} -> /run/fr-secrets and every code path uses a per-workspace dir (canonical_token_dir(repo, profile, worktree) as the fallback spelling); cleanup removes only that workspace subdir. Proven by tests/unit/test_secrets_wiring.py::test_down_of_one_workspace_leaves_sibling_workspace_tokens and tests/unit/test_scaffold_infisical.py::test_scaffold_infisical_profile (mount shape).

<!-- fr:journal kind=finding scope=plan id=review-p5-I2 created=2026-09-14T17:41:05 phase=5 state=fixed -->
### review-p5-I2 · finding [fixed] · I2: host token dir must follow the committed mount, not be recomputed (phase 5)

The scaffold bakes repo_root.name into the mount while the runtime used the main-checkout basename; a differently named clone or a scaffold from a linked worktree made devcontainer up fail on a missing bind source or put tokens where the container never looked. Fix: secrets.token_mount_source/resolve_token_dir parse the --mount entry (both --mount SPEC and --mount=SPEC) whose target is /run/fr-secrets, substitute ${localEnv:*}, ${localWorkspaceFolderBasename} and ${localWorkspaceFolder}, and up_prepare/exec_wrap/cleanup plus the devcontainer _cleanup_secrets use that dir; a missing mount raises an actionable IsolationError at up/exec; an unreadable config falls back to the canonical per-workspace layout so the june-I1 guarantee holds. Proven by tests/unit/test_secrets_infisical.py::test_resolve_token_dir_follows_mount_and_substitutes_variables[separate|equals], ::test_resolve_token_dir_missing_mount_is_actionable, ::test_exec_wrap_missing_mount_raises_before_mint, ::test_up_prepare_missing_mount_raises, ::test_cleanup_falls_back_to_canonical_dir_when_mount_unreadable, tests/unit/test_secrets_wiring.py::test_up_prepare_follows_the_committed_mount_not_the_runtime_repo_name, ::test_down_removes_token_dir_even_when_profile_config_is_unreadable[missing|corrupt], tests/unit/test_scaffold_infisical.py::test_scaffold_from_differently_named_clone_round_trips_through_the_mount.

<!-- fr:journal kind=finding scope=plan id=review-p5-I3 created=2026-09-14T17:41:08 phase=5 state=fixed -->
### review-p5-I3 · finding [fixed] · I3: a token leaked when exec_wrap raised after minting (phase 5)

exec_wrap minted and wrote the 0600 file before reading ctx.config[infisical][project_id|env|path], so a half-written profile raised KeyError with the token left on disk and a traceback instead of exit 2; local.exec also called exec_wrap outside the try/finally. Fix: validate_infisical_config (block, project_id/env/path, auth mapping, method, universal-auth env names) runs before any mint and raises IsolationError; the mount is resolved before the mint too; exec_wrap moved inside the try so post_exec (idempotent, no-op without a token path) always runs. Proven by tests/unit/test_secrets_infisical.py::test_exec_wrap_validates_config_before_mint[4 cases] and tests/unit/test_secrets_wiring.py::test_exec_wrap_failure_after_mint_still_runs_post_exec, ::test_exec_secret_with_incomplete_infisical_block_raises_before_mint_and_run.

<!-- fr:journal kind=finding scope=plan id=review-p5-m1 created=2026-09-14T17:41:11 phase=5 state=fixed -->
### review-p5-m1 · finding [fixed] · m1: plain exec must not read fr-profiles.yaml or build a provider (phase 5)

Every exec parsed the profile config and constructed a provider even without --secret, so malformed YAML, profiles: null, a typo in secret_provider or an unknown auth method broke the plain exec that used to work. Fix: with empty keys, exec goes straight to devcontainer exec via _devcontainer_exec. Proven by tests/unit/test_secrets_wiring.py::test_plain_exec_never_reads_the_profile_config[3 cases] using the real provider_for.

<!-- fr:journal kind=finding scope=plan id=review-p5-m2 created=2026-09-14T17:41:14 phase=5 state=fixed -->
### review-p5-m2 · finding [fixed] · m2: token dir was removed before the container teardown was verified (phase 5)

_cleanup_secrets ran first in _teardown_container, so a docker stop/rm that failed verification kept the workspace and its still-running container but had already lost its bind-mount source. Fix: _cleanup_secrets now runs at the end of _teardown_container, after the container is verified gone and before the worktree removal; remove_token_dir is wrapped in the best-effort try the docstring promised. Proven by tests/unit/test_secrets_wiring.py::test_teardown_keeps_token_dir_until_the_container_is_verified_gone.

<!-- fr:journal kind=finding scope=plan id=review-p5-m3 created=2026-09-14T17:41:17 phase=5 state=fixed -->
### review-p5-m3 · finding [fixed] · m3: gc orphan paths skipped token cleanup (phase 5)

_label_reap and _gc_stale_state retired containers and state records but left an aborted exec token dir behind. Fix: _reap_orphan_tokens (best-effort) removes the canonical per-workspace dir when a state record names the profile, else every <repo-cache-name>/*/<worktree-basename> match. Proven by tests/unit/test_secrets_wiring.py::test_gc_stale_state_reap_removes_the_orphan_token_dir and ::test_gc_label_orphan_reap_removes_the_orphan_token_dir.

<!-- fr:journal kind=finding scope=plan id=review-p5-m4 created=2026-09-14T17:41:20 phase=5 state=fixed -->
### review-p5-m4 · finding [fixed] · m4: _subprocess_mint had no timeout and accepted an empty token (phase 5)

Fix: subprocess.run gets timeout=MINT_TIMEOUT_S (60s) mapped to IsolationError, FileNotFoundError (no infisical binary on the host at exec time) maps to IsolationError, and rc 0 with empty stdout raises instead of writing an empty token file. Proven by tests/unit/test_secrets_infisical.py::test_subprocess_mint_missing_binary_is_isolation_error, ::test_subprocess_mint_timeout_is_isolation_error, ::test_subprocess_mint_empty_stdout_is_isolation_error.

<!-- fr:journal kind=finding scope=plan id=review-p5-m5 created=2026-09-14T17:42:11 phase=5 state=fixed -->
### review-p5-m5 · finding [fixed] · m5: the user command inherited INFISICAL_TOKEN from infisical run (phase 5)

infisical run hands its env, token included, to the child, so the agent command could reuse the token for its TTL. Fix: the wrap ends in -- env -u INFISICAL_TOKEN "$@" (same $0/"$@" passthrough). P6.T1.S2 text and spec Test Plan item 6 now also require printenv INFISICAL_TOKEN in a --secret exec to print nothing. Proven by tests/unit/test_secrets_infisical.py::test_exec_wrap_unsets_token_for_the_user_command.

<!-- fr:journal kind=finding scope=plan id=review-p5-m6 created=2026-09-14T17:42:17 phase=5 state=fixed -->
### review-p5-m6 · finding [fixed] · m6: kubernetes-auth wrap still read a never-written file and set INFISICAL_TOKEN empty (phase 5)

With mint_token returning None the script still did INFISICAL_TOKEN="$(cat …)", shadowing the pod auth with an empty value. Fix: when there is no host token the wrap is exec infisical run … -- env -u INFISICAL_TOKEN "$@" with no cat and no assignment, no token dir is required or created. Proven by tests/unit/test_secrets_infisical.py::test_kubernetes_auth_wrap_has_no_token_file_and_no_assignment.

<!-- fr:journal kind=finding scope=plan id=review-p5-m7 created=2026-09-14T17:42:22 phase=5 state=fixed -->
### review-p5-m7 · finding [fixed] · m7: init scaffold accepted any --secret-provider and silently ignored --infisical-* with env-file (phase 5)

Fix: init_cmd.scaffold exits 2 for a --secret-provider outside {env-file, infisical} and exits 2 when any --infisical-project/--infisical-env/--infisical-path is passed with env-file. Proven by tests/unit/test_scaffold_infisical.py::test_scaffold_rejects_unknown_secret_provider and ::test_scaffold_rejects_infisical_flags_with_env_file.

<!-- fr:journal kind=finding scope=plan id=review-p5-m8 created=2026-09-14T17:42:29 phase=5 state=fixed -->
### review-p5-m8 · finding [fixed] · m8: re-scaffolding a profile to infisical left a plaintext host env-file behind silently (phase 5)

Fix: scaffold_profile prints a stderr warning naming ~/.config/fr/secrets/<repo>/<profile>.env when it still exists for an infisical profile, telling the operator to review and delete it; fr never deletes operator secrets. Proven by tests/unit/test_scaffold_infisical.py::test_rescaffold_to_infisical_warns_about_the_leftover_host_env_file.

<!-- fr:journal kind=finding scope=plan id=review-p5-m8-install-pin created=2026-09-14T17:42:36 phase=5 state=refuted -->
### review-p5-m8-install-pin · finding [refuted] · m8 (second half): pin the Infisical CLI install like glab/tea (phase 5)

Refuted for v1. glab and tea ship versioned static binaries with published SHA256 sums, which is what the scaffold pins for them. Infisical CLI for Debian is distributed through an apt repository bootstrapped by artifacts-cli.infisical.com/setup.deb.sh (a Cloudsmith setup script); there is no checksummed static artifact for that bootstrap to pin against, and the .deb itself is verified by the apt repo signing key the script installs, which is the trust anchor. A versioned GitHub release tarball exists but has not been validated on the base image in this branch, so switching blind would trade a known unpinned bootstrap for an unverified install path. Left as a named KNOWN v1 LIMITATION comment above INFISICAL_INSTALL in packages/fr/src/fr/isolation/scaffold.py; revisit when a pinnable, checksummed artifact is confirmed to work in the base image.

<!-- fr:journal kind=finding scope=plan id=review-p5-m9 created=2026-09-14T17:42:43 phase=5 state=fixed -->
### review-p5-m9 · finding [fixed] · m9: stale prose after the per-workspace, per-exec model (phase 5)

Spec section 3 Token conveyance and Flow rewritten to the per-workspace directory mount, per-exec 0600 files, env -u child hardening and kubernetes-auth no-assignment behaviour (pointing at the addendum); secrets.py module docstring no longer says infisical is added in a later phase; _shred renamed _truncate_and_unlink with an honest docstring; the --secret help text now says it injects everything under the profile Infisical path and that KEY is only checked against the declared secrets. Prose-only plus a rename covered by the existing provider tests.

<!-- fr:journal kind=finding scope=plan id=review-p5-m10 created=2026-09-14T17:42:49 phase=5 state=fixed -->
### review-p5-m10 · finding [fixed] · m10: SECRET_NEEDS_DEVCONTAINER lived in hostworktree.py and was imported by external.py (phase 5)

Moved the shared refusal message to isolation/types.py next to IsolationError; hostworktree.py and external.py import it from there. Covered by tests/unit/test_secrets_mode_scope.py (both refusals still name devcontainer mode).
