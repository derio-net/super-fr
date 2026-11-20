# One Python, 3.14, for the whole base

Issue: derio-net/super-fr#1589.

## Background

PR CI (`.github/workflows/ci.yml`) runs the whole suite on two interpreters, 3.11 and 3.14. Each
leg is split into 7 shards, so a PR has 14 test jobs plus one `collect` job per leg. The second leg
was added on purpose (#940, #945) so that a break specific to one version shows from either end.
It doubles the PR test cost and gives a flaky test two chances to fail per run (#1586 saw both of
its flake modes on both legs). The Release workflow (`release.yml`) runs one leg, on 3.11
(`UV_PYTHON`).

Coverage is measured on the 3.14 leg only (spec `2026-11-01-ci-speed` R7). On 3.11, coverage
traces with `settrace`; on 3.14 it uses `sys.monitoring`. That spec measured 3.11 shards with
coverage at about 360 s, against about 250 s on 3.14 with the same split.

The operator decided in the question round to move the whole base to 3.14, not only CI. Today
3.11 is the declared floor in six places: `requires-python = ">=3.11"` in the root
`pyproject.toml` and in each member (`packages/{fr,fr-dispatch,fr-cncd,fr-herdr,fr-claude-cloud}`).
Ruff's `target-version = "py311"` (`pyproject.toml:43`) and mypy's `python_version = "3.11"`
(`pyproject.toml:70`) follow it. `tests/unit/test_ci_python_floor.py` keeps both workflows'
`UV_PYTHON` equal to that floor, and `tests/unit/test_ops_isolated_python.py`
(`test_the_python_floor_has_safe_path`) checks the literal `>=3.11`.

**What a higher floor does to installs.** `scripts/install.sh` installs fr with
`uv tool install --force …` and passes no `--python`. The consumer CI that fr scaffolds installs
it the same way (`@@UV_INSTALL@@`, `@@FR_INSTALL@@` in `packages/fr/src/fr/acceptance/scaffold.py`).
uv picks an interpreter that satisfies `requires-python`, and when none is installed it downloads a
managed one (uv's default `python-downloads = automatic`). So an install on a host with only an
older Python still works. Two cases stop working: a host where uv may not download
(`UV_PYTHON_DOWNLOADS=never`, or offline), and an install with plain `pip` on an older Python. The
operator chose to release this as a major version.

The scaffolded consumer CI runs in `image: python:3.12` (`scaffold.py:290`, `:391`, `:548`). It
still works under a 3.14 floor (uv downloads 3.14), but each run then downloads an interpreter.
The operator chose to move those images to `python:3.14`. Consumer files scaffolded before this
change keep `python:3.12` until their owner scaffolds again; no artifact kind tracks those files,
so no migration exists for them.

Ruff at `py314` reports 13 findings on today's tree: 12 `UP047` (generic function not written
with PEP 695 syntax) and 1 `UP043` (default type arguments). They are fixed in this change.

Out of scope: the hook flake itself (#1586, draft PR #1588).

## Requirements

R1. Every `requires-python` in the workspace (the root `pyproject.toml` and the five members) is `">=3.14"`; ruff's `target-version` is `"py314"`, mypy's `python_version` is `"3.14"`, and `uv.lock` records the new floor.
R2. `ruff check`, `ruff format --check` and `mypy` pass on the tree at the new targets, with the findings the new targets raise fixed in code, not ignored.
R3. `ci.yml` sets `UV_PYTHON: "3.14"` at workflow level, and its `collect` and `test` jobs have no `python` matrix axis: one leg, on that interpreter, with no other Python tested anywhere in CI.
R4. The `test` job keeps 7 shards; every shard runs with coverage (`--cov --cov-report=`) and uploads `coverage-shard-<n>`, and the `coverage` job's combine and `--fail-under=75` gate are unchanged.
R5. Artifact names lose the leg: each shard uploads `durations-shard-<n>`, `collect` uploads `collected`, `split-check` checks that one leg's shards against that one collected set, and on a push to `main` merges those shards' durations into the next run's plan.
R6. `release.yml` sets `UV_PYTHON: "3.14"`, so the release suite runs on the floor, as CI does.
R7. The tests that pin the CI layout (`tests/unit/test_ci_split_workflow.py`, `tests/unit/test_ci_shards.py`, `tests/unit/test_ci_python_floor.py`) and `tests/unit/test_ops_isolated_python.py` assert the new layout: one interpreter, equal to the `requires-python` floor, in both workflows; no `python` axis; coverage on every shard.
R8. The consumer CI that `fr` scaffolds uses `image: python:3.14` in each place it names an image, and the scaffold golden fixtures match.
R9. `.github/ci-budget.yaml` keeps `ci.yml` at 360 s with its comment stating that the budget is for one leg; `AGENTS.md`'s CI notes describe one leg on 3.14 (the durations-merge recipe and the measurement paragraph).
R10. The change ships a `major` change fragment whose summary says the floor is now Python 3.14 and that a `uv` install fetches 3.14 when the host has none.

## Design

### A. The floor (R1, R2)

Edit the six `requires-python` lines, `target-version` and `python_version`. Regenerate the lock
with `uv lock`; only the `requires-python` header and any marker that names the floor may move. Run
`ruff check --target-version py314` and fix the 13 findings by hand: the 12 `UP047` become PEP 695
generic functions (`def f[T](x: T) -> T`), which drops the module-level `TypeVar` they used when
nothing else uses it; the `UP043` drops the default type arguments. Then `mypy` with the five
source trees, as CI runs it; fix any new error it reports at 3.14.

### B. CI: one leg (R3, R4, R5)

In `ci.yml`:

- workflow `env: UV_PYTHON: "3.14"`, with the comment rewritten: the floor we declare, the one
  interpreter we test.
- `collect`: drop `strategy.matrix`, the per-leg `env` and the leg in its name; upload
  `collected`.
- `test`: the matrix keeps `shard: [1..7]` only. Drop `python`, `include`, the per-job `UV_PYTHON`
  and `COV_ARGS`; the pytest step passes `--cov --cov-report=` directly. The job name becomes
  `test (<shard>)`. Upload `durations-shard-<n>`; the coverage upload loses its `if:`.
- `split-check`: download `durations-shard-*` and `collected`; one `split_check.py check
  --collected collected/collected.txt shards/durations-shard-*/shard-durations.json`; the main-push
  merge reads `shards/durations-shard-*/shard-durations.json`. The step names drop "3.14 leg".
- `ci-ok`'s `needs` is unchanged (same job ids).

The required-check name is `ci-ok`, so renaming the test jobs breaks no branch rule.

### C. Release (R6)

`release.yml`'s `UV_PYTHON` becomes `"3.14"`, and its comment keeps "the requires-python floor, like
CI".

### D. Tests (R7)

- `test_ci_python_floor.py`: `test_ci_pins_the_requires_python_floor` and
  `test_release_suite_runs_on_the_requires_python_floor` stay (now 3.14).
  `test_ci_tests_the_floor_and_a_newer_python` becomes
  `test_ci_tests_one_python_the_floor`: neither `test` nor `collect` has a `python` axis or a
  job-level `UV_PYTHON`, so both inherit the workflow's floor.
  `test_only_the_newest_leg_feeds_coverage` becomes `test_every_shard_feeds_coverage`: the
  coverage upload has no `if:`, and the pytest step's run carries `--cov --cov-report=`. The module
  docstring is rewritten (one interpreter, #1589).
- `test_ci_split_workflow.py`: drop the `python` assertions; `collect` has no matrix; the merge step
  reads `durations-shard-*`; `test_split_check_covers_every_test_leg` becomes a check that
  `split-check` runs one `split_check.py check` against `collected/collected.txt`.
- `test_ci_shards.py`: its docstring stops naming 3.14-only coverage; assertions on `cov_args`, if
  any, follow the pytest step.
- `test_ops_isolated_python.py::test_the_python_floor_has_safe_path`: assert the floor parses to a
  version at or above 3.11 (where `-P` exists), not a literal, so the next floor move does not edit
  it.

### E. Scaffold (R8)

`scaffold.py`'s three `image: python:3.12` lines become `python:3.14`; regenerate or edit the
golden fixtures under `tests/fixtures/acceptance_scaffold/` and run the tests that read them
(`test_acceptance_scaffold_publish.py`, `test_acceptance_services.py`).

### F. Budget, notes, fragment (R9, R10)

`.github/ci-budget.yaml`: comment only. `AGENTS.md`: the `split_check.py merge` recipe names "the
shards' `shard-durations.json` files"; the measurement paragraph says the figures were measured
when CI ran two legs, and that CI now runs one leg on 3.14. `.changes/feat-ci-single-python.yaml`:
`bump: major`.

The merged row `ci-coverage-newest-leg` (spec `2026-11-01-ci-speed` R7) says coverage is measured
on the 3.14 leg while the 3.11 leg runs without it. It is amended, never edited in place: `reword`
to "measured on every shard of the one leg", and its level ref is re-pointed (`drop-level` /
`add-level`) to the renamed `test_every_shard_feeds_coverage`.

No page in `.fr/docs.yaml` covers `ci.yml`, `release.yml` or the `pyproject.toml` files, so
`fr docs check` owes nothing; the implementer runs it to confirm.

## Verification

strategy: none
- ci-floor-python-3-14: none — the workflow and pyproject layout is pinned by unit tests that this PR's own CI runs
- ci-single-leg: none — this PR's own CI run is the one-leg layout running, and the unit tests pin its shape
- ci-scaffold-python-3-14: none — the scaffold golden tests pin the image
- ci-single-leg-main-push: live — the main-push merge of durations and the release suite on 3.14 run only after merge
gate: developer

## Test Plan

- post-merge — operator-driven: on the first push to `main` after merge, `ci.yml`'s `split-check`
  merges and saves `test-durations-<run_id>` from the `durations-shard-*` files, and the Release
  workflow's shards run green on Python 3.14 (row `ci-single-leg-main-push`).
