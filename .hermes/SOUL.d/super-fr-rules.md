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
`agent-worktree-default.md` (Agent tool — but see the `fr-phase-executor`
carve-out below) and `fr-isolation-guard.sh` (Bash tool). It is
session-independent: it fires on any edit to an fr-enabled repo, even when no
pipeline skill ran this session.

## How it decides (fail-closed)

1. Not an edit tool, or `FR_BASE_OK=1` set → allow.
2. Target file not in a git repo, or repo not fr-enabled → allow.
3. **Valid `.fr-isolation` marker at the repo toplevel → allow.** Valid =
   present, recorded `toplevel` == the file's actual toplevel, **and** the
   marker's `mode` passes its own check:
   - `worktree` (devcontainer **or** host-worktree mode — an fr linked
     worktree either way) → the toplevel must be a real **linked worktree**
     (`git rev-parse --git-common-dir` ≠ `--git-dir`). Defeats a stale marker
     copied into the primary working tree.
   - `external` (preparer-adopted container) → the toplevel match **plus
     container evidence** — any of `/.dockerenv`, `/run/.containerenv`, or
     `$KUBERNETES_SERVICE_HOST`. A marker forged on a bare host never
     validates; a marker copied to the Mac base clone fails the toplevel match
     (the container checkout path can't equal the base-clone path).
   - any other `mode` → fail closed.
4. Path matches a glob in `.fr-isolation-allow` (below) → allow.
5. Otherwise → **deny** with a message naming the three ways forward.

`fr isolation up` writes the marker (and adds it to `info/exclude`); `down`
removes it. The marker is **never** committed — it is gitignored and a CI
tripwire fails if it is ever tracked.

## Three isolation modes

The marker's `mode` records who owns the environment; the edit-gate only cares
that the workspace is a genuine isolation, per the checks above.

- **devcontainer** (default, operator machines): fr linked worktree +
  devcontainer + secrets env-file. Marker `mode: worktree`.
- **host-worktree** (`FR_ISOLATION_TARGET=worktree`, docker-less pods/CI): fr
  linked worktree, the host process env as-is, no profile, no fr-provisioned
  secrets. Marker `mode: worktree` — same enforcement surface as devcontainer.
- **external** (`mode: external`): the **preparer** (k8s operator, image build,
  attach script) writes the marker itself at its checkout toplevel — the
  hand-off artifact whose meaning is "this container is contained and prepared
  for fr." `fr isolation up --branch` adopts it (no second isolation). Container
  evidence in the hook is corroboration only, never a trigger: an unprepared
  container is never silently treated as isolated.

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

## Carve-out: `fr-phase-executor` must NOT get its own worktree

The org convention `agent-worktree-default.md` says every code-writing subagent
is dispatched with `isolation: "worktree"`. **`fr-phase-executor` is the one
exception, and it is a hard one** (super-fr#420):

- fr-goal §6 dispatches phase executors **serially into the fr-isolation
  worktree that already exists** — that worktree *is* their isolation. A second
  one is not extra safety, it is a different repo state.
- Given the flag, the executor wakes in a fresh worktree cut from `main`: the
  spec and plan live on the feature branch and are invisible, so `fr pickup` is
  unsatisfiable; Bash is denied by `fr-isolation-guard.sh`; and Edit/Write is
  denied by *this* rule's gate, because a fresh checkout has no marker and the
  gate is fail-closed. **The dispatch still succeeds**, so the run looks healthy
  while every phase does nothing.
- The reason is *not* "this agent is read-only" — it writes code. It is that
  **the two isolation mechanisms are mutually exclusive, not composable.**

fr-goal §3 is the opposite case and keeps the flag: those agents each start a
**fresh** pipeline in a **different** repo, so they need their own workspace.

Enforcement, not prose: `plugins/super-fr/hooks/fr-phase-executor-guard.sh`
(PreToolUse, `Agent|Task`) refuses the combination outright. Harnesses without
an `isolation` argument on their dispatch tool — Hermes' `delegate_task`,
OpenCode — cannot express the poisoned shape and need no hook.

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
