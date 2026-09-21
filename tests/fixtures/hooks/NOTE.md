# Harness hook inputs — captured, never constructed

What a harness REALLY hands a hook on stdin, captured from the installed binary.
They exist because `fr-run-idle-guard.sh` (spec
`2026-09-20-unit-record-unification-design.md` §4.G) keys on fields the spec
first asserted from memory — and this repo's standard (gh#494) is *verified on
the installed binary, not from docs*.

**Do not edit these files.** `tests/integration/test_run_idle_guard.py` pins each
file's SHA-256 to the table below.

## Capture

Claude Code **2.1.278**, macOS, 2026-09-21. One headless turn
(`claude -p … --settings <file> --tools "" --model haiku`), with a `Stop` hook
registered through `--settings` whose command appended its stdin to a file and —
on the first stop only — printed
`{"decision": "block", "reason": "PROBE: before stopping, reply with exactly the single word: again"}`
and exited 0. The session replied `ok`, was blocked, replied `again`, and
stopped. Both hook inputs are here, in order.

| file | SHA-256 | what it is |
|---|---|---|
| `claude-code-stop.json` | `ed8dc5d7472cd63bbf35a49ff82c3b63f04fcb0a51d3ba0eb5d32aa3b2ac17e0` | the first `Stop` of a turn: `stop_hook_active: false` |
| `claude-code-stop-after-block.json` | `b9fb043de118d2dae6ba775033241c674a52a951ca362710c448d7c0c7026b9b` | the `Stop` of the continuation that block caused: `stop_hook_active: true` |

**Redaction, stated rather than hidden** (`.claude/rules/third-party-privacy.md`):
the operator's home-directory name was replaced with `operator` in
`transcript_path` and `cwd`, by text substitution over the captured line. Nothing
else was touched — key order, spacing and every other value are as the binary
wrote them. The session id is a throwaway UUID.

## What this capture proves, and what it does not

Proves, on this binary:

- the input carries `session_id`, `transcript_path`, `cwd`, `prompt_id`,
  `permission_mode`, `hook_event_name: "Stop"`, **`stop_hook_active`** (a JSON
  boolean), `last_assistant_message`, **`background_tasks`** and
  `session_crons` (both `[]` here);
- `{"decision": "block", "reason": …}` on stdout with exit 0 **does** stop the
  turn from ending, and the reason reaches the model;
- the next `Stop` carries `stop_hook_active: true`.

Read from the binary's own schema (`strings`-level inspection, not exercised):
`background_tasks` is *"in-flight background work … lets hooks distinguish
'session is done' from 'session is paused waiting for background work to wake
it'"*, and the binary caps consecutive Stop-hook blocks itself
(`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`, default 8).

Does NOT prove: that a hook registered through a **plugin's `hooks.json`**
receives the same input (this one came in through `--settings`); what
`background_tasks` looks like while a background subagent really is running;
anything about an interactive session. Those are the operator's Test Plan
item 17.
