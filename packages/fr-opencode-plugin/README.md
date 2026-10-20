# fr-opencode-plugin

An [OpenCode](https://opencode.ai) 2.x plugin carrying super-fr's harness half
on OpenCode: the isolation gates, the discipline backstops, the session
bindings, and a status line. It is the OpenCode counterpart of super-fr's
Claude Code hooks, ported surface by surface (spec
`docs/superpowers/specs/2026-10-20-opencode-2-support-design.md`).

It targets the V2 plugin API only (`export default {id, setup}` /
`{id, setup}` for the TUI). An OpenCode 1.x binary is refused loudly, by name,
rather than half-hooked.

## What it does

| Surface | Mechanism | Counterpart |
|---|---|---|
| Edit gate | `tool.execute.before` on `write`/`edit`/`patch`/`multiedit` | `fr-isolation-required.sh` |
| Shell gate | `execute.before` on the **whole** shell command line | `fr-isolation-guard.sh` |
| Push guard | `execute.before` on `git push` | `fr-merged-pr-push-guard.sh` |
| Pipeline sentinel | `execute.after` on a pipeline `skill` call | `fr-pipeline-sentinel.sh` |
| Session bind/unbind | `execute.after` on `fr isolation up\|exec\|down`, `fr run start`; `session.deleted` | `fr-session-bind.sh`, `fr-session-unbind.sh` |
| Child-session claim | `execute.before`, the child's first call (gh#530) | — |
| `fr` binary pin | `ctx.shell.hook("create.before")` exporting `FR_HARNESS_FR` | `fr-binary-pin.sh` |
| Acceptance nag | `ctx.session.hook("context")`, first request | `fr-acceptance-nag.sh` |
| Idle guard | `session.idle` | `fr-run-idle-guard.sh` |
| Status line | TUI `tui/index.tsx`, slot `prompt.footer.status` | `fr-statusline-segment.sh` |

Two engines decide the shell gate now (the bash script and `src/guard.ts`), so
the contract between them is a **captured** verdict table —
`tests/fixtures/hooks/guard-verdicts.yaml`, produced by running the real bash
script (`capture_guard_verdicts.py`) — and both suites run every row of it. The
TS port keeps the bash allowances verbatim, including the ones that look too
permissive; parity first, improvement separately.

## The edit gate

It blocks every non-read-only file-writing tool call against tracked source in
an fr-enabled repository (one with a `.devcontainer/*/devcontainer.json`
profile or a `docs/superpowers/plans/` tree). It recursively reads known path
arguments, finds absolute paths in other arguments, and parses `apply_patch`
headers with OpenCode's own grammar. Relative paths resolve from
`ctx.location.directory`, matching OpenCode. An unparseable patch target is
denied rather than allowed, unless:

- a valid `.fr-isolation` marker is present (written by `fr isolation up` /
  `fr isolation down` — must record `mode: "worktree"` for *this* toplevel,
  and this must actually be a linked worktree, not the primary clone), or
- the target path matches a glob in a `.fr-isolation-allow` file at the
  repo toplevel, or
- `FR_BASE_OK=1` is set in the environment (deliberate base-clone edit).

See `plugins/super-fr/rules/fr-isolation-required.md` for the authoritative
rule text and `src/marker.ts` for the decision logic.

## The shell gate

A tool hook cannot see a shell command's filesystem effects, so the shell gate
judges the **command line** — and only while a pipeline sentinel exists for the
session. Inside the pipeline's base repo it refuses the command, except the
`fr isolation …` lifecycle, `fr run start`, the bootstrap/info verbs, and a
leading `cd` into a valid workspace. The unit of decision is the whole line,
never one piece of it: `cd <worktree> && git status` judged piecewise would read
as a bare `git status` in the base clone.

## The discipline backstops

The push guard refuses `git push` from a branch whose PR is already merged or
closed, while a pipeline is active — fail-open on every ambiguity (no
sentinel, no push, `gh` missing, no PR, auth or network error, timeout), exactly
as the bash hook does. It is a backstop, not a security boundary.

## The idle guard (`session.idle`)

On `session.idle` it runs `fr run check --idle --format json` in the session's
directory and, when fr says the run is *advanceable with nobody working on it*,
sends fr's next command back into the session (`/session/{id}/prompt_async`).
Claude Code's counterpart **blocks** the stop; OpenCode cannot refuse a stop, so
this one **continues** the session instead — a weaker tier, declared `partial`
in `fr harness parity`.

It is silent on anything but a clean, parsed "idle" (fr missing, erroring,
refusing or hanging included), acts at most once per run position, leaves child
(subagent) sessions alone, and never throws. Whether a run is idle is fr's
verdict alone — `src/idle.ts` is transport.

## The acceptance nag

At a top-level session's first model request, `ctx.session.hook("context")`
appends one system part carrying `fr acceptance status --brief` — the open
acceptance debt. It never rewrites the operator's prompt, fires once per
session (process-wide, so a plugin loaded twice still serves one part), skips
child sessions, and returns before spawning anything in a repo with no
acceptance matrix.

## The status line

A TUI entry inside the plugin directory (`src/tui/`, delivered as `tui/`)
claims `prompt.footer.status` and `home.footer.status` and renders
`fr-statusline-segment.sh --format plain --cwd <session dir>`: `fr ⎇ <branch>`
inside an fr workspace, `<branch> · no fr-isolation` outside, nothing outside a
git repo. It refreshes on `session.execution.*` and `session.idle`, coalesced —
never per keystroke.

`<session dir>` is the directory of the session the slot renders for (the
slot input's `sessionID`, looked up in the TUI's session data), cached per
session id with one coalesced read each; the home screen, or a session whose
data has not loaded yet, uses the TUI's launch directory. The lookup is
unit-tested against the plugin API's declared shape; the live test opens
sessions in the launch directory only, so a session from another project is
not yet proven live.

`src/tui/index.tsx` is the only file excluded from `tsc` (pinned by exact
path, and by `test/tsconfig.test.ts`): its JSX types come
from `@opentui/solid`, a peer the OpenCode binary bundles but `node_modules`
does not carry. All the logic lives in `src/tui/segment.ts`, which is
type-checked and unit-tested; the entry itself is proven by the live TUI test.

## How consumers get it

super-fr's `install.sh` delivers it (gh#563), under the same opt-in as the
OpenCode skills and agents (`~/.config/opencode` exists, or
`OPENCODE_SKILLS_INSTALL=1`). `scripts/deliver-opencode-plugin.sh` writes ONE
plugin directory and nothing at the top level:

```
~/.config/opencode/plugins/fr-opencode-plugin/index.ts       the server plugin
~/.config/opencode/plugins/fr-opencode-plugin/*.ts           the sources it imports
~/.config/opencode/plugins/fr-opencode-plugin/tui/index.tsx  the status line (TUI only)
```

OpenCode 2 treats each **directory** in the plugins directory as one plugin and
resolves entrypoints by name: `<dir>/server` or else `<dir>/index` for the
server, `<dir>/tui` for the TUI. There is no build step — OpenCode runs plugins
on Bun, which runs TypeScript (and `.tsx`, through its own Solid transform)
directly, so nothing is installed consumer-side.

`install` also appends that directory to `~/.config/opencode/cli.json`'s
`plugins` list — created when absent, refused with the file named when it is
unparsable (never overwritten), idempotent by exact path. A **file** path there
is silently ignored by OpenCode 2; it must be the directory. `install.sh
--uninstall` removes the directory, the `cli.json` entry, and the top-level
`fr-opencode-plugin.ts` loader older versions wrote — that loader is a *second*
load of the same plugin on 2.x, so install deletes a stale one too.

Nothing per repo is needed: every gate is a no-op outside an fr-enabled repo.

`tests/integration/test_opencode_plugin_live.py` checks the delivered copy
against the real `opencode` binary, in an isolated config/data/home: it loads
exactly once, OpenCode's own runtime imports it and refuses a base-clone edit,
and the TUI renders the status line on a pty. CI runs it against the OpenCode
versions the spec names.

## Using it in this repo

This repo loads it automatically via `.opencode/plugins/fr-isolation-required.ts`,
a thin re-export of `src/index.ts`. On a machine that also ran `install.sh`,
OpenCode then loads two copies. That is safe: both refuse the same edits, the
idle adapter's once-per-position memory and the nag's once-per-session memory
are shared process-wide, so each still nudges once, not twice.

## Development

```bash
bun install
bun test
bunx tsc --noEmit
```

`src/marker.ts` holds the pure marker/allowlist decision logic (unit tested
directly in `test/marker.test.ts`); `src/index.ts` wires every surface into the
V2 hooks (tested end-to-end, including a real `git worktree add` scenario, in
`test/index.test.ts`). `src/guard.ts` is the shell gate and `src/idle.ts` the
idle guard's `event` handler. `src/index.ts` exports plugins ONLY — OpenCode
calls every export of a plugin module as a plugin.

## Verification

Direct paths, nested path arguments, relative paths, symlink targets, and
`apply_patch` patch-body targets have regression coverage in `bun test` and run
in CI. The shell gate's behaviour is pinned to the bash script by the captured
verdict table (14 deny / 18 allow rows), and `bun test` fails if either engine
diverges from it.
