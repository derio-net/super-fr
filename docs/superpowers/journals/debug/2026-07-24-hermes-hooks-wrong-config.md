# Journal: 2026-07-24-hermes-hooks-wrong-config

<!-- fr:journal kind=repro scope=debug id=phase8-live-repro created=2026-07-24T17:12:19 -->
### phase8-live-repro · repro · Fresh Hermes session allows tracked edit outside fr isolation

After scripts/install.sh on super-fr 3.15.0, `hermes skills list` found fr-goal and SOUL rules loaded, but a fresh `hermes chat` patched `/opt/data/home/hermes-proof-base/tracked.txt` in an fr-enabled base clone. `hermes hooks list` reported: No shell hooks configured in ~/.hermes/config.yaml. The installer had written all four registrations to `/opt/data/cli-config.yaml`, leaving `/opt/data/config.yaml` without `hooks:`.

<!-- fr:journal kind=root-cause scope=debug id=root-cause-config-filename created=2026-07-24T17:17:44 -->
### root-cause-config-filename · root-cause · super-fr writes hooks to obsolete cli-config.yaml instead of Hermes config.yaml

Confirmed against the running Hermes v0.18.2 source and `hermes hooks list`: shell hook registration calls `iter_configured_hooks(load_config())`, where load_config reads `$HERMES_HOME/config.yaml`. super-fr 3.15.0 hardcodes `CONFIG_FILENAME = "cli-config.yaml"`, and its tests assert that obsolete path, so install succeeds while Hermes registers zero hooks.

<!-- fr:journal kind=finding scope=debug id=8ef99665a682 created=2026-07-24T17:30:10 state=fixed -->
### 8ef99665a682 · finding [fixed] · Target config.yaml, migrate legacy entries, and prove fresh-session enforcement

Changed fr.hermes to merge hooks into HERMES_HOME/config.yaml, remove only super-fr registrations from legacy cli-config.yaml on install/uninstall, and renamed the checked-in snippet to .hermes/config.snippet.yaml. TDD: two regression tests failed before the production change and passed afterward. Live Hermes 0.18.2 proof of the code shipping as 3.15.2: hermes hooks list reports four configured and allowlisted hooks; fresh base-clone patch blocked with file unchanged; linked-worktree patch allowed; FR_BASE_OK=1 patch allowed; base git switch blocked with branch unchanged; linked-worktree git add allowed. Targeted Hermes suite: 49 passed. Broad suite excluding two installer modules whose hardcoded PATH cannot see this pod user-installed jq: 1696 passed, 81 skipped.
