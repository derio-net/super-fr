# Journal: 2026-07-24-remove-vk-legacy-fallbacks

<!-- fr:journal kind=discovery scope=plan id=p1-isolation-reads-retired created=2026-07-24T19:32:44 phase=1 -->
### p1-isolation-reads-retired · discovery · Phase 1: isolation vk dual-read fallbacks removed (phase 1)

types.py: profiles_config reads only fr-profiles.yaml (lone vk-profiles.yaml ignored, returns {}); removed _legacy_state_dir — load_state/list_states/delete_state now touch only .git/fr/isolation. local.py _ensure_mounted_env_file: a devcontainer.json mounting /.config/vk/secrets/ now raises IsolationError pointing at 'fr init migrate' and creates no vk file (was: warn + create). Dead _warn_legacy and its 'import sys' deleted from types.py; import dropped from local.py. Tests rewritten fallback-warns -> fallback-gone. 116 tests in test_isolation.py green; ruff + mypy clean. Files: packages/fr/src/fr/isolation/types.py, packages/fr/src/fr/isolation/local.py, tests/unit/test_isolation.py.

<!-- fr:journal kind=finding scope=plan id=p1-acceptance-row-not-implemented created=2026-07-24T19:32:50 phase=1 state=open -->
### p1-acceptance-row-not-implemented · finding [open] · Acceptance row vk-legacy-fallbacks-removed still not-implemented after phase 1 (phase 1)

Completing phase 1 warned: acceptance row 'vk-legacy-fallbacks-removed' is still not-implemented. Phase 1 scope did not include the acceptance matrix backfill, and phases 2 (fr_vk VK_BRIDGE_* fallback) and 3 remain. Orchestrator should flip the row's status and cite the new test refs (tests/unit/test_isolation.py: test_profiles_config_ignores_lone_vk_profiles, test_load_state_ignores_legacy_vk_dir, test_list_states_ignores_legacy_vk_dir, test_up_legacy_vk_mount_hard_errors) once the full removal lands, or record why in notes.
