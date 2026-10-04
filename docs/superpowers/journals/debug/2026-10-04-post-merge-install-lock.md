# Journal: 2026-10-04-post-merge-install-lock

<!-- fr:journal kind=repro scope=debug id=2b8999cf82c2 created=2026-10-04T06:33:41+00:00 -->
### 2b8999cf82c2 · repro · install.sh replaces live install state in place; overlapping installs collide

Sandboxed HOME (UV_TOOL_DIR/UV_TOOL_BIN_DIR under it, VK_INSTALL_SKIP_PREFLIGHT=1), probing in a loop while scripts/install.sh runs:
- one install: `~/.local/bin/fr` and its tool env are absent for ~30 ms (`uv tool install --force` deletes the env in place before rebuilding). The idle-guard hook itself stayed exit 0 throughout — it fails open, as designed.
- three concurrent installs: one aborted with `mv: .../installed_plugins.json.tmp: No such file or directory` — every install writes the same fixed `<file>.tmp` sidecars (settings.json, installed_plugins.json, known_marketplaces.json), so overlapping runs race and can also clobber each other's JSON.
- `ln -sfn <version> current` (step 4) is unlink-then-create on macOS: during 500 flips a tight probe found `current` missing at 21,588 of 1.6M instants. Invoking `current/hooks/fr-run-idle-guard.sh` while flipping: 388× rc 0, 9× rc 127 (`No such file or directory`), 3× rc 126 (`bad interpreter`).

<!-- fr:journal kind=ruled-out scope=debug id=1a99f0e737d7 created=2026-10-04T06:33:48+00:00 -->
### 1a99f0e737d7 · ruled-out · The idle-guard script's own handling of a failing fr

Once bash has the script open, `trap 'exit 0' EXIT` + fail-open checks make every fr failure (missing, half-built, refusing, hung past the 20 s watchdog) exit 0. Confirmed under live installs: every probe returned 0. A Stop-hook *error* needs the script itself to be unrunnable.

<!-- fr:journal kind=ruled-out scope=debug id=fccccb18e375 created=2026-10-04T06:33:53+00:00 -->
### fccccb18e375 · ruled-out · Hook timeout while fr starts slowly mid-build

The hook bounds fr with its own 20 s watchdog (FR_IDLE_GUARD_TIMEOUT); probes during installs ran 1-2 s. Not the cause.

<!-- fr:journal kind=root-cause scope=debug id=e31b3a4386ca created=2026-10-04T06:33:58+00:00 -->
### e31b3a4386ca · root-cause · install.sh mutates live, shared install state without atomic swaps or a machine lock

Every surface a running session executes is replaced in place: the plugin's `current` link via non-atomic `ln -sfn` (a hook fired in the gap exits 127/126 — the only route to a Stop hook *error*, since the script cannot fail once running), the `fr` tool env via `uv tool install --force` (fr absent ~30 ms), and fixed `.tmp` sidecars that two concurrent installs share. A day of ~12 releases with a hand/watcher/post_merge install per release multiplies both the windows and the overlaps. One cause — no serialisation, no atomic replacement — with three surfaces.
