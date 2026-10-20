# OpenCode 2.0: restore the integration, then close the Claude gap

## Context

OpenCode 2.0 shipped three intentional breaking changes: a new plugin API, new
server/client contracts, and one global `cli.json` instead of layered
`tui.json(c)`. Everything else is meant to keep working. Measured on this host
(OpenCode **2.0.32**, the only binary installed; V1 is not side by side):

- **The plugin does not load at all.** `~/.local/share/opencode/log/opencode.log`
  records, for both the delivered global copy and this repo's project-local copy,
  `failed to load plugin … Plugin must export a default definition with an id and
  an effect or setup function`. A V1 plugin function is not an implementation in
  V2; moving the file is not a port. Today OpenCode users therefore have **no**
  edit gate, **no** idle guard, **no** binary pin, **no** session export and
  **no** claim.
- **The store moved, and the old tables are frozen.** 2.0 reads and writes
  `session_v2` (session rows) and `session_message` (one row per message, its
  `data.content[]` carrying reasoning/text/tool items). `session`, `message` and
  `part` still exist but receive nothing: the live 2.0 session on this host has
  **0 rows in `part`**. `fr run`'s transcript gates (`operator-gate`,
  `spec-review-independence`, `visual-evidence`, `deliver-tests-provenance`) and
  `fr usage` read `session`/`message`/`part`, so they see no 2.0 session — and
  the first `fr run start` after the upgrade printed exactly that symptom.
- **On this host the migration left nothing behind.** `session_v2` holds all 230
  sessions including 1.18.x/1.19.x, and `session_message` holds 10 871 rows with
  the same `cost`/`tokens`/`model`/`agent` shape V1 used. That is one measured
  store, not a guarantee (see R13: it is pinned as a fixture), and it is the
  observation that makes a V2-only reader a plausible choice rather than a
  gamble.
- **Two things V1 could not do are now possible.** `ctx.permission.hook("evaluate")`
  exists (V1's `permission.ask`), and `ctx.tool.hook("execute.before")` rejects a
  call by throwing — so the bash gate V1 made impossible (#436) has a home
  without the per-resource granularity a permission rule alone would impose.
  `@opencode/plugin/tui` exposes UI slots, so a status line exists to write to.

The operator chose, in two question rounds: a **full parity push** (restore plus
bash gate, acceptance nag, pipeline sentinel, session bind/unbind and status
line); **V2-only** — the V1 hook implementation and `@opencode-ai/plugin` go;
V2-only store readers with a **loud, version-named refusal** for an OpenCode 1.x
session; **deny** (Claude parity, never `ask`) for the shell gate; the status
line **delivered and registered** in `cli.json` by the installer; worktree
routing (`fr-worktree-create`/`-remove`) left out and filed as a follow-up;
verification by `candidate` from phase one, with model-driven claims as
post-merge `live` rows at the Tester gate.

### Sources

Every V2 name in this spec is read from one of: the migration guide
(`/v2/docs/migrate-v1`), the plugin guide (`/v2/docs/build/plugins`), the plugin
migration guide (`/v2/docs/build/plugins/migrate-v1`), the CLI-plugin guide
(`/v2/docs/build/plugins/cli`), the permissions guide (`/v2/docs/permissions`),
the published typings of `@opencode/plugin@2.0.32` and `@opencode/schema@2.0.32`
(`dist/promise/{plugin,tool,session,shell,permission,event}.d.ts`), and direct
reads of `~/.local/share/opencode/opencode.db`. Research notes:
`docs/superpowers/journals/specs/2026-10-20-opencode-2-support.md`.

## Requirements

R1. The plugin is a V2 plugin: a default export carrying a stable `id` and a
`setup(ctx)` that registers every hook through `ctx` and returns a cleanup that
aborts the event subscription. The V1 exported function, the `"event"` /
`"shell.env"` / `"tool.execute.before"` hook names and the `@opencode-ai/plugin`
dependency are removed. `@opencode/plugin` is a type-only import (erased), so the
delivered files need no `node_modules`.

R2. The edit gate keeps its decisions and its coverage on V2: the same marker,
worktree, branch-drift, allowlist and `FR_BASE_OK` rules over V2's
`tool.execute.before` event (`event.tool`, `event.input`, `event.sessionID`),
including nested path arguments, absolute paths in other arguments, patch
bodies and symlink resolution. V2's renamed `shell` tool is classified
non-writing exactly as `bash` is today.

R3. The shell gate decides on the **whole command line and the session cwd**,
exactly as the shipped bash guard does, and runs from
`ctx.tool.hook("execute.before", …)` for `tool === "shell"`, rejecting the call
with `throw new Error(<guard's refusal text>)`. It is not built on
`permission.evaluate`: that event delivers the scanner's resources one at a
time, which would judge `cd <worktree> && git status` as a bare `git status` in
the base repo and deny the guard's most common allowed shape. The port must not
broaden or narrow today's decision, which is: no active session sentinel → allow;
a cwd outside the pipeline's base repo → allow; a leading `cd` into a valid
isolation workspace or an allowed prefix → follow it; `fr isolation …` → allow;
otherwise refuse, naming the three escapes. It also carries the three duties the
bash entrypoint performs around that decision: refreshing the sentinel's mtime
on every call, treating a linked worktree of the same repo as a workspace, and
retiring an orphaned sentinel under the same lock `fr isolation attach` takes.

R4. The merged-PR push guard is enforced on the same whole-command hook for
`git push` / `gh pr merge` commands, with today's decision and message.

R5. The idle guard continues, never blocks: `session.idle` from the
`ctx.event.subscribe()` async iterable runs the same `fr run check --idle`
predicate with the same once-per-`position` memory, and nudges with
`ctx.session.prompt` (V2's replacement for `promptAsync`). Its parity cell stays
`partial`, and says so.

R6. The session id fr reads is the one OpenCode itself supplies. On 2.0.32,
`create.before`'s `env` carries no session id, but OpenCode places the ISSUING
session's id in every command it spawns as `OPENCODE_SESSION_ID` — measured by
printing it from a child's own `echo` (2026-10-20). So fr reads
`FR_OPENCODE_SESSION_ID` when a wrapper sets it, `OPENCODE_SESSION_ID` otherwise,
and walks `parent_id` to the root for every transcript read. The plugin exports
nothing and keeps no correlation queue: one was built, measured, and removed
because the id already arrives correctly, and carrying two mechanisms for it
would only be a second thing to get wrong. `why_unobservable`'s unset-id wording
names the plugin only when NEITHER variable is present.

R7. A child session's first tool call still claims its open unit through
`fr run claim --open-unit`, unchanged: the V2 event supplies `sessionID`, and
`ctx.session.get` supplies `parentID`, `agent` and the model reference.

R8. The binary pin (`FR_HARNESS_FR`) survives: `create.before` sets it when the
plugin resolved an `fr` at load time, and a failed pin never blocks a command.

R9. The acceptance nag runs at most once per top-level session, at that
session's first model request, through
`ctx.session.hook("context", …)` — appending one system part
(`event.system.push({type: "text", text})`), never by rewriting the operator's
prompt text. It is bounded (a short timeout), skipped before any process spawn
when the repo has no `docs/acceptance/matrix.yaml`, and silent on failure.

R10. The pipeline sentinel is written on a completed `skill` tool call
(`ctx.tool.hook("execute.after", …)`) naming
`fr-goal`/`fr-brainstorming`/`fr-execute` in a base-repo cwd, with the same JSON
shape the guard and `fr` already read (`repo_root`, `workspaces`, mtime as
liveness), the same 48h GC and the same "never in a valid workspace" rule.

R11. Session bind/unbind: a completed `shell` call whose first line is
`fr isolation up|exec|down` or `fr run start` attaches the session
(`fr isolation attach --session <id> --repo <cwd> --harness opencode`), and a
`session.deleted` event from the subscription detaches it
(`fr isolation detach --session <id>`). Both are best-effort and never block.

R12. The status line is a delivered TUI entrypoint rendering
`fr-statusline-segment.sh`. It lives **beside**, not inside, the server plugin
(the server loader picks up every top-level file in the plugin directory), and
`install.sh` registers its path in `cli.json`'s `plugins` list, appending only
its own entry. The row is observed by a config probe in `fr.harness.observe`
(the entry is listed and the file exists), not by a `super-fr-parity:` marker. If
OpenCode cannot load a delivered TSX entrypoint without consumer-side peer
packages, the fallback is a command that prints the segment; the row stays
`partial` and the PR says which happened rather than claiming a status line that
does not render.

R13. `fr` reads OpenCode 2's store: session rows from `session_v2`, messages
from `session_message` (`data.content[]`), with V2's field names (`id`, `name`,
`state.{status,input,metadata,content}`, `time.{created,ran,completed}`,
`data.model.{id,providerID}`, `data.agent`, `data.cost`, `data.tokens`). Every
existing query site moves, not only the obvious one: the session probe, the
tool-part scan, the child walk, the final-text read, the unscoped top-level
query and its activity probe, the readability probe that tells "wrong database"
from "nothing happened" (gh#740), the task-brief metadata keys, and the usage
reader's session/message/part joins. Tool-name aliases `bash`→`shell` and
`task`→its V2 name are resolved in one place, and historical `session_message`
rows carrying V1 tool names stay readable. The "migration lost nothing" claim is
pinned as a fixture of migrated V1 rows (redacted, taken from a real store), not
asserted.

R14. An OpenCode 1.x session fails loudly and specifically, per requested
session: a store probe (`v2` | `v1-only` | `absent` | `unreadable`) feeds both
`why_unobservable` and the usage reader, and a `v1-only` answer names OpenCode
1.x and the fix (`upgrade opencode; super-fr supports 2.0 only`). It is reported
as `unavailable` with that reason — never as an empty observation, never as
zeros, never as today's "check `FR_OPENCODE_DB`". A database with no
`session_v2` table is reported this way per session, never as a command-level
preflight.

R15. Verification: `candidate` is the run's strategy; a scenario exercises both
readers against a fixture store and runs the delivered plugin against the real
`opencode` binary. The claims only a model-driven 2.x session can prove — a
refused edit, a refused base-clone shell command, an executed idle nudge, an
observed transcript, a correlated session id — are post-merge `live` rows at the
Tester gate, with the exact command and the exact expected refusal.

R16. Parity, matrix and prose stay honest in the same PR: `parity.yaml` rows and
their `super-fr-parity:` markers follow the port; the acceptance matrix rows
move with evidence; `docs/explainers/` (both the `.md` and the regenerated
`.html`), `README.md`, `AGENTS.md`, the canonical
`plugins/super-fr/rules/fr-isolation-required.md` (it still says OpenCode cannot
gate bash), its hand-maintained `.claude/rules/` mirror, and the generated
OpenCode/Hermes mirrors (`scripts/sync-opencode.py`, `scripts/sync-hermes.py`)
stop describing `@opencode-ai/plugin`, `shell.env`, and the bash gap. The CI
live probe moves to OpenCode 2.0.x (the 1.18.32 pin goes with V1 support). A
`.changes/feat-opencode-v2-support.yaml` fragment is added with `bump: major`
(consumers on OpenCode 1.x lose the gate) and no version-bearing field is
edited — `packages/fr-opencode-plugin/package.json` may change its dependency,
never its `version`. No artifact shape changes, so no stamp or migration is owed.

## Design

### A. The hook map, and what replaces what

| V1 (today) | V2 |
|---|---|
| `export async function FrIsolationRequired(ctx)` | `export default { id: "super-fr", async setup(ctx) }` |
| `"tool.execute.before": ({tool}, output)` | `ctx.tool.hook("execute.before", event)` — `event.tool`, `event.input`, `event.sessionID`; throwing rejects the call |
| `event` (`session.idle`) | `for await (const event of ctx.event.subscribe({signal}))` |
| `"shell.env": ({cwd, sessionID})` | none for the run-session id — OpenCode 2 itself exports `OPENCODE_SESSION_ID` on the command (§C); `create.before` carries `event.env` for the pin |
| `tool.execute.after` (none) | `ctx.tool.hook("execute.after", event)` — `event.status`, `event.result`, `event.error` |
| `chat.message` / system transform | `ctx.session.hook("prompt" \| "context", event)`; `context` carries `event.system` |
| `permission.ask` | `ctx.permission.hook("evaluate", event)` — not used for the shell gate (R3) |
| `ctx.client.session.get` / `promptAsync` | `ctx.session.get` / `ctx.session.prompt` |
| `ctx.directory`, `ctx.worktree` | `ctx.location.directory`, `ctx.location.project` |
| `@opencode-ai/plugin` ^1 | `@opencode/plugin` ^2 (types only) |

`ctx` is captured by `setup`; every handler is a closure over it. `setup`
returns a cleanup that aborts the subscription and disposes the registrations,
so a reload leaves no listener behind.

### B. Shell gate: the whole line, in one place

Today's guard denies a command **only** while a session sentinel exists and the
cwd is inside the pipeline's base repo; it folds a leading `cd` into an allowed
prefix, allows `fr isolation …` from the start of the line, names the three
escapes, refreshes the sentinel's mtime on every call, and retires an orphaned
sentinel under a lock it shares with `fr isolation attach`. All of that is
whole-line behaviour, so the decision sits where the whole line is available:
`execute.before` for the `shell` tool. A rejection fails that call alone (the
adapter's own rule), and the guard's text reaches the model exactly as Claude's
exit-2 message does.

The permission hook remains the documented interception point for shell
commands, and it is deliberately not used: `resources` are the scanner's
per-command split, so judging them one at a time inverts the guard's allowances.
This choice is the operator's "deny, not ask" decision implemented at the hook
that can see the command.

Two decision engines now exist (bash script and port). The contract between them
is a **verdict table** at `tests/fixtures/hooks/guard-verdicts.yaml` — each row
a command, cwd, sentinel and expected verdict — loaded by the existing
`tests/unit/test_hooks_guard.py` and by a new
`packages/fr-opencode-plugin/test/guard-verdicts.test.ts`. Rows cover plain
commands, compound commands (`cd <worktree> && git status`,
`fr isolation status && make`), a leading `cd` into an allowed prefix, another
repo's toplevel, a linked worktree, the sentinel heal and the absence of a
sentinel. A change to one implementation that is not a change to both goes red.

### C. The session id: measured, not correlated

The first cut of this design correlated the id from `execute.before`
(`sessionID` + `input.command`) to `create.before` (same `command`) through a
short-TTL pending queue, because `create.before` carries no session id. The
plan's first phase measured the real thing and found a better answer: the id is
already there for the only consumer that needs it. OpenCode sets
`OPENCODE_SESSION_ID` on the spawned command, naming the issuing session; fr
reads it from its own environment and walks `parent_id` to the root. The queue
and its tests were removed in the same phase.

That keeps the property the queue existed to protect — an unscoped reading is a
known, reported state, a mis-scoped one is a false claim — without a
correlation that could mis-attribute two identical commands from different
sessions.

### D. Python: one adapter, both readers, every query site

`fr.run.observed.OpenCodeSession` and `fr.usage.readers.opencode` grow a v2 path
behind the same public interface, so a gate and a usage report can never
disagree about what a session did. The sites that move are, at least:

| site | today | V2 |
|---|---|---|
| session probe (`_known`) | `SELECT 1 FROM session` | `session_v2`, else the R14 probe |
| tool parts (`_parts`) | `part` rows | `session_message.data.content[]` where `type == "tool"` |
| final text (`_final_text`) | `part` text rows | `content[]` where `type == "text"` |
| children (`_children`) | `session.parent_id` | `session_v2.parent_id` |
| root walk (`opencode_root`) | `session.parent_id` | `session_v2.parent_id` |
| unscoped top-level + activity probe | `part JOIN session` | `session_message JOIN session_v2` |
| readability probe (gh#740) | `SELECT 1 FROM session` | the R14 probe, distinguishing wrong DB from 1.x |
| task brief | `state.metadata.parentSessionId/sessionId` | measured in phase 1; the V2 task/subagent metadata |
| usage record | `session`/`message`/`part` | `session_v2`/`session_message` |

Field mapping: `data.cost`, `data.tokens.{input,output,reasoning,cache.{read,write}}`,
`data.model.{id,providerID}`, `data.agent`, `time.{created,ran,completed}`,
exit from `state.metadata.exit`, output from `state.content[].text`. The legacy
tables are read for nothing but the 1.x detection that produces R14's message;
that is what makes "V2-only" loud rather than silent.

### E. Delivery and configuration

`scripts/deliver-opencode-plugin.sh` keeps writing the server entrypoint and its
directory, copies the status-line entrypoint beside it (not inside the server
plugin's top-level scan), and `install.sh` gains a `cli.json` registration. Its
behaviour is stated rather than implied: `$XDG_CONFIG_HOME/opencode/cli.json`
(or `~/.config/opencode/cli.json`); created holding only this entry when absent;
unparsable or JSONC content refuses with a message and is never overwritten;
reinstall is idempotent by exact entry path (drop ours, then append ours);
uninstall removes that exact entry and the files it owns, leaving every other
key and entry untouched. Tested next to `test_opencode_plugin_delivery.py`.

### F. What is not changed

`fr isolation`, its marker format, the sentinel format, `fr run`'s cursor and
the gate predicates are untouched — the plugin is transport. `fr-phase-executor`
needs no worktree guard on OpenCode (its task tool takes no isolation
argument), and worktree routing stays out of scope.

## Verification

strategy: candidate

- opencode-2-plugin-loads: candidate
- opencode-2-store-read: candidate
- opencode-2-v1-refusal: candidate
- opencode-2-nag: candidate
- opencode-2-sentinel: candidate
- opencode-2-bind-unbind: candidate
- opencode-2-edit-gate: live — a refused edit requires a model-driven OpenCode 2.x session; `candidate` proves the hook's verdicts on a tool event but cannot prove a model's tool call routes through them
- opencode-2-bash-gate: live — a denied shell command requires a model-driven session to issue it; `candidate` can only prove the guard's decision on a synthesized event
- opencode-2-session-export: live — the export is the one claim that depends on V2's unobserved event ordering, so it is measured in a real session before its row is trusted
- opencode-2-idle-nudge: live — `session.idle` fires only in a real session, and the nudge is only real if it is actually submitted
- opencode-2-status-line: live — a rendered terminal slot is not observable without the real TUI
gate: opencode-2-edit-gate=tester
gate: opencode-2-bash-gate=tester
gate: opencode-2-session-export=tester
gate: opencode-2-idle-nudge=tester
gate: opencode-2-status-line=tester

`candidate` is the run's strategy, driven by an agent, from phase one.
`.fr/candidate-install` already exists here, so the install contract is
unchanged.

What `candidate` proves before merge (a new `tests/scenarios/` script):

1. A fixture `opencode.db` with a 2.0 session (`session_v2` + `session_message`,
   tool items, cost/tokens) and a 1.x-only session: `fr usage` and the run
   observation report the first and refuse the second by version name.
2. The delivered plugin loads in the real `opencode` 2.0 binary (`opencode debug
   config` + the existing sentinel-plugin probe), and its `execute.before`
   verdicts on a base-clone write match the edit-gate fixture table.
3. The guard verdict table passes against both implementations, and the shell
   hook's throw is observed on a synthesized event.
4. The nag, the sentinel write and the bind/unbind command lines are driven
   through the plugin's exported handlers with a fake context, asserting the
   command each one runs.

What only a live model-driven 2.x session proves, and is therefore post-merge at
the **Tester** gate with an explicit refusal expectation:

1. An `edit` into an fr-enabled base clone is refused.
2. A `shell` command from the base clone during an active pipeline is denied,
   and `git status` from the worktree is not.
3. `OPENCODE_SESSION_ID` reaches the command, and `fr run status` names the
   top-level session, not a child's.
4. The idle nudge is actually submitted.
5. The status line renders the fr segment.

## Test Plan

Post-merge (`live`, gate `tester`), each run from a disposable clone with
OpenCode 2.0.x and a fresh config dir:

1. Enter a workspace, start a run, ask the model to edit a tracked file in the
   base clone; expect the plugin's refusal and no file change.
2. From the workspace, run `git status` (allowed) and then a base-clone write
   through `shell` during an active pipeline (denied, with the escape list).
3. In the same session run `fr run status` and confirm `OPENCODE_SESSION_ID`
   resolved to the top-level session, not a child's.
4. Let a run sit advanceable and confirm one idle nudge is submitted, with no
   second nudge at the same `position`.
5. Confirm the status line shows the fr segment, and that a session opened
   outside any repo shows none.
6. Open a session in a repo with an acceptance matrix and confirm the nag
   appears once, in the system context, not in the operator's prompt.

## Out of scope

- OpenCode 1.x support of any kind (plugin or readers); the refusal names the fix.
- `fr-worktree-create`/`fr-worktree-remove` on OpenCode (`ctx.worktree.transform`)
  — a separate follow-up, invasive to a user-facing feature.
- The durable `event`/`event_sequence` tables as an observation source (they are
  empty on this host's store).
- Any change to `fr isolation`, the sentinel format, the run cursor or the
  accepted plugin-hook decision set beyond what R2–R4 name.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-20-opencode-2-support | `derio-net/super-fr` | `2026-10-20-opencode-2-support` | — |
