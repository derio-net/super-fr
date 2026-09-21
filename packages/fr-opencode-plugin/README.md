# fr-opencode-plugin

An [OpenCode](https://opencode.ai) plugin that ports super-fr's
`fr-isolation-required` PreToolUse hook (Claude Code) to OpenCode's
`tool.execute.before` hook API.

It blocks Edit/Write-class tool calls (`edit`, `write`, `patch`,
`multiedit`) against tracked source in an fr-enabled repository (one with
a `.devcontainer/*/devcontainer.json` profile or a
`docs/superpowers/plans/` tree) unless:

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

## Using it in this repo

This repo loads it automatically via `.opencode/plugins/fr-isolation-required.ts`,
a thin re-export of `src/index.ts`. No extra setup needed for OpenCode
sessions run from within this repository.

## Using it in another repo

1. Install the package (once published) or vendor this directory.
2. Add it to your repo's `opencode.json`:

   ```json
   {
     "plugin": ["fr-opencode-plugin"]
   }
   ```

   or, if consuming from a local path / monorepo checkout, point at the
   built entry point directly per OpenCode's local-plugin loading
   conventions.
3. Ensure your repo actually has an fr-isolation marker workflow (a
   `.devcontainer/*/devcontainer.json` profile and/or
   `docs/superpowers/plans/`) — otherwise the hook is a no-op (`frEnabled`
   is false and every edit is allowed).

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

The edit-class tool names (`edit`, `write`, `patch`, `multiedit`) and the
`args.filePath` argument shape have been verified against live `opencode run`
sessions; the marker and hook behavior are covered by `bun test` and run in CI.
