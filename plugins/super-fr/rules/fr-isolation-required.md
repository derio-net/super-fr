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
