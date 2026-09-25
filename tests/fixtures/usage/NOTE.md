# Usage reader fixtures — provenance

Fixtures for `fr.usage.readers` (spec
`2026-09-25-lean-cost-aware-process-design.md` §5.A, Test Plan item 1). Each is
a capture of the real thing or is built from the harness's live/documented
schema by a committed script — never composed alongside the parser.

## claude-code/

Captured live 2026-09-25 from this operator's own Claude Code transcripts of the
super-fr repo: session `145101c9-bdfc-4f5d-a8be-617eeced7485` (a 2026-09-21
holder-proof run) — the main `<session>.jsonl` and ONE of its two subagent
streams, `subagents/agent-af7cb1e9fc08366c6.jsonl` + `.meta.json`.

Redacted at capture time per `.claude/rules/third-party-privacy.md`:

- **kept byte-exact:** record `type`, `uuid`, `timestamp`, `sessionId`,
  `isSidechain`; `message.{model,id,type,role,stop_reason,usage}` (the whole
  usage block, `iterations` included); every `cost-state` record unchanged;
  `tool_use.{id,name}`; the subagent meta's `agentType`/`toolUseId`/`model`.
- **replaced:** every free-text payload — assistant text, thinking (signature
  emptied), user prompts and tool results (`<redacted N chars>`), attachments
  and other record types (reduced to `type`/`uuid`/`timestamp`/`sessionId`),
  the meta `description`.
- **tool_use inputs** keep only `command`, `file_path`, `path`,
  `subagent_type`, `pattern` (what the classifier reads); commands over 400
  characters are truncated; the home directory is rewritten to `~` and the
  account name to `operator`; any URL not on `github.com/derio-net` becomes
  `https://example.invalid/`.

The deliberately duplicated `message.id` records (one per content block) are
preserved: they are what the dedupe test exercises.

| file | sha256 |
|---|---|
| `claude-code/145101c9-bdfc-4f5d-a8be-617eeced7485.jsonl` | `173d8b3fb20514c06294f6c88a9cc8685e1622b2977e896fdd0b36dde601e991` |
| `claude-code/145101c9-bdfc-4f5d-a8be-617eeced7485/subagents/agent-af7cb1e9fc08366c6.jsonl` | `21bfb67b2070c3cbb42617a7008fbd988d55755831acfdae0a750f96b72bd8e3` |

## opencode/

`opencode.db` is built by `opencode/build.py` (committed; rerun it to
regenerate). Its DDL is the subset of the **live** OpenCode schema the reader
touches, copied from a 2026-09-25 `sqlite3 .schema` of this operator's own
`~/.local/share/opencode/opencode.db` (columns never read are omitted; names and
types verbatim); the `message.data` / `part.data` JSON follows live rows of the
same capture. Rows are fictional: `ses_paid` (one paid assistant message with a
`bash` tool part), `ses_free` (one `$0` free-model message), `ses_copilot` (one
`github-copilot`-routed message whose non-zero `cost` is OpenCode's own estimate;
providerID and figures copied from a live row of the same capture) and
`ses_mixed` (one `anthropic` + one `github-copilot` message).

## hermes/

`state.db` is built by `hermes/build.py` from `hermes/schema.sql`, a verbatim
copy of the `sessions`, `messages` and `session_model_usage` tables of
NousResearch/hermes-agent `hermes_state_common.py` `SCHEMA_SQL` (commit
`a3a85a3143a54305cafd79065a22de5b51395027`, `SCHEMA_VERSION = 30`). No Hermes
host was available, so the rows are **constructed against that schema**, and the
`messages.tool_calls` JSON assumes the OpenAI chat-completions shape — a stated
assumption, not a capture. Includes an ACP-style session with zero tokens
(hermes-agent#6775).

| file | sha256 |
|---|---|
| `opencode/opencode.db` | `33f89d0a29eefcbb3a3cb97013cd1b81b3493283c372486888f28e450c3bc25b` |
| `hermes/schema.sql` | `342e5bfaf785b6a9281de19d9296b3199f04fb98a723c54abf39454c1ecdd4a7` |
| `hermes/state.db` | `46a42617cd2774d0a9a0bdaddb430b004c5b6e7bff352ab52e7b27387ac602be` |
