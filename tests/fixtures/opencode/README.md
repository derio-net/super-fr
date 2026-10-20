# OpenCode 2 store fixture — provenance

`two-sessions.db` is BUILT by `build.py` (re-run it after editing; the file is
committed). It pins the shape `fr` reads (spec
`2026-10-20-opencode-2-support-design.md` R13, R14):

- **Shape, captured live, identity redacted.** The DDL of `session_v2`,
  `session_message`, `session`, `message` and `part` is verbatim from a
  2026-10-20 `.schema` of a live OpenCode 2.1.0 store, read from a read-only
  copy. The `data` JSON shapes (`content[]` items `reasoning`/`text`/`tool`, a
  tool item's `id`/`name`/`time.{created,ran,completed}`/
  `state.{status,input,metadata,content[]}`, an assistant message's
  `agent`/`model.{id,providerID,variant}`/`cost`/`tokens`) follow live rows.
  Every directory (`/home/u/...`), title, prompt, model, provider and figure is
  fictional.
- **`ses_v2demo`** — a 2.x session: a user message; an assistant message with
  `skill`, `question` (answered), `shell` (exit 0) and `subagent` tool items,
  `cost` 0.0123 and full `tokens`; a second assistant message carrying a
  migrated 1.x tool name (`bash`), `cost` 0 (an integer, as live rows have).
- **`ses_v2child`** — its subagent child (`parent_id` = `ses_v2demo`), one
  assistant message with a final text item, `cost` 0.002.
- **`ses_v1only`** — a 1.x session present ONLY in the legacy
  `session`/`message`/`part` tables: what `v1-only` means.

`tests/unit/test_opencode_store_fixture.py` asserts the tables and columns
the readers query exist here, so a later store change fails there first.
