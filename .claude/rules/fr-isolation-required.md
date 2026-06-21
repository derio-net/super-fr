# fr-isolation Required — repo mirror

In this fr-enabled repo, edits to tracked source/docs belong **inside an
fr-isolation workspace**, never the base clone. A super-fr PreToolUse hook
(`fr-isolation-required.sh`) enforces this on Edit / Write / MultiEdit /
NotebookEdit: it allows the edit only when a valid `.fr-isolation` marker sits
at the repo toplevel and that toplevel is a real linked worktree.

To work here:

- Enter isolation — `fr isolation up --branch <branch>` (or run fr-goal /
  fr-brainstorming / fr-debugging) and edit in the worktree.
- For base-clone paths that are operator-managed (data, caches, memory), list
  them in `.fr-isolation-allow` at the repo root (`*` spans `/`).
- For a deliberate one-off base edit, set `FR_BASE_OK=1`.

`.fr-isolation` is gitignored and must never be committed (a CI tripwire
enforces this). Full rationale and the operator-level install live in the
shipped rule `~/.claude/rules/fr-isolation-required.md` (super-fr). This mirror
is intentionally host-neutral so it is safe to auto-load in every clone,
including devcontainer pods.
