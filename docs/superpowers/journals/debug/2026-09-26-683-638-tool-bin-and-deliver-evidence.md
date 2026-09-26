# Journal: 2026-09-26-683-638-tool-bin-and-deliver-evidence

<!-- fr:journal kind=repro scope=debug id=e42699f33a0e created=2026-09-26T11:48:31 -->
### e42699f33a0e · repro · #683: test_install_bridge relinks the host's ~/.local/bin/fr into a pytest tmpdir

tests/integration/test_install_bridge.py sets UV_TOOL_DIR to tmp_path but not UV_TOOL_BIN_DIR, then runs `uv tool install --force … packages/fr`. uv resolves the executable dir as UV_TOOL_BIN_DIR > XDG_BIN_HOME > XDG_DATA_HOME/../bin > ~/.local/bin, so the fr entry point link lands in the real bin dir, and --force replaces the operator link. When pytest reaps tmp_path the link dangles. Observed on the host 2026-09-26 (issue body). install.sh --install-bridge itself only reads `uv tool dir`, never PATH, so the link is not even needed by the test.

<!-- fr:journal kind=root-cause scope=debug id=da566ebe529b created=2026-09-26T11:51:53 -->
### da566ebe529b · root-cause · #683: UV_TOOL_BIN_DIR not isolated in test_install_bridge

The test isolates the tool ENV (UV_TOOL_DIR) but not the tool BIN dir, so `uv tool install --force` relinks the real ~/.local/bin/fr (or $XDG_BIN_HOME/fr) into tmp_path. Nothing asserted the host link survives a suite run, so it regressed silently from 4.22.2 (#635).

<!-- fr:journal kind=repro scope=debug id=e2ef6178e8e8 created=2026-09-26T11:51:56 -->
### e2ef6178e8e8 · repro · #638: deliver tests= passes on OpenCode on file freshness alone

run_cmd._verify_tests_log -> telemetry.orchestrator_wrote_since returns None for every harness but claude-code (_this_session gates on detect_harness), and None means "unobservable": the gate then only checks mtime > unit open and records unobserved=tests. Run 2026-09-26-fix-models-opencode-noop-505 resolved deliver on an 8-line agent-written prose file reporting a failed test.

<!-- fr:journal kind=hypothesis scope=debug id=e7e0c5aa2856 created=2026-09-26T11:51:58 -->
### e7e0c5aa2856 · hypothesis · #638: OpenCode records enough to verify the log's writer

opencode.db `part` rows for tool=bash carry state.input.command, state.status, state.metadata.exit and state.time.{start,end} (ms); sessions carry parent_id (NULL = top-level, i.e. the orchestrator, not a task subagent). Confirmed by reading the local db schema and a live bash part (2026-09-26). No session-id env var reaches fr under OpenCode, so the reader scopes to top-level sessions active since the unit opened, instead of one session.

<!-- fr:journal kind=root-cause scope=debug id=5f2b434f6caf created=2026-09-26T11:51:59 -->
### 5f2b434f6caf · root-cause · #638: OpenCode has no tests= reader; .records/ is not guarded as fr-owned

(a) orchestrator_wrote_since has only a Claude Code reader, so on OpenCode the tests= provenance gate degrades to "a fresh non-empty file". (b) fr renders pr-body.md into <run>.records/, so agents treat that dir as the evidence dir and commit logs there (a5182264, 79bb92a6, c422fed0 are all agent commits). The record kind locator is *.records/*.yaml, so `fr validate artifacts` never looks at a .log in that dir, and nothing on deliver or in CI refuses it. The fix-659 run leaked the same way, not only fix-505.

<!-- fr:journal kind=repro scope=debug id=b71e7537bf8b created=2026-09-26T11:54:14 -->
### b71e7537bf8b · repro · #683 reproduced in the devcontainer, and caught by both new guards

Running tests/integration/test_install_bridge.py in the dev container relinked /home/vscode/.local/bin/fr -> /tmp/pytest-of-vscode/.../uv-tools/fr/bin/fr. The new in-test assertion (link_state before == after) failed, and the new session-scoped conftest guard _operators_fr_survives_the_suite errored at teardown. Container link repaired with ln -sf "$(uv tool dir)/fr/bin/fr".

<!-- fr:journal kind=finding scope=debug id=f-683 created=2026-09-26T12:01:42 state=fixed -->
### f-683 · finding [fixed] · #683 fixed: UV_TOOL_BIN_DIR isolated, real fr link guarded

tests/integration/test_install_bridge.py sets UV_TOOL_BIN_DIR=tmp_path/uv-bin and asserts the real bin-dir fr link is unchanged (red before: relinked into /tmp/pytest-of-vscode/...). tests/conftest.py _operators_fr_survives_the_suite snapshots the link for the whole session. Full suite in the devcontainer left the container link untouched.

<!-- fr:journal kind=finding scope=debug id=f-638 created=2026-09-26T12:01:44 state=fixed -->
### f-638 · finding [fixed] · #638 fixed: OpenCode tests= reader; .records/ holds records only

telemetry._opencode_wrote_since reads opencode.db (top-level sessions, bash parts, status completed, exit 0, start >= unit open, _writes(command, log)); unreadable db stays None/unverified. run_cmd._verify_tests_log refuses a log whose parent is a *.records dir. validate._records_dir_issues flags non-record files under runs/*.records (CI validate-artifacts job). Stray logs removed. fr-goal SKILL.md now says: redirect into $TMPDIR, never .records/. Pinned by tests/unit/test_run_tests_log_opencode.py (12 tests, all red first). Hermes and a missing Claude transcript still degrade to unobserved=tests with a warning: unchanged, deliberately.
