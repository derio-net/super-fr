<!-- fr:journal-schema=2 -->
# Journal: 2026-10-20-opencode-2-support

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-20T05:29:50+00:00 input=true -->
### operator-brief · discovery · Operator brief, verbatim

OpenCode 2.0 was released. See whether we need to update our support for
it and whether any of the features lagging behind Claude can be fixed
now. See https://opencode.ai/v2/docs/migrate-v1/

<!-- fr:journal kind=discovery scope=spec id=opencode-2-breaks-plugin-and-store created=2026-10-20T05:29:50+00:00 -->
### opencode-2-breaks-plugin-and-store · discovery · On 2.0.32 the plugin does not load and the store moved to session_v2/session_message

Measured on this host, OpenCode 2.0.32 (the only binary; V1 is not side by
side):

- `~/.local/share/opencode/log/opencode.log` records `failed to load
  plugin ... Plugin must export a default definition with an id and an
  effect or setup function`, for the delivered global copy and this
  repo's project-local copy alike. V1 plugin functions are not an
  implementation in V2, so the edit gate, idle guard, pin, session export
  and claim are all inert.
- `opencode.db` holds both stores. A live 2.0 session has a row in
  `session_v2` and **0** rows in `part`; its messages are `session_message`
  rows whose `data.content[]` carries reasoning/text/tool items. The
  legacy `session`/`message`/`part` tables receive nothing.
- The migration was lossless: `session_v2` holds all 230 sessions
  including 1.18.x/1.19.x, and `session_message` holds 10 871 rows with
  V1's `cost`/`tokens`/`model`/`agent` shape — which is why V2-only
  readers lose no history.
- Tool items are renamed (`bash` -> `shell`) and reshaped (`id`, `name`,
  `state.{status,input,content,metadata}`, `time.{created,ran,completed}`).
- V2 adds `ctx.permission.hook("evaluate")` with `action: "shell"` and
  the scanner's command resources, and `@opencode/plugin/tui` UI slots.

<!-- fr:journal kind=decision scope=spec id=opencode-2-scope created=2026-10-20T05:29:50+00:00 decided_by=operator -->
### opencode-2-scope · decision · Full parity push, V2-only, deny, delivered status line, no worktree routing

Round 1: full parity push (restore plus bash gate, acceptance nag,
pipeline sentinel, session bind/unbind, status line); dual V1/V2 support
rejected in favour of V2-only; V2-only store readers with a loud 1.x
refusal; verification by `candidate` plus post-merge live rows.

Round 2: the loud 1.x refusal is per-session with a version-named reason
(a per-store preflight would refuse a mid-migration store and an upgraded
binary whose store still holds old sessions); the shell gate uses
`effect: "deny"` for Claude parity, never `ask`; the status line is
delivered and registered in `cli.json` by the installer, appending only
its own entry; `fr-worktree-create`/`fr-worktree-remove` stay out and are
filed as a follow-up.

_`decided_by=operator` recorded unverified: the gate could not read who answered it._

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-10-20T05:29:56+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: design-risk. Round 1's full-parity scope decided what to build; round 2 had to settle four things that decision opened and the code could not answer — the shape of the loud 1.x refusal (per-session vs per-store), the shell gate's effect (deny vs ask), how the TUI status line is delivered and registered, and whether worktree routing joins this run.
