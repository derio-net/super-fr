# CI and release speed — design

**Date:** 2026-11-01
**Slug:** `2026-11-01-ci-speed`
**Status:** design (fr-goal, autonomous)
**Repo:** `derio-net/super-fr` (single-repo change)

## 1. Goal

super-fr's `CI` workflow takes a median 810 s and `Release` 600–1000 s per cut
(max 1795 s). Make both much faster without weakening any gate: every check
that blocks today still blocks, and the release still proves the exact staged
tree it pushes.

### Non-goals

- A merge queue. `main` has no queue, no bypass actor and no
  `FR_AUTOMATION_APP_ID` today; routing the release through a queue
  (#1238 option A) and a light-PR / full-queue CI split are filed as one
  design issue extending #1238 (operator decision, round 2).
- Routing every `yaml.safe_load` in `packages/` (104 sites, 71 files) through
  the new helper. Three parallel goal runs edit those files; the
  standardization is a follow-up issue (operator request).
- Splitting `docs/acceptance/matrix.yaml` into areas: with libyaml the whole
  parse is ~0.25 s on a loaded laptop, and a split is an artifact shape change
  in every consumer repo.

## 2. Measurements (2026-11-01, last 30 completed runs of each workflow)

| Workflow | wall median | p90 | max | critical path |
|---|---|---|---|---|
| `ci.yml` | 810 s | 865 s | 2009 s | `test (py3.11, 2)` 792 s → `coverage` 17 s → `ci-ok` |
| `release.yml` (runs that cut) | ~950 s | 1019 s | 1795 s | one job; `release.py`'s unsharded staged suite |
| everything else | ≤ 40 s | | | |

Queue time is negligible (first-job median 1–5 s). `uv sync` is 2 s on every
job (the setup-uv cache works); checkout 7 s.

Per job in `ci.yml` (medians): py3.11 shards 366 / **792** / 360 / 363 s,
py3.14 shards 246 / 324 / 251 / 252 s. Every other job ≤ 70 s.

Five findings, each measured:

1. **One test is the critical path.** On draft PR #1276 (`--durations=40`):
   `tests/unit/test_dispatch_lint_corpus.py::test_the_dispatch_gate_scores_zero_on_this_repos_own_plans`
   took **418.6 s**; the next slowest test took 16.7 s. In the main-run log,
   shard 2 sits at 92 % from 11:05:44 to 11:12:06 while its other three xdist
   workers are idle. A profile of 20 of its 164 plans: 98 % of the time is
   PyYAML's pure-Python parser reading `docs/acceptance/matrix.yaml`
   (10,221 lines) inside `self_review` → `_verification_issues` →
   `load_spec_matrix` → `load_matrix` (`packages/fr/src/fr/acceptance/model.py:324`,
   `parse_matrix` at :331, `yaml.safe_load`). The same text parsed with
   libyaml (`yaml.CSafeLoader`, available — `yaml.__with_libyaml__` is True):
   pure 4.6 s, C 0.254 s, identical result.
2. **`.test_durations` is stale.** Last refreshed 2026-09-26 (#703) with 6,413
   entries; the suite collects 13,703 tests. pytest-split gives every unknown
   test the average known duration, so more than half the suite is split blind.
   The file was also recorded on a laptop, not a CI runner.
3. **Coverage tracing costs the floor leg ~40 %.** Both legs run `--cov`
   (`ci.yml` test step), only 3.11 uploads it, and 3.11's tracer is
   `settrace` while 3.14's is `sys.monitoring`: 3.11 shards ~360 s vs
   3.14 ~250 s on the same split.
4. **The release suite is unsharded.** `release.py` `_run_staged_tests`
   (`scripts/release.py:191`) runs `pytest -n auto` once on a 4-vCPU runner,
   with no timeout. When `main` moves during the suite, the push is rejected and
   `release_to_main` (:763) recomputes and re-runs the whole suite, up to
   `MAX_ATTEMPTS = 3` (:81) — the 26-minute rc.3 release (#1238).
5. **The CI budget watcher has never filed an issue.** `GhAdapter.fetch_workflow_text`
   (`scripts/ci_budget.py:576`) calls `gh api repos/…/contents/<path> -f ref=<sha>`;
   `-f` makes `gh api` send a POST, which returns 404, and `run_once` (:627, the line at :641)
   reports `not found at <sha>; skipping (renamed?)` for every run. That is why
   CI drifted from 155 s (#703) to 810 s without a budget issue.

## Requirements

R1. fr parses the acceptance matrix with libyaml's `CSafeLoader` when PyYAML has it, and with the pure-Python `SafeLoader` otherwise; both produce the same `Matrix`.
R2. Within one process, `parse_matrix` of text it has already parsed does not parse it again, and no caller can change another caller's result.
R3. The YAML loader choice lives in one helper module in `fr`, which later call sites can adopt.
R4. CI's test shards are split by one durations file per run, derived from CI's own measurements on `main`, with the committed `.test_durations` as the fallback; every shard of a run uses the same file.
R5. CI (for each Python leg) and the release (for its one leg) fail when the union of tests their shards ran is not exactly the set that leg collects with the shards' own options, or when a test ran in two shards.
R6. Each Python leg runs 6 shards.
R7. The coverage gate (`--fail-under=75`, combined across shards) is measured on the 3.14 leg; the 3.11 leg runs the same tests without coverage.
R8. The release proves its staged commit by running the full suite in 6 shards on that exact commit, each shard checking that the installed `fr` reports the new version; it pushes only when every shard is green.
R9. The release's staged suite runs with no forge token in its environment and no write-capable token reachable from its checkout.
R10. When `main` has moved past the commit a release was staged on (a `race` result, never a protection refusal), the release does not push; a fragment-driven run exits successfully as superseded and leaves the release to a later run, and a run carrying an explicit `--version` exits non-zero telling the operator to re-dispatch it.
R11. Every outcome today's release produces (final, RC, nothing to release, untagged RC at HEAD tagged, floor issue, explicit `--version`) is still produced.
R12. Every CI test job and every release job has a `timeout-minutes` bound.
R13. The CI budget watcher reads a workflow file at a commit with a GET request, so a breach files or updates its issue.
R14. `.github/ci-budget.yaml` budgets match the new targets: `ci.yml` 360 s, `release.yml` 600 s.

## 3. Design

### A. Fast matrix parsing (R1–R3)

New module `packages/fr/src/fr/yamlio.py`:

```python
SafeLoader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
def safe_load(text: str) -> object: ...   # yaml.load(text, Loader=SafeLoader)
```

`parse_matrix` (`fr/acceptance/model.py:331`) calls `fr.yamlio.safe_load`.
Repeated parses go through a private `_parse_matrix_cached(text)`, wrapped in
`functools.lru_cache(maxsize=8)` and keyed on the exact text.
`parse_matrix` returns `cached.model_copy(deep=True)`. `Matrix` and `Row` are
`frozen=True` (`model.py:222`, `:306`), but `Row.levels` is a plain `dict`
(`:232`), so a shared instance could be mutated item by item. A deep copy of
about 560 rows costs a small fraction of a pure parse, and no caller can change
what another caller gets. Only successful parses are cached, so an
`AcceptanceError` is raised again on every call.

`_StrictLoader` (`fr/artifacts/structure.py:46`, duplicate-key detection for
`fr validate artifacts`) could be based on `fr.yamlio.SafeLoader`:
`construct_mapping` lives on the Python `SafeConstructor`, so a `CSafeLoader`
subclass would work. It stays pure-Python in this change anyway. It is not a
hot path, and the artifacts module belongs to a parallel goal run. Moving it is
part of follow-up issue §3.F.1.

Expected effect: the corpus test drops from 418 s to well under 30 s on CI.
Every fr command that reads a matrix (acceptance, self-review, deliver, debt)
gets the same speed-up in every consumer repo.

### B. Self-maintaining shard weights (R4, R5)

`ci.yml` gains three jobs and changes `test`. Every new job has a
`timeout-minutes`.

- **`plan`** (needs nothing; timeout 5): `actions/cache/restore` with key
  prefix `test-durations-` restores the newest entry. If there is none, the
  committed `.test_durations` is used. The chosen file is uploaded as artifact
  `durations-plan`. Every shard downloads that one artifact, so a cache save
  landing mid-run cannot make two shards split differently.
- **`test`** (needs `plan`; matrix python × shard 1–6; timeout 20): one
  invocation, after `cp durations-plan.json shard-durations.json`:

  ```
  uv run pytest -o addopts="--strict-markers" <cov options per §C>
    -n auto --splits 6 --group N --splitting-algorithm least_duration
    --durations-path shard-durations.json --store-durations --clean-durations
    --durations=25 --junitxml=junit-shard.xml
  ```

  pytest-split reads `--durations-path` when its plugin is constructed
  (`plugin.py:126-130`) and writes the same path at session finish
  (`:188-222`). With `--clean-durations`, the written file holds only the tests
  this shard reported, keyed by exact node id. The shard uploads it as
  `durations-py<v>-shard-<n>`. Workers also register the writer
  (`plugin.py:110-113`). Phase 1 checks once, and a test pins, that the
  controller's file is the one uploaded. A worker overwrite would fail
  split-check red, so it cannot drop tests silently.
- **`collect`** (needs nothing; matrix python; timeout 10):
  `uv run pytest -o addopts="--strict-markers" --collect-only -q`
  with no split and no coverage. The node ids are the stdout lines that
  contain `::`, so the summary and blank lines drop out. It runs in parallel
  with the shards, off the critical path.
- **`split-check`** (needs `test`, `collect`; timeout 5):
  `scripts/split_check.py check` compares, per leg, the multiset of node ids
  across the shard files with the collected set. Any missing, extra or
  duplicated id fails the job and is named. On a `push` to `main` with every
  shard green, `split_check.py merge` combines the 3.14 leg's shard files into
  one file and saves it as cache key `test-durations-<run_id>`. The 3.14 leg is
  measured because it carries coverage (§C) and so is the slower leg.

`ci-ok` adds `plan`, `collect` and `split-check` to its `needs`.
`scripts/split_check.py` keeps `check` and `merge` as pure functions with unit
tests. This PR also regenerates the committed `.test_durations` from its own
CI shard outputs, so the fallback is fresh.

### C. Six shards, coverage on the newest leg (R6, R7)

The matrix becomes `shard: [1..6]`. The 3.14 leg runs `--cov --cov-report=`
with `COVERAGE_FILE: .coverage.shard<n>` and uploads `coverage-shard-<n>`. The
3.11 leg runs `--no-cov`. The `coverage` job is unchanged: combine, then
fail-under 75. Coverage measured on 3.14 can differ slightly from 3.11 where
code branches on `sys.version_info`. The threshold is unchanged.

### D. Sharded release (R8–R12)

`release.yml` keeps its workflow-level concurrency group (`release`,
`cancel-in-progress: false`) and `UV_PYTHON: 3.11`. Its one job becomes six:

1. **`prepare`** (timeout 10): app token, checkout (`persist-credentials:
   false`, full history), then `release.py prepare`. This is steps 1–3 of
   today's flow: sync to tip, compute, and the release commit with bump,
   migration and fragment removal, including `make_release_commit`'s
   `verify_staged`. It writes `release-plan.json` with the new version, rc
   flag, override, base sha, staged sha and notes inputs. It also writes
   `staged.bundle` (`git bundle` of base..staged) and the durations file, using
   §B's cache restore and fallback. All three are uploaded as one artifact.
   Output `cut=true|false`. A "nothing to release" outcome, or "tag the
   untagged RC at HEAD", sets `cut=false` and finishes in this job, as today.
2. **`collect`** (needs `prepare`, `if: cut`; timeout 10) and
3. **`test`** (needs `prepare`, `if: cut`; matrix shard 1–6; timeout 20).
   Both use `permissions: contents: read`, have no app-token step and no
   `GH_TOKEN`/`FR_RELEASE_STATUS_TOKEN` env, and check out with
   `persist-credentials: false` and full history. Both run
   `release.py materialise`: fetch the bundle, check out the staged sha, verify
   it equals the plan's, and pin `refs/remotes/origin/main` to the plan's base
   sha. That makes tests that read `origin/main`
   (`tests/unit/test_tripwire_unarchived_plans.py`) judge the same base the
   release pushes onto. `collect` then runs §B's collect command.
   `test` runs `release.py test-shard --group N --splits 6`, which is the
   existing version probe (`_FR_VERSION_PROBE`, refusing a wrong number)
   followed by the shard, `--no-cov -n auto`, with §B's durations options.
   Both run through `_credential_free_env()` (`release.py:174`).
4. **`split-check`** (needs `collect`, `test`; timeout 5): §B's `check` over
   the release's single leg.
5. **`publish`** (needs `split-check`, `if: cut`; timeout 10): app token, then
   `release.py publish`. It materialises the staged commit as `test` does, but
   without pinning, and fetches `main`. If `origin/main` is not the plan's base
   sha, or `push` (`release.py:729`) returns `race`, it prints
   `superseded: main moved to <sha>` and pushes nothing. With no override it
   exits 0. A run carrying an explicit `--version` exits non-zero with
   `re-dispatch: gh workflow run release.yml -f version=<X>`, because no later
   run carries the override. A protection refusal still raises, exactly as
   today (`release.py:737`). After a successful push it runs `finish`
   (tag, GitHub Release, floor issues), unchanged.

**Why superseded is safe.** Every push to `main` starts a Release run. GitHub's
concurrency group keeps at most one pending run and cancels an older pending
run when a newer one queues, so the newest pending run always recomputes from
the newest tip. A push that starts no run (a `[skip ci]` message, or a
`GITHUB_TOKEN` push) is picked up by the daily cron within 24 h. The recompute
loop (`MAX_ATTEMPTS`, `EXIT_RACE`, docstring step 5, `release.py:43-45`,
`:81`, `:89`, `:763-786`) is removed.

`release.py`'s no-subcommand entry point keeps its signature and composes
prepare → (one unsharded suite) → publish in one process. That path is for
local use and the unit tests. `--dry-run` stays compute-only (`dry_run`,
`:887`).

`ci.yml`'s test jobs also get `timeout-minutes: 20`.

### E. Watcher fix and budgets (R13, R14)

`fetch_workflow_text` calls
`gh api -X GET repos/…/contents/<path> -f ref=<sha>`, which sends the field as
a query parameter. A unit test pins the argv (`-X GET` present) through the
adapter's `_run` seam (`ci_budget.py:485`). `.github/ci-budget.yaml` sets
`ci.yml: {budget_seconds: 360}` and `release.yml: {budget_seconds: 600}`. The
watcher's `wall_clock` (`ci_budget.py:73`) is the span from the first job's
start to the last job's end, so it includes the queue time between the
release's four stages. The 600 s budget is set with that in mind: estimated
prepare 60 s + test ~300 s + split-check and publish ~60 s + gaps.

### E2. Existing tests this design changes

- `tests/unit/test_release_script.py:322`, `:344`, `:594`, which pin the
  recompute loop, are rewritten to the superseded outcome: exit 0, nothing
  pushed, one bump, and no second suite. A new case covers the override
  (non-zero, with the re-dispatch line). New cases cover each subcommand
  (`prepare` writes the plan and bundle; `materialise` refuses a staged-sha
  mismatch and pins `origin/main`; `test-shard` probes before running;
  `publish` handles superseded, race, protection refusal and success).
- `tests/unit/test_release_workflow.py`: the budget pin (`:138`, `>= 900`)
  moves to `>= 600`, with the rationale above. The checkout and token
  assertions (`:74-127`, which use `next()` and so see only the first job) are
  made per job: every checkout has `persist-credentials: false`; `collect` and
  `test` have no app-token step, no token env and `permissions: contents:
  read`; `publish` and `prepare` take the app token or the default.
- `tests/unit/test_ci_python_floor.py:63`
  (`test_only_the_floor_leg_feeds_coverage`) becomes "only the newest leg
  feeds coverage". It selects the upload by `with.name` starting
  `coverage-shard-` and asserts that the 3.11 leg's pytest step carries
  `--no-cov`.
- `tests/unit/test_ci_budget.py`: no new workflow file, so the watch-list
  tripwire is unaffected. A new case pins the GET argv.

### F. Follow-up issues (filed at deliver)

1. Standardize fr's YAML reading on `fr.yamlio` (the remaining 104 sites,
   `_StrictLoader` on the C loader, plus a tripwire banning bare
   `yaml.safe_load` in `packages/`), for every consumer
   repo (operator request).
2. Merge queue for super-fr: the release rides the queue (#1238 A, app-token
   release PR, `merge_group` proving the landed tree), staging per
   `docs/merge-protection.md`, and whether PR CI can run a lighter set while the
   queue runs the full matrix (note: fr-goal's `tests: ci` reads the PR's gate
   checks). Extends #1238.

## 4. Risks

- **Split mismatch drops tests silently.** pytest-split is deterministic given
  identical durations and collection. One plan artifact per run and the
  `split-check` job make a mismatch a red check rather than a lost test.
- **Release artifacts between jobs.** A bundle that fails to apply, or a staged
  sha that differs from the plan, fails the `test` job. `publish` never runs
  then, so nothing is pushed.
- **Job count.** CI goes from 17 to 25 jobs per run (12 test + 2 collect +
  plan + split-check + 9 others). Queue time is under 5 s today; the watcher
  measures wall clock including queue, so pressure shows up as a budget issue.

## Verification

strategy: candidate
gate: tester
- release-staged-suite-sharded: live — only a real Release run on `main` exercises prepare → sharded test → publish with the app token and the bundle hand-off; walked on first real use (an RC cut counts)
- release-superseded-not-retried: live — needs two pushes to `main` racing a real release run; walked on first real use, unit tests pin the decision
- ci-budget-watcher-files-breach: live — the watcher runs only on `workflow_run` events in this repo; walked on its first run after merge
- matrix-parse-libyaml: none — unit tests in CI prove loader choice, equality and memoization
- ci-shards-complete: none — the `split-check` job runs in this PR's own CI
- ci-coverage-newest-leg: none — `test_ci_python_floor.py` and the `coverage` job in this PR's own CI

## Test Plan

Post-merge, operator-driven. Each step carries its cost.

1. **First real release after merge** (cost: none — walked on first real use).
   The release run that the merge triggers (an RC while `gate:tester` holds)
   shows `prepare` → 6 `test` shards → `split-check` → `publish`, and the tag
   and GitHub Release exist. Record its wall clock beside the 600–1000 s
   baseline with `fr acceptance set-status --walk … --status walked`.
2. **Superseded** (cost: none — walked on first real use). The first time two
   merges land within a release's test window, the older run's `publish` logs
   `superseded` and exits green, and the newer run cuts the release.
3. **Budget watcher** (cost: none). After the merge's CI run, the `CI time
   budget` workflow's log no longer says `not found … (renamed?)`; a breach
   opens or updates a `ci-budget` issue.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-11-01-ci-speed | `derio-net/super-fr` | `2026-11-01-ci-speed` | — |
