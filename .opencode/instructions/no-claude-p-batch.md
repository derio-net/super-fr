# Never `claude -p` for batch LLM work (Org-Wide)

## Rule

**Never use `claude -p` (print mode) for batch / per-element operations.** Each
invocation **cold-starts a full Claude Code session** — system prompt, tools,
MCP, skills, and memory reload on every call. Measured (2026-06-20):
**~22k input tokens, ~$0.37, ~5s per call**. For N elements that is N
cold-starts; the cost and latency blow up, and it is *more* expensive than a
direct Haiku API call.

A single interactive / one-off `claude -p` is fine. Batch is the failure mode.

## Use instead (in order)

1. **One persistent agent session**, fed each element as a successive turn —
   warm context, prompt-cache reuse across elements.
2. **Subagent fan-out** for parallelism — each subagent is *one* warm session,
   not N cold-starts.
3. **Batch K elements per prompt** when a session isn't available.

Then **clean up** (close sessions / agents you opened).

## The deeper principle

**Separate the engine from the LLM transport.** The engine is deterministic ops
plus a per-item protocol (what one element's prompt and parsing look like). The
transport is how those calls are batched and warmed. Never bake
`claude -p`-per-call into an engine — that fuses the two and makes batch cost
structural. Keep the per-item protocol pure so the transport can be a persistent
session, a subagent pool, or a batched prompt without touching the engine.

## Why this is a super-fr rule

fr-* flows routinely orchestrate batch LLM work (dedup / maintain, distillation,
enrich triage, per-topic report agents). Discovered building brain-fr's
`ClaudeCliJudge` (one `claude -p` per dedup pair). super-fr's own packages never
shell out to `claude -p`, and a CI tripwire
(`tests/unit/test_tripwire_claude_p.py`) fails if they ever start — enforcement,
not just this prose.
