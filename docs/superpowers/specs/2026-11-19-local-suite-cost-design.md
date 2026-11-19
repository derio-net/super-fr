# The local full suite's cost: lighter heavy tests, CI as the suite evidence

Issue: derio-net/super-fr#1555. Run: `2026-11-18-perf-test-suite-cost`.

## 1. Goal

A run in this repo should not spend hours on a local full suite. Two tracks:

1. **Lighter tests.** Cut the cost of the heaviest test files where it comes from,
   and measure the saving per file.
2. **CI is the suite evidence.** `deliver` cites CI's full suite (`tests: ci`, which
   already exists) as this repo's declared default. Local runs during a phase are a
   fast, advisory tier, and fr refuses an advisory log offered as evidence. CI's
   `ci-ok` becomes a required check on `main`, so the full suite really is the merge
   gate.

## 2. Background (measured 2026-11-18/19, in this workspace)

- `.test_durations` (refreshed 2026-11-15): 15,182 tests, 18,855 worker-seconds.
  AGENTS.md's "~150 s vs ~870 s on a 12-core host" is out of date by more than 20 times.
- One test, `tests/unit/test_record_review_fixes.py::test_a_crash_at_the_commit_restores_everything_and_a_retry_converges`,
  run alone with `-p no:xdist` under a host load of about 65: 64 s. A profile shows
  **928 subprocesses**. 53 s of the 64 s is waiting on them, and 19 in-process
  `fr` calls (`CliRunner`) make almost all of them.
- By call site, about 530 of the 928 come from one question asked about 7 times per
  `fr` invocation: which remote, and which default branch.
  `fr/git.py`'s `remote_name` (`config --get checkout.defaultRemote`, `remote`) and
  `remote_default_ref` (`symbolic-ref`, `rev-parse --verify` per well-known name)
  are uncached: 133 `config`, 133 `remote`, 91 `symbolic-ref`, 135 `rev-parse
  --verify`, 42 `for-each-ref`, plus 62 `rev-parse --git-dir` and 29
  `--show-toplevel`.
- `tests/unit/record_support.py`'s `started_run` drives a run to `implement` through
  about 10 CLI calls (`tests/integration/test_fr_goal_shape.py`'s
  `_drive_to_implement`). It costs about 30 s under load, and that test builds it
  twice. 8 test files call it.
- `tests/unit/test_run_cli.py`: a sample of 3 tests (26 s, 5 s, 4 s) spawned 571
  git processes, mostly `rev-parse` (199) and `config` (131).
- `tests/integration/test_scenarios.py`: 72 shell scenarios that drive the installed
  `fr` as a subprocess, 1263 s in total, up to 126 s each.
- `deliver`'s `tests` log check (`run_cmd._verify_tests_log`) checks that the log is
  fresh, that you wrote it, and that it is newer than every code path. It never checks
  that the log is a *full* suite. `tests: ci` (`fr/run/ci_evidence.py`) is verified
  against `.fr/ci.yaml`'s `gate_checks: [ci-ok]`. Its witness `ci:<sha>+<base>;tree=`
  is accepted by `tests: reuse`.
- CI's PR runs take 6–13 min of wall clock (last 8 runs). CI runs pytest with
  `-o addopts="--strict-markers"` (`.github/workflows/ci.yml` collect and test jobs),
  which REPLACES `addopts`. `scripts/release.py` (`_probe_then_pytest`) does not
  override `addopts`.
- The `protect main` ruleset holds only `deletion` and `non_fast_forward`. `ci-ok`
  is not required: it is a line in the Ready checklist.
- The phase executor already has a `tests: ci` mode
  (`plugins/super-fr/agents/fr-phase-executor.md`, "Your last act…" section), and a
  phase's `tests` is offered, not owed (`run_cmd._OFFERED_EVIDENCE`).

## Requirements

R1. Within one `fr` invocation, fr answers each read-only git question about a repository's default remote and default branch (`remote_name`, `remote_default_ref`) and its git directory and toplevel at most once per repository state: a later identical question in the same invocation reuses the answer without starting git, and a git write fr makes in that invocation (a fetch, a remote or ref change, a commit) never leaves a stale answer behind. The cache never outlives the invocation.
R2. The test fixtures that build a started run (`record_support.started_run`) and `test_run_cli.py`'s isolated workspace are built once per test worker and copied for each test; every copy is an independent repository (and linked worktree, where the fixture makes one) that passes the same checks the original did.
R3. The twelve slowest files named in #1555 are each profiled (setup vs assertion, subprocess count) and each gets a remedy or a recorded reason for none; each file's single-file run time is measured before and after, on the same host, with the host load stated.
R4. A test case is merged or removed only when another test asserts the same claim on the same code path; each merged or removed case is named in the plan journal with the test that still covers it, and no acceptance-matrix level ref loses its test.
R5. `tests/integration/test_scenarios.py` and `tests/integration/test_install_sh.py` carry a `scenario` marker that the default local run deselects; CI's sharded test job, its collect and split-check jobs, and the release's staged suite still run every test, scenarios included.
R6. A fast local tier, `--fr-scope <base-ref>` (a pytest option in `tests/conftest.py`), selects the test files changed since the merge-base with `<base-ref>`, the test files whose imports reach a source module changed since then, and the tests marked `smoke`; it never selects the `scenario` tier, and it prints the line `fr-scope: advisory — not deliver evidence` in its output.
R7. fr refuses, at `deliver` and at a phase unit, a `tests` log that contains the line `fr-scope: advisory — not deliver evidence`, naming the line and the full-suite or `tests: ci` alternative; a local full-suite log stays accepted as before.
R8. `.fr/ci.yaml` may declare `tests: ci` beside `gate_checks`; when it does, the `deliver` brief names `tests: ci` as the repo's evidence, and each `implement-phase` brief tells the executor to run the fast tier (R6), not the full suite, and to return `tests_log: none` with the fast tier's pass/fail summary. This repo's `.fr/ci.yaml` declares it.
R9. `ci-ok` is a required status check on `main`, set by the operator through `scripts/configure-main-protection.sh` (`--stage bypass`, then `--stage require`), in a back-loaded manual phase.
R10. After track 1 lands, `.test_durations` is refreshed with pytest-split's `--store-durations` over every test (scenarios included), and AGENTS.md's timing figures are replaced by the measured ones, with the fast tier, the `scenario` marker and the declared `tests: ci` default described there.

## 3. Design

### 3.A A per-invocation git answer cache (R1)

A small module, `fr/git_cache.py`, holds a dict keyed on `(resolved root, question)`.
`remote_name`, `remote_default_ref`, the git-dir lookups and the toplevel lookups read
through it. Two rules keep it correct:

1. **Scope.** `fr.cli`'s entry (the `invoke` that every command, and every
   `CliRunner` call in tests, passes through) clears it. Nothing else may hold it
   across invocations.
2. **State fingerprint.** Each entry stores a fingerprint of the files git reads to
   answer the question: the `stat` (mtime_ns, size, inode) of the common dir's
   `config`, `packed-refs`, `HEAD`, and the `refs/remotes/<remote>/` directory with
   its direct children. A lookup whose fingerprint differs is a miss. A fetch, a
   `remote set-head`, a `config` write or a ref deletion moves one of them, so fr never
   needs to invalidate the cache at each of its many write sites. A `stat` costs
   microseconds. A git process costs about 5–60 ms, depending on load.

A `GitRefusal` and a `GitUnavailableError` are never cached. A test pins the effect:
the profiled test of §2 makes at most half the git calls it made before (928 → ≤ 464).
Unit tests show that a fetch, a `remote set-head` and a config change inside one
invocation each produce a fresh answer.

### 3.B Template fixtures (R2)

A session-scoped (per xdist worker) factory builds the started run once, in
`tmp_path_factory`, and gives each test a copy (`shutil.copytree`, symlinks kept). A
linked worktree records absolute paths in both directions (`<wt>/.git` and
`<common>/worktrees/<id>/gitdir`), so the copy runs `git worktree repair` from the
copied base, and the `.fr-isolation` marker's `toplevel` is rewritten for the new
path. A test asserts that a copy passes `fr.isolation.marker.valid_workspace` and
that writing in one copy leaves the others unchanged.

### 3.C Per-file remedies (R3, R4)

Phase 1 profiles each of the twelve files (`pytest --durations=0 -p no:xdist <file>`,
plus the subprocess counter used in §2) and records in the plan journal: setup
seconds, assertion seconds, subprocess count, the remedy, and the before and after
times with the host load. Candidate remedies: the template fixture, an in-process
`CliRunner` call in place of a `fr` subprocess, a module-scoped repository, and
merged parametrized cases (R4 rules).

### 3.D The scenario tier (R5)

`pyproject.toml` registers the `scenario` and `smoke` markers. Its `addopts` gains
`-m "not scenario"`. The two files set `pytestmark = pytest.mark.scenario`. CI
already replaces `addopts`, so its jobs are unchanged. `scripts/release.py`'s staged
suite passes `-m ""`, or an equivalent override, and a test pins that. The
`fr verification walk` scenarios run through the walk, not pytest, and do not change.

### 3.E The fast tier and its marker (R6, R7)

`tests/conftest.py` adds `--fr-scope <base-ref>`. Selection: `git diff --name-only
<merge-base>..` plus uncommitted paths. Changed `tests/**/test_*.py` are selected.
A changed `packages/*/src/<pkg>/…/<mod>.py` selects every test file whose static
imports (`ast`, transitively through `tests/` helper modules) name that module or a
parent package. `smoke`-marked tests are always selected. A small `smoke` set, one
CLI round trip per command group, is marked in phase 2. The run header and terminal
summary print `fr-scope: advisory — not deliver evidence`. The selection is
advisory and makes no claim to be sound: tests that start `fr` as a subprocess are
invisible to an import graph.

`run_cmd._read_suite_log` (shared by `deliver`'s and a phase's `tests` log) refuses a
log that contains that line, exit 2.

### 3.F The declared default (R8)

`ci_evidence.load_gate_checks`'s reader accepts one more key, `tests: ci`. Any other
value is refused, and a file with keys other than `gate_checks` and `tests` is still
refused. The `deliver` brief and the `implement-phase` brief gain a `tests` key
(`{mode: ci, fast_tier: "uv run pytest --fr-scope origin/main -n 2 -q --no-cov"}`)
when the repo declares it. The fr-goal skill (§5, §8) and the phase-executor agent
read the key. The agent edit follows AGENTS.md's agents procedure: sync, a kind
version move, `CANONICAL_SHA256`, a rerender migration hop, and
`fr migrate artifacts --yes`.

### 3.G Required CI (R9)

This is a `[manual]` last phase. The operator runs the two stages of
`scripts/configure-main-protection.sh` (docs/merge-protection.md gives the order).
The PR ships with this phase not done.

## Verification

gate: developer
gate: ci-ok-required-on-main=developer
- git-answers-cached-per-invocation: none — unit tests in CI pin the call-count reduction and the fresh answer after each in-invocation write; the candidate walk's smoke exercises the installed fr end to end
- scenario-tier-deselected-locally: none — unit tests in CI pin the marker, the default deselection and release.py's override; split-check proves CI ran every test
- fast-tier-advisory-and-refused: none — unit tests in CI drive the selection over a fixture repo and the refusal at deliver and at a phase unit
- repo-declares-ci-tests-evidence: none — unit tests in CI pin the `.fr/ci.yaml` reader and both briefs' `tests` key
- ci-ok-required-on-main: live — only the live GitHub ruleset shows the required check, set by the operator's manual phase

## Test Plan

- post-merge — operator-driven: after the manual phase, `gh api repos/derio-net/super-fr/rulesets/<id>` lists a `required_status_checks` rule naming `ci-ok`, and a test PR with a red `ci-ok` cannot merge (row `ci-ok-required-on-main`).

## 4. Out of scope

- Selecting tests by coverage map, or a sound local selection: CI is the evidence.
- CI's own wall clock (#1340).
- A new CI job for scenarios: they stay in the balanced shards.
