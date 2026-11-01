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
   `-f` makes `gh api` send a POST, which returns 404, and `run_once` (:639)
   reports `not found at <sha>; skipping (renamed?)` for every run. That is why
   CI drifted from 155 s (#703) to 810 s without a budget issue.

## Requirements

R1. fr parses the acceptance matrix with libyaml's `CSafeLoader` when PyYAML has it, and with the pure-Python `SafeLoader` otherwise; both produce the same `Matrix`.
R2. Within one process, `parse_matrix` of text it has already parsed returns the earlier immutable result instead of parsing again.
R3. The YAML loader choice lives in one helper module in `fr`, which later call sites can adopt.
R4. CI's test shards are split by one durations file per run, derived from CI's own measurements on `main`, with the committed `.test_durations` as the fallback; every shard of a run uses the same file.
R5. CI fails when, for either Python leg, the union of tests its shards ran is not exactly the set that leg collects, or when a test ran in two shards.
R6. Each Python leg runs 6 shards.
R7. The coverage gate (`--fail-under=75`, combined across shards) is measured on the 3.14 leg; the 3.11 leg runs the same tests without coverage.
R8. The release proves its staged commit by running the full suite in 6 shards on that exact commit, each shard checking that the installed `fr` reports the new version; it pushes only when every shard is green.
R9. Release test jobs hold no forge token and no write permission.
R10. When `main` has moved past the commit a release was staged on, the release does not push, exits successfully as superseded, and leaves the release to the run that push triggered.
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

`parse_matrix` (`fr/acceptance/model.py:331`) calls `fr.yamlio.safe_load`, and
is memoized on its exact input text (`functools.lru_cache(maxsize=8)` around a
private `_parse_matrix_cached(text)`). `Matrix` is `frozen=True`
(`model.py:306`) and its rows are a tuple, so sharing one result is safe. A
cached `AcceptanceError` is not kept: the cache wraps only the successful path,
so an error re-raises every call.

`_StrictLoader` (`fr.artifacts.structure`, duplicate-key detection for
`fr validate artifacts`) stays a pure `SafeLoader` subclass. The C loader
cannot be subclassed to override `construct_mapping` the same way, and
validation is not on a hot path.

Expected: the corpus test drops from 418 s to well under 30 s on CI. Every fr
command that reads a matrix (acceptance, self-review, deliver, debt) gets the
same speed-up in every consumer repo.

### B. Self-maintaining shard weights (R4, R5)

`ci.yml` gains two jobs and changes `test`:

- **`plan`** (needs nothing): restores the newest durations cache entry
  (`actions/cache/restore`, key prefix `test-durations-`), falls back to the
  committed `.test_durations`, and uploads the chosen file as artifact
  `durations-plan`. Every shard downloads that one artifact, so a cache save
  landing mid-run cannot make two shards split differently.
- **`test`** (needs `plan`; matrix python × shard 1–6): runs pytest-split with
  `--durations-path durations-plan.json --splits 6 --group N`, plus
  `--store-durations --clean-durations` to a per-shard output path. pytest-split
  loads its input at plugin construction and its writer records only the tests
  this shard ran, by exact node id, from the controller's reports (it sees
  xdist workers' reports). The shard uploads `durations-py<v>-shard-<n>.json`.
  Because pytest-split reads and writes the same `--durations-path`, the step
  first copies the plan file to the per-shard path.
- **`collect`** (needs nothing; matrix python): `pytest --collect-only -q`
  writes the leg's node ids; runs in parallel with the shards, so it is off the
  critical path.
- **`split-check`** (needs `test`, `collect`): `scripts/split_check.py`
  compares, per leg, the multiset of node ids across shard outputs with the
  collected set; any missing, extra or duplicated id fails with the ids named.
  On a `push` to `main` with every shard green, it merges the 3.14 leg's shard
  outputs into one file and saves it as cache key `test-durations-<run_id>`.
  The 3.14 leg is the measured one because it carries coverage (§C), like the
  slowest real run.

`ci-ok` adds `plan`, `collect` and `split-check` to its `needs`.
`scripts/split_check.py` holds the comparison and merge as pure functions with
unit tests. This PR also regenerates the committed `.test_durations` from the
PR's own CI shard outputs, so the fallback is fresh.

### C. Six shards, coverage on the newest leg (R6, R7)

The matrix becomes `shard: [1..6]`. The 3.14 leg runs `--cov` with
`COVERAGE_FILE: .coverage.shard<n>` and uploads `coverage-shard-<n>`; the 3.11
leg runs `--no-cov`. The `coverage` job is unchanged (combine + fail-under 75).
`tests/unit/test_ci_python_floor.py::test_only_the_floor_leg_feeds_coverage`
is the policy pin and changes to "only the newest leg feeds coverage". Coverage
measured on 3.14 can differ slightly from 3.11 where code branches on
`sys.version_info`; the gate's threshold is unchanged.

### D. Sharded release (R8–R12)

`release.yml` becomes three jobs in one concurrency group (`release`,
`cancel-in-progress: false`, as today):

1. **`prepare`**: app token, checkout, then `release.py prepare`: steps 1–4 of
   today's flow (sync to tip, compute, release commit with bump, migration and
   fragment removal, `verify_staged`). It writes `release-plan.json` (new
   version, rc flag, base sha, staged sha, notes inputs) and
   `staged.bundle` (`git bundle` of base..staged) as artifacts, and sets the
   output `cut=true|false`. A "nothing to release" or "tag the untagged RC at
   HEAD" outcome sets `cut=false` and finishes in this job, as today.
2. **`test`** (needs `prepare`, `if: cut == 'true'`; matrix shard 1–6;
   `permissions: contents: read`; no app token): checks out the base sha,
   fetches the bundle, checks out the staged sha, and runs
   `release.py test-shard --group N --splits 6`: the existing version probe
   (`_FR_VERSION_PROBE`, refusing a wrong number), then the shard with
   `--no-cov -n auto` and the plan's durations file (§B's `plan` artifact
   logic, reused from the cache). The release's own `split-check` runs the same
   completeness check as CI over the six shards.
3. **`publish`** (needs `test` + check, `if: cut == 'true'`): app token,
   `release.py publish`: fetches `main`. If `origin/main` is no longer the
   plan's base sha, prints `superseded: main moved to <sha>; the run it
   triggered releases` and exits 0 without pushing (R10). Otherwise it pushes
   the staged commit with today's `push` (a rejection there is the same
   superseded outcome), then tags, publishes the GitHub Release and files floor
   issues (`finish`, unchanged).

`MAX_ATTEMPTS`' recompute loop is removed. It is safe because every push to
`main` starts a Release run and the concurrency group runs them in order: the
run started by the push that superseded this one recomputes from the new tip.
The daily cron and `workflow_dispatch --version` enter at `prepare` like a
push. `release.py`'s no-subcommand entry point keeps its current signature and
composes the three phases in one process (used by `--dry-run` and the unit
tests), so R11 is pinned by the existing `test_release_script.py` cases.

Bounds: `test` jobs `timeout-minutes: 20`, `prepare`/`publish` 10;
`ci.yml` test jobs 20.

### E. Watcher fix and budgets (R13, R14)

`fetch_workflow_text` calls `gh api -X GET repos/…/contents/<path> -f ref=<sha>`,
which sends the field as a query parameter. A unit test pins the argv
(`-X GET` present) through the adapter's `_run` seam. `.github/ci-budget.yaml`
sets `ci.yml: {budget_seconds: 360}` and `release.yml: {budget_seconds: 600}`.
The release workflow's wall clock is the sum over its jobs, which the watcher
already measures (`fetch_jobs`).

### F. Follow-up issues (filed at deliver)

1. Standardize fr's YAML reading on `fr.yamlio` (the remaining 104 sites, plus
   a tripwire banning bare `yaml.safe_load` in `packages/`), for every consumer
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
- **Job count.** CI goes from 17 to 24 jobs per run (12 test + 2 collect +
  plan + split-check + the rest). Queue time is under 5 s today; the watcher
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

| Plan | Status |
|---|---|
