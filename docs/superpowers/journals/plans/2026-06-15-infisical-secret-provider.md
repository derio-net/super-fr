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

<!-- fr:journal kind=finding scope=plan id=verify-p5-V1 created=2026-09-14T18:10:16 phase=5 state=fixed -->
### verify-p5-V1 · finding [fixed] · V1: the resolved token dir had no containment (phase 5)

resolve_token_dir substituted a PR-reachable mount source and remove_token_dir then truncated every top-level file and rmtree-d the result, so source=${localEnv:HOME} would empty every dotfile at down, an unset variable resolved under /, run-tokens/../../.. escaped the root, a secrets/<repo> target emptied the operator env-files, and a symlinked dir truncated the files it pointed at. Fix: contain_token_dir (used by resolve_token_dir, canonical_token_dir and, in depth, remove_token_dir) requires the normalized path to be lexically under ~/.cache/fr/run-tokens, exactly three components deep, with no . / .. / empty component and no symlink in those components (realpath comparison); any leftover ${ after substitution is refused; remove_token_dir refuses symlinked dirs and out-of-root paths as a logged no-op and skips symlinked children. Proven by tests/unit/test_secrets_infisical.py::test_resolve_token_dir_refuses_uncontained_sources[7 sources], ::test_uncontained_source_fails_closed_at_up_exec_and_cleanup, ::test_symlinked_token_dir_is_refused_and_its_target_untouched, ::test_remove_token_dir_refuses_paths_outside_the_root, ::test_remove_token_dir_never_truncates_through_symlinked_children, ::test_canonical_token_dir_is_contained_too, tests/unit/test_secrets_wiring.py::test_down_with_home_as_mount_source_deletes_nothing_in_home; the legit mount keeps working (::test_resolve_token_dir_follows_mount_and_substitutes_variables and the exec/down suites).

<!-- fr:journal kind=finding scope=plan id=verify-p5-V2 created=2026-09-14T18:10:24 phase=5 state=fixed -->
### verify-p5-V2 · finding [fixed] · V2: the gc orphan glob was unguarded (phase 5)

_reap_orphan_tokens built */<basename> from the docker label path; a label of / gave */ (every repo dir on Python 3.11+) and a basename with glob metacharacters matched siblings. Fix: return when the repo or basename component is empty, glob.escape both, and route every match through canonical_token_dir (containment) before remove_token_dir. Proven by tests/unit/test_secrets_wiring.py::test_gc_orphan_token_glob_skips_empty_names and ::test_gc_orphan_token_glob_escapes_metacharacters.

<!-- fr:journal kind=finding scope=plan id=verify-p5-V3 created=2026-09-14T18:10:31 phase=5 state=fixed -->
### verify-p5-V3 · finding [fixed] · V3: label-orphan token reap ran before the container was confirmed gone (phase 5)

Same ordering m2 fixed for down. Fix: _container_present re-queries docker ps --all --filter=id=<cid> (fails closed: a query error reads as present) and _reap_orphan_tokens runs only when the container is absent; otherwise the tokens are left. Proven by tests/unit/test_secrets_wiring.py::test_gc_label_orphan_leaves_tokens_when_the_container_survives (rm fails, dir kept) and ::test_gc_label_orphan_reap_removes_the_orphan_token_dir (absent, dir reaped).

<!-- fr:journal kind=finding scope=plan id=verify-p5-V4 created=2026-09-14T18:10:38 phase=5 state=fixed -->
### verify-p5-V4 · finding [fixed] · V4: kubernetes-auth up no longer created the mount source (phase 5)

up_prepare created the dir only for universal-auth while the scaffold always writes the mount, so devcontainer up failed on a missing bind source for a kubernetes-auth profile. Fix: the (contained) dir is ensured whenever the mount is present, whatever the auth method; universal-auth still requires the mount. Proven by tests/unit/test_secrets_infisical.py::test_up_prepare_creates_the_mount_dir_for_kubernetes_auth_too and ::test_up_prepare_kubernetes_auth_without_a_mount_is_fine.

<!-- fr:journal kind=finding scope=plan id=verify-p5-V5 created=2026-09-14T18:10:44 phase=5 state=fixed -->
### verify-p5-V5 · finding [fixed] · V5: a token write that failed halfway left the partial file behind (phase 5)

_token_path was set after fh.write, so post_exec had nothing to remove. Fix: set immediately after os.open succeeds. Proven by tests/unit/test_secrets_infisical.py::test_partially_written_token_is_removed_by_post_exec (fdopen returns a writer that raises).

<!-- fr:journal kind=finding scope=plan id=verify-p5-V6 created=2026-09-14T18:10:50 phase=5 state=fixed -->
### verify-p5-V6 · finding [fixed] · V6: env -u INFISICAL_TOKEN parsed a NAME=VALUE or -x user command as its own operand (phase 5)

Fix: both scripts end in env -u INFISICAL_TOKEN -- "$@"; shape tests updated. Proven by tests/unit/test_secrets_infisical.py::test_exec_wrap_unsets_token_for_the_user_command and ::test_kubernetes_auth_wrap_has_no_token_file_and_no_assignment.

<!-- fr:journal kind=finding scope=plan id=verify-p5-V7 created=2026-09-14T18:10:59 phase=5 state=fixed -->
### verify-p5-V7 · finding [fixed] · V7: ${localEnv:VAR:default} was not parsed (phase 5)

Implemented rather than refused: _VAR accepts the default form and _substitute uses the default when the variable is unset, matching the devcontainer CLI. Proven by tests/unit/test_secrets_infisical.py::test_resolve_token_dir_supports_localenv_default_values (unset -> default, set -> value).

<!-- fr:journal kind=finding scope=plan id=verify-p5-V8 created=2026-09-14T18:11:05 phase=5 state=fixed -->
### verify-p5-V8 · finding [fixed] · V8: no test proved down follows a non-canonical mount (phase 5)

Added tests/unit/test_secrets_wiring.py::test_down_follows_a_mount_that_differs_from_the_canonical_layout: the committed mount names other-clone, down removes that dir and leaves the canonical-layout sibling keyed on the runtime repo name intact.

<!-- fr:journal kind=decision scope=plan id=verify-p5-limit-shared-basename created=2026-09-14T18:11:15 phase=5 -->
### verify-p5-limit-shared-basename · decision · Known limitation: custom --path workspaces sharing a basename share a token dir (phase 5)

The per-workspace key is the worktree basename, so two workspaces of one repo and profile created with custom --path values that share a basename still share a token dir. Accepted for v1: nothing in the repo passes --path today and the default cache layout (~/.cache/fr/worktrees/<repo>/<branch-slug>) makes basenames unique per repo. Recorded in the spec re-integration addendum under Known limitations.

<!-- fr:journal kind=decision scope=plan id=verify-p5-limit-renamed-clone-gc created=2026-09-14T18:11:20 phase=5 -->
### verify-p5-limit-renamed-clone-gc · decision · Known limitation: the gc fallback does not find orphan token dirs of a renamed clone (phase 5)

When a workspace config is gone the gc fallback keys on the current checkout name, so an orphan token dir left by a clone renamed after scaffolding is not found. Accepted for v1: the dir is normally empty because each exec removes its own file. Recorded in the spec re-integration addendum under Known limitations.

<!-- fr:journal kind=finding scope=plan id=verify2-p5-W1 created=2026-09-14T18:54:34 phase=5 state=fixed -->
### verify2-p5-W1 · finding [fixed] · W1: post_exec truncation followed a symlink or FIFO the container planted (phase 5)

The token-dir bind mount was read-write and the container knows the per-exec file name, so code inside it could swap the file for a symlink to a host file this user can write (authorized_keys, zshrc): is_file() followed the link and write_text emptied the target; a FIFO could block post_exec. Fix, two layers: (1) the scaffold mount ends in ,readonly — token_mount_source already ignores bare options, so a mount without it (nothing merged yet) still parses; (2) _truncate_and_unlink now opens with O_WRONLY|O_TRUNC|O_NOFOLLOW|O_NONBLOCK, closes, swallows OSError (ELOOP, ENXIO, ...) and unlinks the entry itself (unlink wrapped best-effort); remove_token_dir routes every non-symlink, non-dir child through the same call, so no host-side write inside the token dir follows a link. Proven by tests/unit/test_secrets_infisical.py::test_post_exec_never_truncates_through_a_planted_symlink, ::test_post_exec_never_blocks_on_a_planted_fifo (thread-bounded), ::test_remove_token_dir_survives_planted_fifo_and_symlink_children, ::test_resolve_token_dir_accepts_the_readonly_mount_option, tests/unit/test_scaffold_infisical.py::test_scaffold_infisical_profile (mount ends in ,readonly).

<!-- fr:journal kind=finding scope=plan id=verify2-p5-W2 created=2026-09-14T18:54:35 phase=5 state=fixed -->
### verify2-p5-W2 · finding [fixed] · W2: .. was collapsed lexically before containment (phase 5)

normpath collapses .. lexically while the kernel resolves it through symlinks, so fr and docker could disagree about the directory. Fix: contain_token_dir refuses any .. component in the candidate before normalising (covers mount-resolved and canonical spellings). Proven by tests/unit/test_secrets_infisical.py::test_resolve_token_dir_refuses_dotdot_even_when_it_normalizes_inside (a source that normalises to the legit layout is still refused) plus the existing .. escape case.

<!-- fr:journal kind=finding scope=plan id=verify2-p5-W3 created=2026-09-14T18:54:37 phase=5 state=fixed -->
### verify2-p5-W3 · finding [fixed] · W3: localEnv default with a set-but-empty variable (phase 5)

Chose env[name] || default: a variable that is set but empty takes the default, matching JS || semantics; no default still yields the empty string like a shell. UNCONFIRMED against the devcontainer CLI source — @devcontainers/cli is installed neither in the container nor at a discoverable host path (npm root -g, fnm, homebrew, ~/.npm-global searched), so this is pinned by the phase-6 live smoke: if the CLI resolves a set-but-empty variable to the empty string, the host dir and the container mount would diverge and devcontainer up fails loudly on the missing bind source. Proven by tests/unit/test_secrets_infisical.py::test_resolve_token_dir_supports_localenv_default_values (unset, set, set-empty).

<!-- fr:journal kind=finding scope=plan id=verify2-p5-W4 created=2026-09-14T18:54:39 phase=5 state=fixed -->
### verify2-p5-W4 · finding [fixed] · W4: one refused glob match stopped the whole orphan token reap (phase 5)

_reap_orphan_tokens wrapped the loop in a single try. Fix: matches are visited in sorted order, each in its own try that logs and continues. Proven by tests/unit/test_secrets_wiring.py::test_gc_orphan_token_reap_continues_past_a_refused_match (a symlinked profile dir aaa/<base> is refused and its target untouched; dev/<base> after it is reaped).

<!-- fr:journal kind=finding scope=plan id=verify2-p5-W5 created=2026-09-14T18:54:40 phase=5 state=fixed -->
### verify2-p5-W5 · finding [fixed] · W5: vacuous or-clause in the HOME-source test (phase 5)

test_uncontained_source_fails_closed_at_up_exec_and_cleanup ended with ... or (home / .cache).exists(), which could not fail. Now asserts the fake HOME contains exactly .bashrc afterwards.

<!-- fr:journal kind=decision scope=plan id=verify2-p5-toctou-residual created=2026-09-14T18:54:42 phase=5 -->
### verify2-p5-toctou-residual · decision · Accepted residual: check-then-rmtree TOCTOU in remove_token_dir at teardown (phase 5)

remove_token_dir contains and symlink-checks the dir, then truncates children and calls rmtree; a same-user host process could swap the dir between the check and the rmtree. Accepted: the container is verified gone before teardown cleanup runs, so only a same-user host process is in a position to race it (and such a process already has every permission the race would grant), and rmtree uses an fd-based walk that does not follow nested links. No code change.
