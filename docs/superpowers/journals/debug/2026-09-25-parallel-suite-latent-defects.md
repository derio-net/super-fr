# Journal: 2026-09-25-parallel-suite-latent-defects

<!-- fr:journal kind=repro scope=debug id=repro-vk-cache created=2026-09-25T12:48:50 -->
### repro-vk-cache · repro · fr_vk.config._cache leaks across tests (order-dependent failure)

Under `pytest -n auto --dist loadgroup` (probe, 2026-09-25, origin/main 07764f3d) `tests/unit/test_bridge_lifecycle.py::test_lifecycle_hook_not_invoked_when_env_unset` fails; passes serially in default order. Deterministic serial repro, ordering only:

`uv run pytest --no-cov tests/integration/test_bridge_e2e.py tests/unit/test_bridge_lifecycle.py::test_lifecycle_hook_not_invoked_when_env_unset`
→ `VkMcpError: dispatch: VK has no repo registered for 'derio-net/superpowers-for-vk' (known short names: ['bar', 'foo'])`.

<!-- fr:journal kind=ruled-out scope=debug id=ro-dying-mcp created=2026-09-25T12:48:50 -->
### ro-dying-mcp · ruled-out · test_bridge_resilience's failing list_repos is not the leaker in isolation

Its `_DyingMcp` caches `{}`, but `tick()` → `VkRunner` clears the cache per tick; resilience-then-lifecycle passes (13 passed). Every other fr_vk-touching unit file was also paired with the lifecycle test serially: all pass. The e2e file is the one confirmed leaker; any test that populates the cache without clearing afterwards is a latent one.

<!-- fr:journal kind=root-cause scope=debug id=rc-vk-cache created=2026-09-25T12:48:50 -->
### rc-vk-cache · root-cause · Process-global single-slot cache with no per-test reset

`packages/fr-vk/src/fr_vk/config.py` `_cache` is module-global; `known_repos` returns it verbatim once set. `test_bridge_e2e` populates it with a `{foo, bar}` registry via `tick()`; `dispatch_phase` (called directly, not via tick, so no `clear_repo_cache()`) then reads that stale registry → `repo_id_for` misses → VkMcpError. Nothing in tests/conftest.py resets the cache, so correctness depends on test order — which xdist reshuffles. Production is fine: the daemon clears once per tick by design.

<!-- fr:journal kind=finding scope=debug id=fx-vk-cache created=2026-09-25T12:49:56 state=fixed -->
### fx-vk-cache · finding [fixed] · Autouse fixture resets fr_vk.config._cache per test

`tests/conftest.py::_fresh_vk_repo_cache` monkeypatches `_cache` to None for every test (restored on teardown). Failing-test-first: `tests/unit/test_suite_isolation_vk_repo_cache.py` runs a poison→observe pair in an inner pytest subprocess over a copy of the real conftest (order fixed regardless of xdist). RED before the fixture: `AssertionError: leaked from the previous test: {'leaked': 'uuid-leaked'}`; GREEN after, and the e2e→lifecycle ordering passes.

<!-- fr:journal kind=root-cause scope=debug id=rc-idle-budget created=2026-09-25T12:49:57 -->
### rc-idle-budget · root-cause · Idle-guard hang test's 10s wall-clock budget is too tight under parallel load

`tests/integration/test_run_idle_guard.py::test_fails_open_when_fr_hangs_and_does_not_hang_with_it` bounds a watchdog (FR_IDLE_GUARD_TIMEOUT=1) over `exec sleep 30` with `elapsed < 10`. Alone ~1.1s; with 12 loaded xdist workers process startup + bash + fr spawn push it past 10s. Not a guard defect: the assertion's purpose is 'did not wait for the 30s sleep', which < 25 still proves.

<!-- fr:journal kind=finding scope=debug id=fx-idle-budget created=2026-09-25T12:49:57 state=fixed -->
### fx-idle-budget · finding [fixed] · Idle-guard budget widened to < 25s

Still bounds the 30s sleep; one-line comment records why.

<!-- fr:journal kind=review scope=debug id=review-1 created=2026-09-25T13:01:15 -->
### review-1 · review · Independent code review: 1 in-scope hardening fixed, 2 out-of-scope notes

Reviewer (separate context, read-only). In-scope: the inner-subprocess regression test's `--rootdir` does not stop pytest's ini discovery walking up from tmp_path, so an ancestor ini's addopts could make it fail spuriously (latent). Fixed: an empty `pytest.ini` is written into tmp_path; RED (without the conftest fixture) and GREEN re-verified. Verified sound: fixture restore semantics, pytest-cov combining xdist workers under --cov-fail-under=75, the <25s budget. Out-of-scope, no evidence of a real leak: `fr.workflow.resolve._PACKAGED_DIR_CACHE` (depends only on install shape) and `monkeypatch.chdir` users (auto-restoring). Not filed: no observed failure.

<!-- fr:journal kind=repro scope=debug id=repro-columns-80 created=2026-09-25T13:22:30 -->
### repro-columns-80 · repro · CI-only: four CLI tests wrap at 80 cols under -n auto on Linux

PR #615 CI (4 workers, Linux, py3.12): test_models_cmd::test_set_names_the_file_it_changed, test_journal_cmd::TestCheckRequireReviews x2, test_run_cost_cmd::test_the_command_prints_the_table_and_writes_nothing fail — rich output wrapped at ~80 despite conftest's per-test COLUMNS=200. Did NOT reproduce on macOS under -n 4 even with CI=true GITHUB_ACTIONS=true and no TTY. DID reproduce in a python:3.12 Linux container: serial 117 passed; `-n 1` on the three files alone → the same 4 failures. So not ordering: any Linux xdist worker.

<!-- fr:journal kind=ruled-out scope=debug id=ro-columns-ordering created=2026-09-25T13:22:30 -->
### ro-columns-ordering · ruled-out · Not a test-order leak, not a Console width setter, not FORCE_COLOR/TERM

No test or src sets Console width/_environ/FORCE_COLOR/TTY_COMPATIBLE/TERM; no os.environ rebinding; `-n 1` with one file fails, so no predecessor test is involved. xdist/execnet/pytest-cov/click/typer source contains no COLUMNS write.

<!-- fr:journal kind=root-cause scope=debug id=rc-columns-80 created=2026-09-25T13:22:31 -->
### rc-columns-80 · root-cause · GNU readline setenvs COLUMNS=80 in the pytest main process; xdist workers inherit it; module-level rich Consoles freeze it at import

Evidence (Linux container): a .pth probe shows the pytest main process starts with COLUMNS unset while its xdist worker starts with COLUMNS='80' LINES='24'. An import hook shows `import readline` comes from `_pytest/capture.py::_readline_workaround` (pytest_load_initial_conftests). `python -c 'import readline'` then `echo $COLUMNS` in a child → 80/24 while `os.environ.get('COLUMNS')` stays None: GNU readline (rl_change_environment) setenvs at C level; macOS libedit does not, hence Linux-only. execnet spawns workers via `Popen(args)` with no env=, inheriting the C environ. In the worker, `fr.commands.*` build `Console()` at import (collection, before fixtures); rich's Console.__init__ snapshots COLUMNS into `_width` → frozen at 80 (probe: at import ('80', 80); in-test COLUMNS=200 but console.size.width=80). Serial runs never have COLUMNS in os.environ, so their consoles read the width live.

<!-- fr:journal kind=finding scope=debug id=fx-columns-80 created=2026-09-25T13:23:55 state=fixed -->
### fx-columns-80 · finding [fixed] · conftest drops inherited COLUMNS/LINES at import so module-level consoles stay live

`tests/conftest.py` pops COLUMNS and LINES from os.environ at import (before any test module is collected), so fr's import-time `Console()`s keep `_width=None` and follow each test's COLUMNS (the per-test 200 pin, and the tests that deliberately narrow to 40/60/80 still work). Failing-test-first: `tests/unit/test_suite_isolation_inherited_columns.py` runs a real `fr.commands.journal_cmd.err_console` width probe in an inner pytest session over a copy of the real conftest with COLUMNS=80/LINES=24 in its env (the worker's inherited values). RED: `AssertionError: frozen at import: _width=80`; GREEN after. Linux container: the 3 affected files + the narrow-width tests pass at -n 1, -n 4 and serially; full `-n 4` goes 74→70 failures, the 4 targets gone and nothing new (the remaining 70 are container-only: no gh/jq). Rejected alternative: making fr's consoles lazy in src — the CLI process's import-time COLUMNS is its runtime COLUMNS, so users are unaffected; the defect is the test harness's inherited env.
