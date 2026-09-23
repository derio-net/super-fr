# fr-opencode-plugin

An [OpenCode](https://opencode.ai) plugin that ports super-fr's
`fr-isolation-required` PreToolUse hook (Claude Code) to OpenCode's
`tool.execute.before` hook API.

It blocks every non-read-only file-writing tool call against tracked source in
an fr-enabled repository (one with a `.devcontainer/*/devcontainer.json`
profile or a `docs/superpowers/plans/` tree). It recursively reads known path
arguments, finds absolute paths in other arguments, and parses `apply_patch`
headers with OpenCode's own grammar. Relative paths resolve from
`ctx.directory`, matching OpenCode. An unparseable patch target is denied
rather than allowed,
unless:

- a valid `.fr-isolation` marker is present (written by `fr isolation up` /
  `fr isolation down` — must record `mode: "worktree"` for *this* toplevel,
  and this must actually be a linked worktree, not the primary clone), or
- the target path matches a glob in a `.fr-isolation-allow` file at the
  repo toplevel, or
- `FR_BASE_OK=1` is set in the environment (deliberate base-clone edit).

This mirrors `plugins/super-fr/hooks/fr-isolation-required.sh` — see that
script and `plugins/super-fr/rules/fr-isolation-required.md` for the
authoritative rule text and decision-logic comments this plugin follows.

## The idle guard (`session.idle`)

The same plugin also carries the OpenCode half of super-fr's **idle guard**
(gh#518): on a `session.idle` event it runs `fr run check --idle --format json`
in the session's directory and, when fr says the run is *advanceable with nobody
working on it*, sends fr's next command back into the session
(`/session/{id}/prompt_async`). Claude Code's counterpart
(`plugins/super-fr/hooks/fr-run-idle-guard.sh`) **blocks** the stop; OpenCode
cannot refuse a stop, so this one **continues** the session instead — a weaker
tier, declared `partial` in `fr harness parity`.

It is silent on anything but a clean, parsed "idle" (fr missing, erroring,
refusing or hanging included), acts at most once per run position, leaves child
(subagent) sessions alone, and never throws. Whether a run is idle is fr's
verdict alone — `src/idle.ts` is transport.

**Not live-proven.** `session.idle` and `prompt_async` were read from the
installed SDK's types and the tests drive the handler with a fake client; that a
plugin-originated prompt on idle actually *executes* in a live session has not
been shown. A green `bun test` does not show it.

## How consumers get it

super-fr's `install.sh` delivers it (gh#563), under the same opt-in as the
OpenCode skills and agents (`~/.config/opencode` exists, or
`OPENCODE_SKILLS_INSTALL=1`). `scripts/deliver-opencode-plugin.sh` writes:

```
~/.config/opencode/plugins/fr-opencode-plugin.ts     the loader OpenCode loads
~/.config/opencode/plugins/fr-opencode-plugin/*.ts   this package's src/
```

OpenCode loads only top-level `*.ts`/`*.js` files in that directory, so the
sources sit in a subdirectory it does not scan, and the loader re-exports
them. There is no build step: OpenCode runs plugins on Bun, which runs
TypeScript directly. `install.sh --uninstall` removes both paths. Nothing
per repo is needed: the hook is a no-op outside an fr-enabled repo (no
`.devcontainer/*/` profile and no `docs/superpowers/plans/`).

`tests/integration/test_opencode_plugin_live.py` checks the delivered copy
against the real `opencode` binary: it is registered, and OpenCode's own
runtime imports it and refuses a base-clone edit. CI runs it pinned to the
OpenCode version it was written against.

## Using it in this repo

This repo loads it automatically via `.opencode/plugins/fr-isolation-required.ts`,
a thin re-export of `src/index.ts`. On a machine that also ran `install.sh`,
OpenCode then loads two copies. That is safe: both refuse the same edits, and
the idle adapter's once-per-position memory is shared process-wide, so it
still sends one nudge, not two.

## Development

```bash
bun install
bun test
```

`src/marker.ts` holds the pure marker/allowlist decision logic (unit
tested directly in `test/marker.test.ts`); `src/index.ts` wires it into
OpenCode's `tool.execute.before` hook (tested end-to-end, including a real
`git worktree add` scenario, in `test/index.test.ts`). `src/idle.ts` is the idle guard's
`event` handler (`test/idle.test.ts`). `src/index.ts` exports plugins ONLY —
OpenCode calls every export of a plugin module as a plugin.

## Verification

Direct paths, nested path arguments, relative paths, symlink targets, and
`apply_patch` patch-body targets have regression coverage in `bun test` and
run in CI. Bash is intentionally ungated because an OpenCode tool hook cannot
inspect filesystem effects performed by a shell command.
