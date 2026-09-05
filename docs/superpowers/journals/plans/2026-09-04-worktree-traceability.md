# Journal: 2026-09-04-worktree-traceability

<!-- fr:journal kind=decision scope=plan id=d1-binding-location created=2026-09-05T20:14:53 -->
### d1-binding-location · decision · d1: binding = fr state + per-session index, never the sentinel

IsolationState.sessions is the source of truth; ~/.cache/fr/sessions/<session_id>.json (FR_SESSIONS_DIR override) is a derived index. NOT the pipeline sentinel: its PRESENCE arms fr-isolation-guard.sh.

<!-- fr:journal kind=decision scope=plan id=d2-worktreecreate-sessions-only created=2026-09-05T20:14:54 -->
### d2-worktreecreate-sessions-only · decision · d2: WorktreeCreate makes fr own SESSION worktrees only

claude --worktree / EnterWorktree / desktop sessions -> fr isolation up --session --print-path, branch wt/<name> unless the name has a slash. agent-* names reproduce Claude default: <repo>/.claude/worktrees/<name>, detached at origin/HEAD else HEAD. A registered hook cannot decline, so every path prints a path or exits 1.

<!-- fr:journal kind=decision scope=plan id=d3-repo-key created=2026-09-05T20:14:54 -->
### d3-repo-key · decision · d3: fr cache keyed on the MAIN checkout basename

repo_cache_name() resolves via the git common dir (<main>/.git -> main basename; fallback repo_root.name). Existing workspaces unaffected: state stores absolute paths.

<!-- fr:journal kind=decision scope=plan id=d4-statusline-format created=2026-09-05T20:14:55 -->
### d4-statusline-format · decision · d4: status line format

Line 2 = branch | full cwd | iso: <full bound worktree>. Line 3 = other worktrees as branch:rel (rel to main checkout when cwd is inside it, else ~-relative). Segment script: shell+jq+git only, never the fr CLI (measured 4.2 s).

<!-- fr:journal kind=discovery scope=plan id=disc-multi-workspace-exec created=2026-09-05T20:14:55 -->
### disc-multi-workspace-exec · discovery · Every exec needs --branch feat/worktree-traceability

super-fr has several fr workspaces on this host; bare fr isolation exec errors with multiple isolation workspaces. Devcontainer profile=dev, container running; worktree mounted at /workspaces/feat__worktree-traceability inside the container.

<!-- fr:journal kind=discovery scope=plan id=disc-bind-no-success-check created=2026-09-05T20:14:56 -->
### disc-bind-no-success-check · discovery · Bind hook does not check Bash success

An attach after a failed up finds no state and is a harmless no-op (attach errors, hook exits 0). No CLAUDE_SESSION_ID env var exists for the Bash tool; only hooks receive session_id.
