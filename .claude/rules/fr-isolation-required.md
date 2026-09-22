# fr-isolation Required — repo mirror

In this fr-enabled repo, edits to tracked source/docs belong **inside an
fr-isolation workspace**, never the base clone. A super-fr edit gate enforces
this: it allows the edit only when a valid `.fr-isolation` marker sits at the
repo toplevel, checked by the marker's `mode`:

- `worktree` (devcontainer or host-worktree mode) → toplevel must be a real
  linked worktree.
- `external` (preparer-adopted container) → toplevel match **plus** container
  evidence (`/.dockerenv`, `/run/.containerenv`, or `$KUBERNETES_SERVICE_HOST`),
  so a marker forged on a bare host or copied to the base clone never validates.

**Harness — edit gate:** Claude Code runs it as the PreToolUse hook
`fr-isolation-required.sh` on Edit / Write / MultiEdit / NotebookEdit. OpenCode
runs it as the `fr-opencode-plugin` `tool.execute.before` plugin on the `edit` /
`write` / `patch` / `multiedit` tool calls (not `bash` — a known gap, not a
sanctioned bypass). Hermes
runs it as a `pre_tool_call` hook on `write_file` / `patch`, installed by
`fr hermes install`.

`fr isolation up` selects the mode (`FR_ISOLATION_TARGET=worktree` for a
docker-less host; a preparer-written `external` marker is adopted as-is) and
writes the marker; devcontainer mode is the default.

**Scope.** fr-isolation answers one question — *is this fr work happening in an
fr-enabled repo's base clone instead of its workspace?* — and is silent on
everything else. Not in a git repo, or not fr-enabled → allowed. It is **not** a
filesystem sandbox or a credential boundary: `~/.ssh`, `~/.aws` and friends are
outside its scope (including when `$HOME` is a dotfiles git repo, which is not
fr-enabled), and a session with no active pipeline sentinel is ungated by the
bash guard entirely. Protecting those paths is the harness permission layer's
job (`permissions.deny` in `~/.claude/settings.json`), not fr's. Session
bindings (`fr isolation attach`, `up --session`) are traceability for the edit
gate — it reads the marker, never a binding. The Bash guard is the exception:
binding adds the workspace to the session's pipeline sentinel, and the guard
heals (retires) a sentinel only once every workspace it lists is gone, so a
session that never bound stays armed after its workspace is reaped.

To work here:

- Enter isolation — `fr isolation up --branch <branch>` (or run fr-goal /
  fr-brainstorming / fr-debugging) and edit in the worktree.
- For base-clone paths that are operator-managed (data, caches, memory), list
  them in `.fr-isolation-allow` at the repo root (`*` spans `/`).
- For a deliberate one-off base edit, set `FR_BASE_OK=1`.

**Carve-out — `fr-phase-executor` must NOT get its own worktree.** The org
`agent-worktree-default` convention says every code-writing subagent gets its
own worktree; this one agent is the exception, because fr-goal §5 runs phase executors serially *inside the
fr-isolation worktree that already exists* — that worktree IS their isolation,
and the two mechanisms don't compose. Given one, the executor wakes in a
fresh worktree cut from `main` where the spec/plan are invisible and every
Bash/Edit call is denied, yet the dispatch succeeds, so the run looks healthy
while nothing happens (super-fr#420). fr-goal §2 is the opposite case — its
cross-repo agents each start a fresh pipeline in a different repo, in a
workspace of their own.

**Harness — subagent worktree:** On Claude Code the second worktree is the Agent
tool's `isolation: "worktree"` argument: dispatch the executor without it, and
`fr-phase-executor-guard.sh` refuses it if you do not. OpenCode's task tool and
Hermes' `delegate_task` take no isolation argument, so there is nothing to
refuse: dispatch the executor as any subagent, into the existing workspace.

`.fr-isolation` is gitignored and must never be committed (a CI tripwire
enforces this). Full rationale and the operator-level install live in the
shipped rule `~/.claude/rules/fr-isolation-required.md` (super-fr). This mirror
is intentionally host-neutral so it is safe to auto-load in every clone,
including devcontainer pods.
