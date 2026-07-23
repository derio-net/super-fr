<!-- super-fr:rules START -->

# fr-isolation Required — Edit/Write Enforcement (Org-Wide)

## Rule

In an **fr-enabled** repo, edits to tracked source/docs must happen **inside an
fr-isolation workspace**, never the base clone. This is enforced by the
PreToolUse hook `fr-isolation-required.sh` (shipped by super-fr, registered via
the plugin's `hooks.json`), which gates **Edit / Write / MultiEdit /
NotebookEdit** — you can't commit what you can't write.

A repo is **fr-enabled** when it has a `.devcontainer/<profile>/` profile or a
`docs/superpowers/plans/` directory.

## Why

fr-isolation used to be prose ("fr-brainstorming / fr-goal enter isolation
first, so the base repo is never touched"). Prose gets bypassed under load: a
session enters isolation for the brainstorm, then *wanders* — follow-up edits in
another repo, later turns, host-side chores — all landing on the **base clone**
with no gate forcing re-entry. This hook is the tool-layer backstop, mirroring
`agent-worktree-default.md` (Agent tool) and `fr-isolation-guard.sh` (Bash
tool). It is session-independent: it fires on any edit to an fr-enabled repo,
even when no pipeline skill ran this session.

## How it decides (fail-closed)

1. Not an edit tool, or `FR_BASE_OK=1` set → allow.
2. Target file not in a git repo, or repo not fr-enabled → allow.
3. **Valid `.fr-isolation` marker at the repo toplevel → allow.** Valid =
   present, recorded `toplevel` == the file's actual toplevel, and (mode
   `worktree`) the toplevel is a real **linked worktree**
   (`git rev-parse --git-common-dir` ≠ `--git-dir`). The linked-worktree check
   is what defeats a stale marker copied into the primary working tree.
4. Path matches a glob in `.fr-isolation-allow` (below) → allow.
5. Otherwise → **deny** with a message naming the three ways forward.

`fr isolation up` writes the marker (and adds it to `info/exclude`); `down`
removes it. The marker is **never** committed — it is gitignored and a CI
tripwire fails if it is ever tracked.

## Escapes

- **Enter isolation** — `fr isolation up --branch <branch>` (or run fr-goal /
  fr-brainstorming / fr-debugging), then edit in the worktree. The right answer
  almost always.
- **`.fr-isolation-allow`** — a globlist at the repo root for operator-managed
  paths that legitimately live in the base clone (data, caches, memory).
  Matched against the file's repo-relative path; `*` spans `/`. Example:
  ```
  # operator-managed, base-clone edits allowed
  projects/**
  data/**
  context/**
  memory/**
  *.local.md
  ```
- **`FR_BASE_OK=1`** — a one-shot env escape for a deliberate base-clone edit
  (e.g. a quick host-side chore you accept is outside isolation).

## Rollout (two-file pattern)

Mirrors `agent-worktree-default.md`:

- This operator-level file installs to `~/.claude/rules/fr-isolation-required.md`
  (via super-fr's `install.sh`) and the hook auto-registers through the plugin.
- A repo-level mirror `.claude/rules/fr-isolation-required.md` lives in each
  fr-enabled repo for discoverability (it auto-loads in every clone, including
  pods — keep host-specific paths out of it).
- Each fr-enabled repo should gitignore `.fr-isolation` and carry the
  never-tracked tripwire.

## Plan Skill Override

When the brainstorming skill says to invoke `writing-plans`, invoke `fr-plan` instead.
When any skill references `superpowers:writing-plans`, use `fr-plan`.

## Autonomous Goal Override

When the operator asks for a feature to be built autonomously — /fr-goal,
/goal, "build this autonomously", "ask your questions once then build it",
"take this to a PR", "no approval gates", "auto mode" — invoke `fr-goal`
FIRST, before brainstorming. fr-goal wraps and sequences brainstorming,
fr-plan, and fr-execute with the operator's gate-waiving contract; starting
with plain brainstorming loses that contract and reintroduces the approval
pauses the operator explicitly waived.

## Brainstorming Override

In a repo with fr plans (`docs/superpowers/plans/`) or devcontainer profiles
(`.devcontainer/<profile>/`), feature brainstorms use `fr-brainstorming`
instead of plain brainstorming — it enters fr-isolation first, so the base
repo is never touched. Plain brainstorming remains for non-fr repos and
non-feature ideation.

## Debugging Override

In a repo with fr plans (`docs/superpowers/plans/`) or devcontainer profiles
(`.devcontainer/<profile>/`), debugging a bug, test failure, or unexpected
behavior uses `fr-debugging` instead of plain
`superpowers:systematic-debugging` — it enters fr-isolation first (reusing an
active workspace, else a fresh `fix/<slug>` branch), so the base repo is never
touched, and delivers the fix as a reviewed PR. Plain systematic-debugging
remains for non-fr repos and quick non-isolated checks.

## fr-* Skill Overview

For a condensed overview of the fr-* skills and their CLI subcommands, run `fr skills`.

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

<!-- super-fr:rules END -->
