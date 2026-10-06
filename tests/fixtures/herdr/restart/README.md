# herdr restart-idle fixtures

Captured live on 2026-10-06 from herdr 0.9.1 (Claude Code 2.1.289 / 2.1.291 panes),
from inside a herdr session. Every capture was read-only against operator panes; every
key press went into scratch tabs created for the probe and closed afterwards.
`pane read` prints raw terminal text, not a JSON envelope, so `_run_herdr` returns it
as `{"raw": <text>}`; the `screen-*.json` files are exactly that return value.

Redaction (`.claude/rules/third-party-privacy.md`): the home path became `/home/user`,
the scratch dir `/tmp`, a non-derio-net project name became `example-project`, and
every terminal title in `agent-list.json` became `<title redacted>`. Shapes are unchanged.

| file | command | notes |
|---|---|---|
| `agent-list.json` | `herdr agent list` | nine agents (one opencode, eight claude); `name` is absent on an unnamed pane (not `null`); `agent_status` is `idle`/`working`/`done` |
| `process-info.json` | `herdr pane process-info --pane <idle claude pane>` | `foreground_processes[]` also holds non-claude processes (an MCP server, a bare `mcp@latest` with NO `argv` key); the claude one has `argv: ["claude","--resume","<id>"]` and `cwd` |
| `process-info-model-flag.json` | same, on a pane launched `claude --model <m>` | a kept flag with a value |
| `screen-suggestion.json` | `herdr pane read <pane> --source visible --ansi` | idle (`done`) pane showing Claude's FAINT prompt suggestion: `❯\xa0` ESC[0m ESC[2m`<text>`. No shells. |
| `screen-placeholder.json` | same | a fresh session's faint placeholder (`Try "..."`), same shape as a suggestion |
| `screen-empty.json` | same | an idle pane with a truly empty prompt (`❯\xa0`); trimmed to the prompt and the status lines under it (the conversation above was an operator's) |
| `screen-draft.json` | same | a real unsent draft: `❯\xa0half typed draft`, NOT faint |
| `screen-background.json` | same | status line `2 shells, 1 monitor` and an agent panel (`⏺ main` / `◯ general-purpose ...`) under it, while herdr reports `done` |
| `screen-subagent.json` | same | captured in a scratch tab while ONE background subagent ran (after its brief turn settled): `← 1 agent` on the status line and a `◯ general-purpose` panel row under it. herdr reported `working` for the whole time the subagent ran, then `done` |
| `screen-draft-multiline.json` | same | a draft whose first line is empty (`❯\xa0`) and whose text sits on the next line, typed with shift+enter in a scratch tab |
| `tab-list.json` | `herdr tab list` | `tabs[]` of `{agent_status, focused, label, number, pane_count, tab_id, workspace_id}`; labels outside the `derio-net` org became `<label redacted>`, the `\|` ones are as captured |
| `agent-start-reuse.json` | `herdr agent start fr-probe --kind claude --pane <p> -- --resume <id>` | run in the pane right after `/exit`, the name `fr-probe` having been held by that same pane's previous claude |
| `agent-start-name-taken.json` | `herdr agent start fr-probe --kind claude --pane <other pane>` | error envelope (`error.code: agent_name_taken`), exit 1, while another pane held the name |

## Environment

`HERDR_PANE_ID` is set in the environment of every herdr pane (`HERDR_ENV=1` too) and
holds the pane's own id in the shape `agent list` reports (`w<workspace>:p<pane>`):
`restart-idle` reads it as "the pane running the command" and never restarts it. Read
live from a pane's shell, 2026-10-06.

## Probe outcome (decides spec §A step 3)

- After `/exit` the pane drops out of `agent list` (the agent registration, name
  included, is released), and `agent start <same name> --kind claude --pane <same pane>
  -- --resume <id>` is ACCEPTED (`agent-start-reuse.json`): same `agent_session.value`,
  same name, argv `["claude","--resume","<id>"]`. So the named path works and is primary.
- herdr refuses a name only when ANOTHER pane still holds it (`agent_name_taken`). That
  refusal is the fallback trigger (send-text) the engine handles.
- A `--resume` needs a transcript: a session that never took a turn has none.
- Findings that corrected the spec: `← N agent` appears in the status line of every
  idle session, fresh ones included (it never changed with a running subagent), so it
  is not background-work evidence; `N shells` / `N monitors` and the agent panel are.
  herdr also reports `done`, not `idle`, for a pane with background work and a settled
  turn. While a draft is typed, the status line's trailing hint segments disappear and
  herdr still says `idle`, which is why a draft cannot be read from the status.

## Not live-captured

Claude's exit dialog ("You have 1 unsent feedback draft · Enter to review & send · Esc
to discard and exit") is quoted from super-fr#964's live report; an unsent feedback
draft is not reproducible without sending the operator's feedback, and no fixture of it
exists. The engine matches those phrases in the visible text.
