# Journal: 2026-07-24-remove-vk-legacy-fallbacks

<!-- fr:journal kind=discovery scope=plan id=p1-isolation-reads-retired created=2026-07-24T19:32:44 phase=1 -->
### p1-isolation-reads-retired · discovery · Phase 1: isolation vk dual-read fallbacks removed (phase 1)

types.py: profiles_config reads only fr-profiles.yaml (lone vk-profiles.yaml ignored, returns {}); removed _legacy_state_dir — load_state/list_states/delete_state now touch only .git/fr/isolation. local.py _ensure_mounted_env_file: a devcontainer.json mounting /.config/vk/secrets/ now raises IsolationError pointing at 'fr init migrate' and creates no vk file (was: warn + create). Dead _warn_legacy and its 'import sys' deleted from types.py; import dropped from local.py. Tests rewritten fallback-warns -> fallback-gone. 116 tests in test_isolation.py green; ruff + mypy clean. Files: packages/fr/src/fr/isolation/types.py, packages/fr/src/fr/isolation/local.py, tests/unit/test_isolation.py.

<!-- fr:journal kind=finding scope=plan id=p1-acceptance-row-not-implemented created=2026-07-24T19:32:50 phase=1 state=open -->
### p1-acceptance-row-not-implemented · finding [open] · Acceptance row vk-legacy-fallbacks-removed still not-implemented after phase 1 (phase 1)

Completing phase 1 warned: acceptance row 'vk-legacy-fallbacks-removed' is still not-implemented. Phase 1 scope did not include the acceptance matrix backfill, and phases 2 (fr_vk VK_BRIDGE_* fallback) and 3 remain. Orchestrator should flip the row's status and cite the new test refs (tests/unit/test_isolation.py: test_profiles_config_ignores_lone_vk_profiles, test_load_state_ignores_legacy_vk_dir, test_list_states_ignores_legacy_vk_dir, test_up_legacy_vk_mount_hard_errors) once the full removal lands, or record why in notes.

<!-- fr:journal kind=discovery scope=plan id=bd44f330ef6a created=2026-07-24T19:38:54 -->
### bd44f330ef6a · discovery · Phase 2: VK_BRIDGE_* bridge_env fallback retired

bridge_env now returns os.environ.get('FR_BRIDGE_<name>') only; dropped the VK_BRIDGE_<name> dual-read + '[fr] WARNING: legacy' line and the 'import sys'. Stale '(legacy: VK_BRIDGE_*)' notes dropped from bridge_cli.py _configured_repos / _bridge_checkout_base docstrings. Only VK_BRIDGE match remaining in packages/*/src is the config.py docstring describing the removal — no read survives.

<!-- fr:journal kind=finding scope=plan id=f64d417d0cd0 created=2026-07-24T19:39:03 state=fixed -->
### f64d417d0cd0 · finding [fixed] · Plan gap: integration/unit test fixtures fed the removed VK_BRIDGE_* fallback

Phase 2 steps only named tests/unit/test_bridge_cli.py, but 12 other tests set VK_BRIDGE_REPOS / VK_BRIDGE_LOCK_PATH / VK_BRIDGE_RECOVER_ORPHAN_CARDS as pure fixtures feeding the code under test. With the fallback gone these went red (PermissionError on real /var/run/fr-bridge.lock; recover-orphan no longer triggered). Migrated those fixtures to FR_BRIDGE_* — mechanical, no new behavior. Files: tests/integration/test_bridge_cli.py, tests/integration/test_bridge_resilience.py, tests/unit/test_bridge_workspaces.py. Left out of scope: test_install_bridge.py VK_BRIDGE_WRAPPER_PATH (read by scripts/install.sh, not bridge_env — not part of this spec's removal); harmless redundant delenv in test_bridge_checkout.py:81; and the deliberate 'VK is ignored' assertions in test_bridge_cli.py bridge_env tests.
