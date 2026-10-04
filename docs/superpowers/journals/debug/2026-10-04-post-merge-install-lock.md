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

<!-- fr:journal kind=root-cause scope=debug id=c3a06b737277 created=2026-10-04T06:41:45+00:00 -->
### c3a06b737277 · root-cause · Observed hook errors: Claude Code holds the resolved version dir, and install.sh prunes it

Supersedes the earlier root-cause entry as an account of the OBSERVED error. Every hook_non_blocking_error in the operator's last 30 days of transcripts (≈50, across Stop, PreToolUse, PostToolUse and SessionStart, Claude Code 2.1.280–2.1.287, 2026-09-24 → 2026-10-04) has the same text: `Failed to run: Plugin directory does not exist: ~/.claude/plugins/cache/derio-net--super-fr/super-fr/<version> (… run /plugin to reinstall)`, exit 1, durationMs ~2: the script never ran. Claude Code resolves installPath (`…/current`) to the version directory when it loads the plugin and keeps that path for the session; install.sh step 4 keeps only current + one previous version dir, so the third release after a session started deletes the directory it runs every hook from. The 2026-06-21 premise that a session "keeps installPath literal" no longer holds. Consequence beyond the Stop hook: the PreToolUse guards (fr-isolation-required, fr-isolation-guard, merged-pr-push-guard) fail OPEN in those sessions. Not overlap- or race-dependent: one install per release suffices.

<!-- fr:journal kind=ruled-out scope=debug id=6cfa22c2f2cf created=2026-10-04T06:41:54+00:00 -->
### 6cfa22c2f2cf · ruled-out · ln -sfn gap as the cause of the observed error

Real but not what the operator hit: the observed stderr names a missing VERSION directory, not a missing `current`. Also, on macOS/APFS even rename(2) over a symlink lets a concurrent lookup see ENOENT (60 misses in 300 os.replace swaps), so an atomic swap narrows that gap ~100x but cannot close it.

<!-- fr:journal kind=hypothesis scope=debug id=9fadb88aefd4 created=2026-10-04T08:17:00+00:00 -->
### 9fadb88aefd4 · hypothesis · Staging fr aside is enough to keep it on PATH (fix 1 — failed live)

Built a copy of the env aside and pointed the PATH symlink at it during `uv tool install --force`. The stub test passed; a live run with real uv still lost fr (~250 ms, `fr: command not found`). Probed directly: uv --force deletes the entry point its RECEIPT names — whatever that path points at by then — at 0.77 s and relinks at 2.1 s. The stub did not model that; it does now.
