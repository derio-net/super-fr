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

<!-- fr:journal kind=discovery scope=plan id=fa98d868720c created=2026-09-05T20:25:35 phase=1 -->
### fa98d868720c · discovery · fr.isolation.sessions API as shipped in phase 1 (phase 1)

Module packages/fr/src/fr/isolation/sessions.py. Signatures: sessions_dir() -> Path (FR_SESSIONS_DIR override, default ~/.cache/fr/sessions); session_index_path(session_id) -> Path (IsolationError on empty, '/', '.', '..'); read_session_index(session_id) -> dict|None; attach(repo_root, branch, session_id, harness='unknown') -> IsolationState (idempotent, single binding per session, moves across repos via the index); detach(session_id, repo_root=None, branch=None) -> list[str] branches detached, [] when none; detach_all(state) -> list[str] session ids; stale_session_indexes() -> list[tuple[Path, dict]] (pure; unparseable files come back with {}). types.py: SessionBinding(session_id, harness='unknown', attached_at) frozen; IsolationState.sessions: list[SessionBinding] default []. Index JSON keys: session_id, harness, repo_root, branch, worktree, profile, attached_at (attached_at is datetime.now(UTC).isoformat(), i.e. +00:00 suffix, not Z). CLI: fr isolation attach --session --repo --branch --harness; detach --session [--repo --branch]; status --session <id> filter plus sessions=<ids|none> text column and sessions: [{session_id,harness,attached_at}] in json; up --session --harness; down --session (excluded from the still-attached warning). Shared resolver _resolve_single(root, branch) in isolation_cmd.py now backs exec, restart, down and attach (verify-merge still has its inline copy).

<!-- fr:journal kind=discovery scope=plan id=7656ab55c62c created=2026-09-05T20:25:42 phase=1 -->
### 7656ab55c62c · discovery · Deviation: down detaches sessions AFTER a successful teardown, not before (phase 1)

The plan text placed _sessions.detach_all(state) before _target(root).down(). That drops bindings even when down is refused (open PR without --force) and the workspace survives, contradicting spec 5.A ('detaches all sessions of the workspace it removes'). Shipped order: warn about other sessions -> target.down -> detach_all only on success (same in _down_all: kept workspaces keep their bindings). To make that safe, detach_all only rewrites the state file when it still exists (state_path(...).is_file()), so it never resurrects a retired workspace with sessions=[]. Pinned by test_down_refused_by_open_pr_keeps_bindings in tests/unit/test_isolation_sessions_cmd.py. Consequence for later phases: after down, the index files are gone and there is no state file to consult, so gc/statusline must not assume an index exists for a session that ran down.

<!-- fr:journal kind=discovery scope=plan id=69dd98f5bdd8 created=2026-09-05T20:25:48 phase=1 -->
### 69dd98f5bdd8 · discovery · Test-fixture notes for the CLI binding surface (phase 1)

tests/unit/test_isolation_sessions_cmd.py pins FR_ISOLATION_TARGET=worktree (host mode, no docker, no profile gate) for every test and sets FR_SESSIONS_DIR under tmp_path. Its fake_run returns rc=1/empty stdout for gh, which _pr() maps to 'no PR' (so down proceeds); the open-PR refusal test uses its own runner returning state OPEN. Host-mode up works on a repo with no origin (fetch degrades to HEAD). The existing tests/unit/test_isolation_cmd.py only asserts substrings of the workspace-resolution messages, so unifying exec/restart/down on _resolve_single changed down's branch-given message from 'no isolation workspace for branch X.' to '... — run fr isolation up first.' without breaking anything. The gc phase can rely on sessions.stale_session_indexes() being pure and on detach_all being a no-op writer when the state file is absent.
