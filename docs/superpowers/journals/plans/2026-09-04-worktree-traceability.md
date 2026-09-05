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

<!-- fr:journal kind=discovery scope=plan id=bd5b6af94c03 created=2026-09-05T20:34:49 phase=2 -->
### bd5b6af94c03 · discovery · repo_cache_name is belt-and-braces: Target.__init__ already normalizes to the main checkout (phase 2)

The Task 1 RED test for up-from-inside-agent-worktree passed as soon as repo_cache_name existed, BEFORE _worktree_up_core was touched: LocalWorktreeDevcontainerTarget.__init__ already routes repo_root through _main_worktree_root (#292), so self.repo_root.name was already the main checkout basename for any Target instance. The plan's 'today it lands under agent-abc' only holds for code that bypasses __init__. The §5.C change to _worktree_up_core was applied anyway (explicit, survives a future __init__ change). repo_cache_name(repo_root) -> str lives in fr.isolation.types; falls back to Path(repo_root).name for non-git paths and non-'.git' common dirs. Later phases (WorktreeCreate hook, statusline) can rely on repo_cache_name for the cache folder name and on _main_worktree_root for the main toplevel.

<!-- fr:journal kind=discovery scope=plan id=05bf844fb7ea created=2026-09-05T20:40:14 phase=2 -->
### 05bf844fb7ea · discovery · gc hygiene sweeps as shipped: empty-repo-dir + stale-session run on every gc, after the workspace sweep (phase 2)

LocalWorktreeDevcontainerTarget.gc() now appends _sweep_empty_repo_dirs(dry_run) then _sweep_stale_sessions(dry_run) after _sweep_dangling_images; HostWorktreeTarget inherits both (no docker/git involved); ExternalTarget has its own read-only gc and is untouched. Semantics: empty-repo-dir = a direct child of ~/.cache/fr/worktrees that is a dir with NO subdirectories (stray files like .DS_Store do not make it live) -> shutil.rmtree; actions would-remove | removed | reap-failed, branch=None, worktree=<dir>. Consequence: after the last down of a repo, the next gc removes ~/.cache/fr/worktrees/<repo>/ itself (up re-mkdirs the parent), so nothing may assume the repo folder persists. stale-session = every (path, data) from sessions.stale_session_indexes(): worktree gone OR state no longer lists the session OR unparseable JSON (data={} -> worktree '?', branch None); action would-remove | removed, detail=<index path>. Ordering note: within one live gc the orphan sweep deletes a vanished worktree's state record first, then the session sweep still classifies its index as stale (worktree gone), so both actions appear for the same workspace. The CLI gc printer is generic (branch-or-worktree: verdict -> action (detail)) — no per-verdict switch needed. GcAction comment now lists all verdicts/actions. Statusline (phase 5) must tolerate a missing index for a session that ran down or was gc-pruned.

<!-- fr:journal kind=discovery scope=plan id=aa8ed079c1dc created=2026-09-05T20:48:35 phase=3 -->
### aa8ed079c1dc · discovery · Claude session bind/unbind hooks as shipped in phase 3 (phase 3)

plugins/super-fr/hooks/fr-session-bind.sh (PostToolUse, matcher Bash) and fr-session-unbind.sh (SessionEnd, no matcher) are registered in hooks.json; both are jq-only transports that shell out to the installed fr binary and exit 0 on every path (missing jq or fr, non-Bash tool, agent_id present, missing fields, nonexistent cd target). Bind parses ONLY the first line of tool_input.command, start-anchored: a leading cd <dir> (bare, double- or single-quoted, tilde-expanded) followed by && or ; folds into --repo as pwd -P of that dir resolved relative to cwd; without a cd, --repo is the payload cwd verbatim (not realpath-ed). Verbs: up|exec -> attach --session --repo [--branch] --harness claude; down -> detach --session (no --branch/--repo, since down already detached everyone). The verb regex requires whitespace or end after the verb, so fr isolation upgrade/status/gc never match. --branch is parsed from anywhere on the line and accepts --branch v, --branch=v, and quoted values. Unbind skips reason=resume only. The sed with the cd regex in double quotes needs the group refs spelled as double-backslash (\\2\\3\\4, \\6) or bash eats them - case (d) pins this. Test harness: tests/unit/test_hooks_session_bind.py uses a stub fr on PATH that appends its argv to FR_STUB_LOG; reuse that fixture pattern for the WorktreeCreate/WorktreeRemove hooks (phase 4). The Hermes hooks-sync tripwire did NOT fail: it only validates .hermes/config.snippet.yaml commands, it does not enumerate Claude hooks.

<!-- fr:journal kind=finding scope=plan id=d028f3cc945a created=2026-09-05T20:48:41 phase=3 state=open -->
### d028f3cc945a · finding [open] · Hermes has no session bind/unbind transport (phase 3)

The two new Claude hooks have no Hermes counterpart: .hermes/config.snippet.yaml was left unchanged and plugins/super-fr/hooks/hermes/ has no fr-session-bind or fr-session-unbind. Hermes sessions therefore never get a binding in IsolationState.sessions and fr isolation status --session cannot see them. Wiring a post_tool_call(terminal) bind and a session-end unbind in the Hermes snippet is a follow-up outside this plan; when it lands, add the registrations to the expected set in tests/unit/test_tripwire_hermes_hooks_sync.py.

<!-- fr:journal kind=discovery scope=plan id=62c39ba6fb84 created=2026-09-05T20:50:54 phase=3 -->
### 62c39ba6fb84 · discovery · Acceptance matrix has no hook/golden/rule level: LEVELS = unit, api, int, ui (phase 3)

fr.acceptance.model.LEVELS is ('unit', 'api', 'int', 'ui') and the validator rejects any other key under levels:, so the spec 8 level names 'hook', 'golden', and 'rule + tripwire' cannot be used verbatim. Phase 3 filed the hook-level test (tests/unit/test_hooks_session_bind.py, subprocess + stub fr) under int: on row session-workspace-binding and said so in the row notes. Phases 4 and 5 should do the same: WorktreeCreate/WorktreeRemove hook tests -> int:, statusline golden tests -> unit: (pure Python) or int: (subprocess), the rule + tripwire row -> unit: for the tripwire test. fr plan edit --complete-phase 3 did NOT warn about the row; the refs were extended proactively because the row notes promised it, then fr acceptance report --deterministic regenerated docs/acceptance/report_*.

<!-- fr:journal kind=discovery scope=plan id=d862b37c25b6 created=2026-09-05T21:04:19 phase=4 -->
### d862b37c25b6 · discovery · Exact stdout contract of fr isolation up --print-path (phase 4) (phase 4)

up --print-path guarantees only this: exit 0 and the LAST non-empty stdout line is str(state.worktree), the absolute worktree path (no trailing text, no ANSI). The human lines (isolation up: worktree=... profile=... branch=... and the CLAUDECODE /add-dir tip) move to stderr via typer.echo(err=print_path). Earlier stdout lines are NOT guaranteed empty: on a genuine cold start LocalWorktreeDevcontainerTarget._worktree_up_core prints the cold-start base log line (local.py, print(log_line, file=sys.stdout) unless it starts with WARNING) to stdout, so consumers must take the last non-empty line, never the whole output. fr-worktree-create.sh does exactly that: strips ANSI with sed, then awk NF{l=$0} END{print l}. Idempotence for an existing branch+worktree needed no new code: _git_worktree_add short-circuits, and the second call prints the same path. Errors still go through _fail (stderr, exit 2) so a failed up leaves stdout without a path; the hook treats a non-directory last line as failure (exit 1).

<!-- fr:journal kind=discovery scope=plan id=ec47de9e64d0 created=2026-09-05T21:04:19 phase=4 -->
### ec47de9e64d0 · discovery · down --worktree resolution and what the remove hook does when down refuses (phase 4) (phase 4)

New helper _resolve_by_worktree(worktree) in isolation_cmd.py: wt = worktree.resolve(); states = list_states(wt) if wt.is_dir() else []; matches on s.worktree.resolve() == wt; no match -> error: no isolation workspace at <wt> (exit 2). list_states keys on the git common dir, which resolves from inside the worktree, and _git_common_dir degrades to <path>/.git for non-git paths, so a bogus path yields [] rather than a traceback. When --worktree is given, --repo is ignored entirely (cwd may be anywhere, even deleted-adjacent) and --all is ignored; root = state.repo_root and the normal single-workspace teardown follows, including the phase-1 detach_all-after-success ordering. fr-worktree-remove.sh: worktree_path matching */.claude/worktrees/agent-* -> git worktree remove --force via the common dir (rm -rf fallback), fr never called; any other path -> fr isolation down --worktree <path> with stdout redirected to stderr (hook stdout stays empty). If down exits non-zero (open PR without --force, unknown path, no fr on PATH is a silent exit 0), the hook prints fr-worktree-remove: fr isolation down refused for <path>; workspace kept (see fr isolation status) to stderr and STILL exits 0 - Claude never sees a hook failure, the workspace and its bindings survive, and status shows it. The hook never rm -rf-s a non-agent path. Missing worktree_path -> exit 0, no side effects.

<!-- fr:journal kind=discovery scope=plan id=7bf132eac75a created=2026-09-05T21:04:20 phase=4 -->
### 7bf132eac75a · discovery · WorktreeCreate hook decision order, env export, and the test harness (phase 4) (phase 4)

fr-worktree-create.sh decision order: missing name/cwd -> exit 1; cwd not a git repo -> exit 1 with stderr ... is not a git repo (the only two hard failures before fr is consulted); name agent-* -> mimic_default; repo not fr-enabled (no docs/superpowers/plans and no .devcontainer/<profile>/) or no fr on PATH -> mimic_default for ANY name; else fr path. mimic_default = <toplevel>/.claude/worktrees/<name>, detached at origin/HEAD if it resolves else HEAD, idempotent (existing dir -> print and exit 0), git output to stderr. Branch = name if it contains a slash, else wt/<name>. If FR_ISOLATION_TARGET is unset AND there is no devcontainer profile the hook exports FR_ISOLATION_TARGET=worktree for the fr call and says so on stderr (host-worktree mode); a preset value is respected and a repo with a profile gets no export. The session flags are built with a bash array (args+=(--session id --harness claude)) instead of the ${session_id:+...} expansion, so a session id can never be word-split. Registered in hooks.json as top-level WorktreeCreate and WorktreeRemove entries with no matcher (jq --indent 2 preserved the file formatting; test_plugin_hooks pins both keys). Test harness tests/unit/test_hooks_worktree.py: the stub fr records argv to FR_STUB_LOG and FR_ISOLATION_TARGET to FR_STUB_LOG.env (separate file so the exact argv assertion in case (a) stays clean), creates the fake worktree under HOME/.cache/fr/worktrees/stub/<branch with / as __>, prints noise then the path; the fixture pops FR_ISOLATION_TARGET from the inherited env. The refusal test rewrites the stub with a trailing exit 2. Both hooks are shellcheck-clean (checked on the host; the devcontainer has no shellcheck). The Hermes hooks-sync tripwire again did not fire (it does not enumerate Claude hooks); Hermes has no WorktreeCreate equivalent, same gap as finding d028f3cc945a.

<!-- fr:journal kind=finding scope=plan id=a309fda69e5a created=2026-09-05T21:04:20 phase=4 state=open -->
### a309fda69e5a · finding [open] · mimic_default does not copy .worktreeinclude matches (phase 4) (phase 4)

Spec 5.B.3 says the agent-* default shape should also copy .worktreeinclude matches (git ls-files --others --ignored --exclude-standard filtered by the include patterns) best effort. The plan GREEN script omits it and so does the shipped fr-worktree-create.sh: an agent-* worktree created by the hook is a plain detached worktree without ignored files such as local .env or node_modules symlinks that Claude default would carry over. Low impact for super-fr (uv sync rebuilds .venv), but a follow-up if a repo relies on it.
