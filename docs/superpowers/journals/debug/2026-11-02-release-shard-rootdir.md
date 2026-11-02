<!-- fr:journal-schema=3 -->
# Journal: 2026-11-02-release-shard-rootdir

<!-- fr:journal kind=repro scope=debug id=6fe0224488ae created=2026-11-02T04:50:56+00:00 -->
### 6fe0224488ae · repro · Release split-check reports every test both missing and extra

Release run 41389896526 (merge of #1276): all six `test` shards green, `split-check` red, `publish` skipped — nothing released. Collected ids are `tests/unit/...`; shard ids are `super-fr/super-fr/tests/unit/...`. Local repro from the worktree: `uv run pytest -o addopts=--strict-markers --durations-path <path outside repo> --collect-only` prints `rootdir: /Users/<home>` and prefixed ids; `--durations-path=<path>` prints plain `tests/...` ids.

<!-- fr:journal kind=ruled-out scope=debug id=e532ca391df2 created=2026-11-02T04:51:02+00:00 -->
### e532ca391df2 · ruled-out · Not a split/coverage gap: the same tests appear on both sides

Every "missing" id has a matching "extra" id differing only by the `super-fr/super-fr/` prefix; the shards ran the whole suite. The check is right, the ids are wrong.
