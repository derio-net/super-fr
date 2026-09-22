# Journal: 2026-09-22-opencode-plugin-delivery

<!-- fr:journal kind=repro scope=debug id=930974f3f998 created=2026-09-22T19:26:46 -->
### 930974f3f998 · repro · install.sh never delivers the OpenCode plugin; parity says it is wired

On a host where `install.sh` ran with `~/.config/opencode` present, the fr skills (`~/.config/opencode/skills/fr-*`) and tier agents (`~/.config/opencode/agent/fr-phase-executor-*.md`) are there, but `~/.config/opencode/plugins/` has no fr module. `opencode debug config` (opencode 1.18.32) resolves `plugin` to a single foreign module. Meanwhile `fr harness parity` declares `fr-isolation-required` and `fr-run-idle-guard` on OpenCode as `partial` (wired). Consumers therefore run OpenCode with no edit gate and no idle adapter.

<!-- fr:journal kind=hypothesis scope=debug id=6cb3b5bb95fc created=2026-09-22T19:26:47 -->
### 6cb3b5bb95fc · hypothesis · OpenCode loads only top-level modules in its global plugins dir

Tested with an isolated `XDG_CONFIG_HOME` and two sentinel plugins: `plugins/top.ts` was registered, imported and initialized; `plugins/sub/nested.ts` was never imported. The host's `plugins/blog-craft/` directory is likewise absent from the resolved list. **Confirmed.** Consequence: a delivered plugin must be a top-level `*.ts`/`*.js` file, and support modules may live in a subdirectory, because only the loader is scanned. An extensionless executable (#568's approach) is never loaded.

<!-- fr:journal kind=root-cause scope=debug id=dc75f183483f created=2026-09-22T19:26:47 -->
### dc75f183483f · root-cause · install.sh's OpenCode block has no plugin step, and parity observes source, not delivery

`scripts/install.sh` §7b copies skills, commands and agents under the OpenCode opt-in gate and nothing else; no line writes `$HOME/.config/opencode/plugins`. `fr.harness.observe._read_opencode` credits the two OpenCode cells from `super-fr-parity:` marker comments in `packages/fr-opencode-plugin/src/*.ts`. That proves the plugin *registers* the surfaces, never that any consumer receives it. This repo's own OpenCode sessions load it through `.opencode/plugins/fr-isolation-required.ts`, which hid the gap from everyone working here.

<!-- fr:journal kind=ruled-out scope=debug id=bad75e495ecb created=2026-09-22T19:30:28 -->
### bad75e495ecb · ruled-out · 'Listed in opencode debug config' is not evidence the plugin works

Mutation: I delivered the plugin with `idle.ts` deleted. `opencode debug config` still listed the loader, so the registration probe stayed green. Only the runtime probe went red: a sentinel plugin that OpenCode itself loads imports the delivered loader, drives its hook and writes the verdicts to a file. OpenCode's logs do not record plugin loads (checked at `--log-level DEBUG`), so that file is the only evidence. Registration is necessary but not sufficient, and both probes stay.

<!-- fr:journal kind=finding scope=debug id=f-delivery created=2026-09-22T19:33:35 state=fixed -->
### f-delivery · finding [fixed] · install.sh delivers the plugin as a top-level loader plus sources

New `scripts/deliver-opencode-plugin.sh install|uninstall <plugins-dir>` is called inside `install.sh`'s existing OpenCode opt-in gate and its `--uninstall` block. It writes `<plugins>/fr-opencode-plugin.ts` (a default re-export) and `<plugins>/fr-opencode-plugin/*.ts`; no build and no `bun`. Pinned by `tests/unit/test_opencode_plugin_delivery.py` (behavioural, red first) and `tests/integration/test_opencode_plugin_live.py`: the real opencode registers the loader, and OpenCode's own runtime imports it and refuses a base-clone edit. CI runs the live file with opencode-ai@1.18.32 and `FR_REQUIRE_OPENCODE=1`.

<!-- fr:journal kind=finding scope=debug id=f-double-load created=2026-09-22T19:33:35 state=fixed -->
### f-double-load · finding [fixed] · A global copy plus a project-local copy would nudge twice per idle position

Delivering globally means super-fr itself (`.opencode/plugins/`) and any consumer that also lists the plugin in `opencode.json` load two instances in one OpenCode process. The edit gate doubling is harmless (both refuse). The idle adapter's once-per-position memory was per handler, so each copy sent its own nudge; the red test showed 2 sends. The plugin now passes a `globalThis`-keyed map (`Symbol.for`), which separately loaded module copies share; `createIdleHandler`'s default stays per instance. Pinned by `idle.test.ts` "two loaded copies send ONE nudge per run position".
