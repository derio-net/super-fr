# Claude Code transcript fixtures — capture note

Captured live 2026-09-20 from two real Claude Code transcript files in this
operator's own `super-fr` project directory (`derio-net/super-fr`, no
third-party repo involved):

- `claude-code-session.jsonl` — 9 records selected from an orchestrator
  session's own `<session-id>.jsonl`
- `claude-code-subagent.jsonl` — 3 records selected from one of its dispatched
  `super-fr:fr-phase-executor` subagents
- `claude-code-subagent.meta.json` — that subagent's companion metadata file,
  captured whole

**Two transcript files, not one.** An earlier draft of this fixture merged all
12 records into a single `.jsonl`. That was wrong and was corrected in the
phase-1 review: no file the harness writes contains both `isSidechain: true`
and `isSidechain: false` records — that is precisely the finding below. A
merged fixture would have been a shape the harness never emits, and a phase-4
parser written against it would pass its tests while reading zero subagent
tokens from every real transcript on disk.

## Where these live on a real machine

```
~/.claude/projects/<cwd-slug>/
    <session-id>.jsonl                                  # the orchestrator stream
    <session-id>/
        subagents/
            agent-<agentId>.jsonl                       # one per dispatched subagent
            agent-<agentId>.meta.json                   # its companion metadata
```

Note the per-session **directory** sitting beside the `<session-id>.jsonl`
file, and that the metadata file is `agent-<agentId>.meta.json` — not a bare
`meta.json`. A glob written from a wrong reading of this finds nothing.

## What was selected

Whole records only, by line index, never edited in shape:

- from the orchestrator stream: `last-prompt` (line 0), two `user` records,
  two `assistant` records carrying `message.usage`, one `system` record
  (`turn_duration`, carrying `cwd`/`gitBranch`/`sessionId`/`version` but no
  usage), the `assistant` record whose `Agent` tool_use `id` matches the
  subagent's metadata `toolUseId`, and the `mode` / `permission-mode` /
  `atis-latch` records — which are **near the end** of the source file (lines
  980–982 of 984), not session-start metadata despite their names;
- from the subagent stream: the dispatch prompt, a `thinking` turn, and the
  final turn (`isSidechain: true` throughout).

## Redaction (per `.claude/rules/third-party-privacy.md`)

The operator's absolute home path was replaced with `/home/user`, and the bare
username wherever it appeared outside that path with `user`. The strings
themselves are deliberately not quoted here, and the companion test asserts the
*property* — that no real macOS home path survives and no unexpected
`/home/<name>` appears — rather than naming them. Naming them in a public
repo's source would reintroduce exactly what the redaction removed, and the
test scans this note too, so even the explanation has to obey the rule.

Two candidate records carrying a **third-party** client path (an `environment`
attachment's `additionalWorkingDirectories`, naming an employer and a client
outside the `derio-net` org) were **excluded from the selection entirely**
rather than redacted in place, since they added nothing the assertions need.

**Method, stated accurately:** each selected record was parsed, redacted and
re-serialized with Python's `json.dumps`. JSON whitespace therefore differs
from the source bytes (the harness emits compact separators); object content
is unchanged, and every record canonicalises equal to its source record. An
earlier version of this note called it a pure substring replacement, which the
artifact itself disproves.

## What the shape turned out to be — findings, not smoothed over

Recorded in the plan journal (`fr journal add --scope plan --phase 1`) as part
of P1.T2; summarized here because it directly contradicts §2 and §5.C of the
spec, and phase 4 depends on the corrected version.

1. **Subagent turns are NOT interleaved in the orchestrator's own session
   file.** Every record in the orchestrator stream carries
   `isSidechain: false` (or omits it); `isSidechain: true` appears only in the
   separate per-agent file. §5.C's B1 ("attributed by walking `parentUuid` back
   to the `Agent` tool_use that started it") assumes one shared stream. The
   real correlation is file-to-file, via the orchestrator's `Agent` tool_use
   `id` matching the subagent's `agent-<agentId>.meta.json` `toolUseId`;
   `parentUuid` inside the subagent file chains only that subagent's own turns
   and starts at `null`.
2. **`sessionId` is shared, not per-agent.** A subagent record's `sessionId` is
   the *orchestrator's*. The subagent's own identity is `agentId`, a field
   absent from orchestrator records.
3. **`cwd` reflects the harness's launch directory, not the worktree the agent
   worked in.** The captured subagent was dispatched with instructions to `cd`
   into an fr-isolation worktree and did all its work there, yet every one of
   its records carries the orchestrator's base-clone launch path. A V2 reader
   cannot use `cwd` to tell which worktree or phase a record belongs to.
4. **`message.usage` carries far more than the four columns §2 names.**
   `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens` and
   `output_tokens` are always present (§2 holds), but the object also carries
   `cache_creation` (a nested `ephemeral_5m`/`ephemeral_1h` breakdown),
   `output_tokens_details`, `server_tool_use`, `service_tier`, `inference_geo`,
   `speed`, and sometimes an `iterations` list repeating a subset of the same
   fields. A V2 parser must **project** onto the four named keys rather than
   assume the object's shape.
5. **A session file interleaves many record types with no usage** —
   `last-prompt`, `mode`, `permission-mode`, `atis-latch`, `attachment`,
   `file-history-snapshot`, `file-history-delta`, `system`, `queue-operation`
   were all observed. A V2 parser must select on `type == "assistant"` before
   reading `message.usage`.
6. **The metadata file also carries `agentType` and `model`.** So the tier
   binding a dispatch actually used is recoverable from the transcript without
   asking the harness anything — useful to `fr models` reporting, beyond
   telemetry.
