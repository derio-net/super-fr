<!-- fr:journal-schema=3 -->
# Journal: 2026-11-02-release-shard-rootdir

<!-- fr:journal kind=repro scope=debug id=6fe0224488ae created=2026-11-02T04:50:56+00:00 -->
### 6fe0224488ae · repro · Release split-check reports every test both missing and extra

Release run 41389896526 (merge of #1276): all six `test` shards green, `split-check` red, `publish` skipped — nothing released. Collected ids are `tests/unit/...`; shard ids are `super-fr/super-fr/tests/unit/...`. Local repro from the worktree: `uv run pytest -o addopts=--strict-markers --durations-path <path outside repo> --collect-only` prints `rootdir: /Users/<home>` and prefixed ids; `--durations-path=<path>` prints plain `tests/...` ids.

<!-- fr:journal kind=ruled-out scope=debug id=e532ca391df2 created=2026-11-02T04:51:02+00:00 -->
### e532ca391df2 · ruled-out · Not a split/coverage gap: the same tests appear on both sides

Every "missing" id has a matching "extra" id differing only by the `super-fr/super-fr/` prefix; the shards ran the whole suite. The check is right, the ids are wrong.

<!-- fr:journal kind=root-cause scope=debug id=8acc89f983e3 created=2026-11-02T04:51:09+00:00 -->
### 8acc89f983e3 · root-cause · Two-token --durations-path makes pytest compute rootdir from the outside path

`scripts/release.py` `_run_shard_tests` passes `--durations-path` and `${runner.temp}/shard-durations.json` as separate argv tokens. pytest determines rootdir in `_initini` before entry-point plugins (pytest-split) register their options, so the unknown option value is taken as a path argument; with no positional test path, rootdir becomes the common ancestor of cwd and that path (`/home/runner/work` on CI), every nodeid gains the checkout-relative prefix, and pyproject config may not load. `ci.yml` is unaffected because its durations path is inside the repo. Unit tests fake `run`, so no real argv ever reached pytest.

<!-- fr:journal kind=finding scope=debug id=234d002c27d7 created=2026-11-02T05:10:59+00:00 state=fixed -->
### 234d002c27d7 · finding [fixed] · Shard/collect argv share a rootdir; durations path is one = token

`scripts/release.py`: `_shard_pytest_args` / `_collect_pytest_args` (both `--rootdir=<repo>`; `--durations-path=<out>`). Failing test first: `tests/integration/test_release_shard_ids.py` (red: split_check reported the 3 ids missing/extra; green after). Unit pin updated in `test_release_script.py`. Verified against this repo: rootdir = checkout, configfile pyproject.toml, plain `tests/...` ids with an outside durations path. Matrix `release-staged-suite-sharded` gains the int ref, stays walk-owed.
