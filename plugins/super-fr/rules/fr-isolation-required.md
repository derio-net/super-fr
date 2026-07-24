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

## Rollout (two-file pattern)

Mirrors `agent-worktree-default.md`:

- This operator-level file installs to `~/.claude/rules/fr-isolation-required.md`
  (via super-fr's `install.sh`) and the hook auto-registers through the plugin.
- A repo-level mirror `.claude/rules/fr-isolation-required.md` lives in each
  fr-enabled repo for discoverability (it auto-loads in every clone, including
  pods — keep host-specific paths out of it).
- Each fr-enabled repo should gitignore `.fr-isolation` and carry the
  never-tracked tripwire.
