# CI time budget: a sharded test job, and a ticket when a CI file runs slow

- **Date:** 2026-09-26
- **Status:** designed
- **Origin:** operator request, 2026-09-26: CI must not take an inordinate
  amount of time. Split and parallelize large test suites so that a run on
  GitHub takes under 4 minutes. A slower run is not an error, but it files a
  ticket, one per CI file and never a duplicate.
- **Goal:** `ci.yml` runs in about 3 minutes of wall clock. A watcher checks
  every completed run of every CI file against a per-file budget (240s by
  default), and keeps ONE open `ci-budget` issue per CI file while that file is
  over budget. The watcher closes the issue on its own once the file is back
  under budget.

## 1. Problem

Measured on 2026-09-26 (three `CI` runs on main and on PRs):

| job | wall clock |
|---|---|
| `test` (`uv run pytest -n auto`) | 434–436s, of which pytest is 425s |
| `opencode-plugin-test` | 28–31s |
| `typecheck`, `lint`, `validate-artifacts`, `version-sync`, `change-fragment` | 6–16s each |

A `CI` run therefore takes 7 to 7.5 minutes, and the `test` job alone sets that
time. Every other workflow (`acceptance-report`, `release`, `PR spec status`,
`pages`) finishes in under 1 minute.

The suite has 6,408 tests, and their summed test time is about 3,100s locally
(junit XML, `-n auto`). The time is spread thinly across files. The largest
file, `tests/unit/test_run_cli.py`, holds 13% of it, and no other file reaches
5%. The 20 largest files hold 67%. 127 unit files shell out to real `git`. The
`unit/` directory holds 84% of the time and `integration/` the other 16%.
Duration-balanced sharding at the test level therefore balances well. Splitting
by directory would not.

Nothing notices when CI slows down. The job got slow one test at a time, and
no single PR crossed a line that anyone could see.

## 2. Decisions (operator, 2026-09-26)

1. **Scope: repo-local.** The watcher is a GitHub workflow plus a tested script
   under `scripts/`, and it serves super-fr's own CI only. There is no `fr`
   verb, no shipped rule, and no scaffolding for consumer repos.
2. **Sharding: pytest-split, 4 shards.** The shards are duration-balanced from
   a committed `.test_durations` file, with `-n auto` inside each shard. A
   follow-up job combines coverage, so `--cov-fail-under=75` still gates the
   whole suite.
3. **What "4 minutes" measures:** the wall clock of one workflow run, from the
   first job's start to the last job's end. Runner queue time is excluded.
4. **Which runs count:** main-push runs are enough for a workflow whose main
   and PR runs execute the same jobs. A workflow that never runs on a push to
   main is measured on the events it does run on. (Checked against the `on:`
   blocks: `ci.yml` and `acceptance-report.yml` run the same jobs on main and
   PRs, except `change-fragment`, which runs only on PRs, for about 8s and in
   parallel. `_pr_spec_status.yml` and `pinned-clis.yml` never run on a push
   to main.)
5. **Closing:** the issue auto-closes after 3 consecutive under-budget counted
   runs. A later regression opens a NEW issue that links the closed one.
6. **Agents filing tickets: dropped.** The mechanical gate is enough.
7. **Budget:** 240s by default, with a per-file override or exclusion in a
   config file.
8. **Test Plan:** after merge, observe the next main `CI` run, then force a
   breach with a manual dispatch and check that no duplicate is filed (§7).

## 3. Design

### 3.A Sharding the `test` job (`.github/workflows/ci.yml`)

- `pytest-split` is added to the root dev dependencies. `.test_durations`, the
  file pytest-split reads, is committed at the repo root. It is generated with
  `uv run pytest --store-durations --no-cov` (with or without `-n auto`,
  whichever pytest-split supports; the first phase verifies this and records
  it).
- `test` becomes a matrix `shard: [1, 2, 3, 4]`, with `fail-fast: false` so
  that one red shard still reports the other three:

  ```
  uv run pytest -n auto --splits 4 --group ${{ matrix.shard }} \
    --splitting-algorithm least_duration \
    --cov-report= --cov-fail-under=0
  ```

  with `COVERAGE_FILE=.coverage.shard${{ matrix.shard }}`. Each shard uploads
  its coverage data file as an artifact. `fetch-depth: 0` stays on every shard,
  because `test_tripwire_unarchived_plans` reads `origin/main`.
- A new `coverage` job (`needs: test`) downloads the four data files, runs
  `coverage combine`, and then runs `coverage report --fail-under=75`. This job
  now holds the gate that `addopts` held. `addopts` itself is unchanged, so a
  local `uv run pytest` still gates at 75.
- The job name `test` stays, so branch-protection or a reader's muscle memory
  still finds it. GitHub reports the shards as `test (1)` … `test (4)`.
- **Staleness is tolerated by design.** pytest-split gives a test that is
  missing from `.test_durations` the average duration. A stale file only makes
  the shards less balanced, never wrong, and the budget watcher (§3.B) is what
  notices when the imbalance starts to cost time. The refresh command lives in
  `AGENTS.md` ("Dev commands").
- **A shard covers every test exactly once.** This is pytest-split's contract,
  and a unit test pins it (§7.1). The union of the 4 groups' collected ids
  must equal the full collection, with no overlap.

Expected wall clock: about 425s of pytest spread over 4 shards is about 110s
each, plus about 25s of checkout and `uv sync`, plus about 20s for the coverage
job. That is roughly 2.5 to 3 minutes, with headroom under 240s.

### 3.B The watcher (`.github/workflows/ci-budget.yml` + `scripts/ci_budget.py`)

**Trigger.** `workflow_run` with `types: [completed]` over an explicit list of
workflow names. `workflow_run` runs the watcher's copy from the default branch
with the repo's own token, so a fork PR cannot alter it. There is also a
`workflow_dispatch` with inputs `run_id` (required) and `budget_seconds`
(optional override), which the Test Plan uses. Permissions:
`actions: read`, `issues: write`. A concurrency group per watched workflow
file, `ci-budget-<file>`, with `cancel-in-progress: false`, keeps two runs of
one file from racing on one issue. GitHub keeps only the newest pending run,
so a burst can drop an intermediate data point. That is acceptable, because
the next run carries the same signal.

**The script** is split into a pure core and a thin `gh` adapter, so that the
decisions can be unit-tested against captured fixtures:

- `wall_clock(jobs) -> seconds | None`: max `completedAt` minus min
  `startedAt` over jobs that actually ran. Skipped jobs, with null
  timestamps, are ignored. `None` when no job ran.
- `counted(workflow_on, run) -> bool`: derived from the workflow file's own
  `on:` block, which is read at the run's `head_sha`. (PyYAML parses the bare
  key `on` as `True`, and the loader handles both.) If the workflow triggers
  on `push` to `main` (no branch filter, a `**` filter, or `main` listed),
  only `event == push` runs on `main` are counted. Otherwise every event is
  counted. `workflow_dispatch` runs of the watched file are counted only under
  that second rule.
- `budget_for(config, file) -> seconds | EXCLUDED`: from
  `.github/ci-budget.yaml`:

  ```yaml
  default_seconds: 240
  workflows:
    fr-spec-status.yml: {exclude: true}   # reusable (workflow_call); timed inside its caller
  ```

- `decide(state, measurement) -> Action`: the state machine below, with the
  current open issue parsed from its body.
- `render_body(...)`: a stable, idempotent body.

**Only runs with conclusion `success` or `failure` are measured.**
`cancelled`, `skipped` and `timed_out` runs are ignored. A cancelled run has no
meaningful length, and a timed-out one is already loud. A failed run can still
breach the budget, since a suite that is both slow and red is slow. Only a
`success` run counts toward the green streak, so a fast failure cannot close
an issue.

**One issue per CI file, found without search.** Each issue body carries the
hidden marker `<!-- ci-budget:<file> -->` and the label `ci-budget`. The
script ensures the label exists. The open issue is found with
`gh issue list --label ci-budget --state open --json number,body`, filtered
locally on the marker. The script deliberately avoids `gh search`: GitHub's
search index is eventually consistent, so two breaches minutes apart could
each miss the other's fresh issue and file a duplicate. The list API reads
current state. This mirrors `acceptance-report.yml`'s body-marker idempotence,
with the search swapped out for that reason.

**State machine** (per watched file, counted runs only):

| open issue? | run | action |
|---|---|---|
| no | over budget | create an issue. Title: `CI budget: <file> over <budget>s`. The body has the marker, the budget, and a table with this run (link, sha, wall clock, slowest job and its time). If a closed `ci-budget` issue with the same marker exists, the body links the most recent one ("regressed again; previously #N"). |
| no | under budget | nothing |
| yes | over budget | rewrite the body: add the row (the table keeps the last 10 over-budget runs) and reset the streak marker `<!-- ci-budget-green:0 -->`. No comment, so there is no notification spam. |
| yes | under budget, `success` | increment the green streak in the body. At 3, close with a comment naming the 3 runs and their times. |
| yes | under budget, `failure` | nothing (a failure never counts toward green) |

`budget_seconds` from `workflow_dispatch` overrides the configured budget for
that one invocation. That is how the Test Plan forces a breach without slowing
CI.

**The list of watched workflows cannot drift.** A unit tripwire (§7.3)
asserts that every file in `.github/workflows/` is either named, by its
`name:`, in the watcher's `workflow_run.workflows`, or marked
`exclude: true` in `.github/ci-budget.yaml`. The watcher itself is the one
built-in exception. A new workflow therefore fails CI until someone decides
whether it is watched. The tripwire also asserts that every key in
`.github/ci-budget.yaml` names an existing workflow file, so no stale override
can linger.

### 3.C What does not change

- The other CI jobs (`lint`, `typecheck`, `validate-artifacts`,
  `opencode-plugin-test`, `version-sync`, `change-fragment`) are already under
  30s and run in parallel with the shards.
- The local dev loop (`uv run pytest -q --no-cov -n auto`) and `addopts`.
- No `fr` code, skill, rule or shipped surface. No change fragment is required,
  because none of the changed paths is on the fragment list (`scripts/` other
  than the install/validate scripts, `.github/**`, `tests/**` and the root
  `pyproject.toml` are exempt). The `change-fragment` CI job is the arbiter.

## 4. Rollout (the PR that ships this)

One PR. `workflow_run` workflows only fire from the default branch, so the
watcher is inert until merge. The sharded `ci.yml` proves itself on the PR's
own CI run. `AGENTS.md` gains the `.test_durations` refresh command and a line
about the watcher under "Dev commands" / CI.

## 5. Error handling

- `gh` or API failure in the watcher: the job fails (red), and there is no
  partial state. The body is written in one `gh issue edit --body-file`, so
  the issue body is either the old one or the new one.
- A body that has lost its markers because someone edited it by hand: the
  script treats the issue as found (the marker line is required to find it at
  all). If the streak marker is missing, the streak is read as 0. The table is
  regenerated from the parsed rows, and rows it cannot parse are dropped. The
  issue is never duplicated because of a hand edit.
- The watched run's workflow file no longer exists at `head_sha` (renamed): the
  run is skipped with a log line.
- Every combined-coverage failure is a red `coverage` job, which is the same
  signal as the old in-job `--cov-fail-under`.

## 6. Non-goals

- Making individual slow tests faster (`test_run_cli` and the `git`-heavy
  fixtures). Sharding brings CI under budget; optimizing tests is the ticket's
  job when one is filed.
- Agents filing or enriching tickets (operator decision 6).
- A shipped `fr ci` verb or consumer-repo scaffolding (operator decision 1).
- Automatically refreshing `.test_durations`.
- Budgeting queue time.

## 7. Test Plan

Unit level (CI, `tests/unit/test_ci_budget.py`, fixtures captured from real
`gh api` output of this repo's runs, trimmed but never composed):

1. **Shard coverage:** collecting with `--splits 4 --group k` for k = 1..4
   yields disjoint sets whose union is the unsplit collection.
2. **`wall_clock`:** a captured `CI` run's jobs give first start to last end.
   Skipped jobs with null timestamps are ignored. A run where every job was
   skipped gives `None`.
3. **Watched-list tripwire:** every workflow file is watched or excluded, and
   every config key names a real file. Negative cases run on a temp directory:
   an unlisted file fails, and a stale key fails.
4. **`counted`:** `ci.yml`-shaped `on: [push, pull_request]` counts only
   `push@main`. `acceptance-report.yml` (`push: branches: ["**"]`) counts only
   `push@main`. `_pr_spec_status.yml` (`pull_request: closed`) and
   `pinned-clis.yml` (schedule, dispatch, PR) count every event. The `on` key
   parsed as `True` is handled.
5. **State machine:** every row of the §3.B table. Also: a regression after
   closure links the prior issue; the table caps at 10 rows; 3 greens close
   the issue while a `failure` does not advance the streak; a
   `budget_seconds` override applies to one invocation only; a
   `cancelled`/`timed_out` run is ignored.
6. **Dedup:** two sequential breaches of one file make exactly one create
   call and then one edit call, driven through the adapter with a fake `gh`.
   A hand-edited body without a streak marker parses as streak 0 and still
   dedups.
7. **Body idempotence:** rendering a parsed body with no new data is
   byte-identical.

Walking skeleton (phase 1): the PR's own `CI` run shows 4 `test (k)` jobs and
a green `coverage` job gating at 75, and the run's wall clock (first job
start to last job end) is under 240s. That is read with `gh run view` and
recorded in the journal.

Post-merge (operator-driven, not blocking):

1. The next `CI` run on main takes under 4 minutes of wall clock (read it with
   `gh run view <id> --json jobs`).
2. Run `gh workflow run ci-budget.yml -f run_id=<that run> -f budget_seconds=30`.
   Exactly one `ci-budget` issue appears for `ci.yml`. Run the same command
   again: the same issue is updated, with two rows and no duplicate.
3. Close that issue by hand. It was a forced breach.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-26-ci-time-budget | `derio-net/super-fr` | `2026-09-26-ci-time-budget` | — |
