# The local full suite's cost: lighter heavy tests, CI as the suite evidence

Issue: derio-net/super-fr#1555. Run: `2026-11-18-perf-test-suite-cost`.

## 1. Goal

A run in this repo should not spend hours on a local full suite. Two tracks:

1. **Lighter tests.** Cut the cost of the heaviest test files where it comes from,
   and measure the saving per file.
2. **CI is the suite evidence.** This repo declares `tests: ci` (the CI witness already
   exists) as its default for `deliver`. Local runs during a phase are a fast,
   advisory tier. fr refuses a log that marks itself advisory. `ci-ok` becomes a
   required check on `main`, so the full suite really is the merge gate.

## 2. Background (measured 2026-11-18/19, in this workspace)

- `.test_durations` (refreshed 2026-11-15): 15,182 tests, 18,855 worker-seconds.
  AGENTS.md:455's "~150 s vs ~870 s on a 12-core host" is out of date by more than 20 times.
- One test, `tests/unit/test_record_review_fixes.py::test_a_crash_at_the_commit_restores_everything_and_a_retry_converges`,
  was run alone with `-p no:xdist` under a host load of about 65. It took 64 s. A
  profile shows **928 subprocesses**, of which 926 are `git` and 2 are `fr`. About
  53 s of the 64 s is spent waiting on them. 19 in-process `fr` calls (`CliRunner`)
  account for almost all of them.
- By call site, about 490 of those git calls come from two helpers in `fr/git.py`.
  `remote_name` (git.py:184) runs `config --get checkout.defaultRemote` (133 calls)
  and `remote` (133). `remote_default_ref` (git.py:215) runs `symbolic-ref` (91)
  and `rev-parse --verify` (about 135). Each fr invocation asks both about 7 times,
  and nothing is cached. The other large groups come from other call sites:
  `rev-parse --git-dir` (62), `for-each-ref` (42) and `--show-toplevel` (29).
- `tests/unit/record_support.py:142` `started_run` drives a run to `implement`
  through about 10 CLI calls (`tests/integration/test_fr_goal_shape.py:401`
  `_drive_to_implement`). It costs about 30 s under load. The profiled test builds
  it twice, and 8 test files call it. It sets the module global
  `record_support.LAST_BRIEF`, and its base repo's `origin` is an absolute path to
  a bare `origin.git` (test_fr_goal_shape.py:174-177).
- `tests/unit/test_run_cli.py:57` `_repo(tmp_path, branch=...)` builds a linked-worktree
  workspace per test, under several branch names. A sample of 3 tests (26 s, 5 s
  and 4 s) spawned 571 git processes, mostly `rev-parse` (199) and `config` (131).
- `tests/integration/test_scenarios.py` holds 72 shell scenarios that drive the
  installed `fr` as a subprocess: 1263 s in total, up to 126 s each.
  `test_every_scenario_script_has_a_test_here` (:200) in the same file is a cheap
  tripwire.
- `deliver`'s `tests` log check (`run_cmd._verify_tests_log`, :3177) checks that the
  log is fresh, that you wrote it, and that it is newer than every code path. It never
  checks that the log is a *full* suite. `_read_suite_log` (:3273) is shared by
  `deliver` (:3191) and a phase unit (:3600). `tests: reuse` (:3442) re-reads no log,
  only the stored witness of a phase log or a CI witness.
- `tests: ci` (`fr/run/ci_evidence.py`) is verified against `.fr/ci.yaml`'s
  `gate_checks: [ci-ok]`. `load_gate_checks` (:73) reads only `gate_checks` and
  ignores any other key. `declared_gates` (:101) takes the union of the files at
  base and HEAD.
- CI's PR runs take 6–13 min of wall clock (last 8 runs). CI's `collect` and `test`
  jobs pass `-o addopts="--strict-markers"` (`.github/workflows/ci.yml:87,142`),
  which replaces `addopts`, and `split-check` compares the two. The release's shards
  and its collect do the same (`scripts/release.py:227` `SHARD_ADDOPTS`, :301,
  :317). Only the unsharded one-process path, `release_to_main` → `check_staged_suite`
  → `_run_staged_tests` (:221, :1046-1050), inherits `addopts`.
- The `protect main` ruleset holds only `deletion` and `non_fast_forward`. `ci-ok`
  is not required. `scripts/configure-main-protection.sh --stage require` refuses
  until the bypass actor is on the ruleset (:67-69), and until the newest `v*` tag
  was pushed by the app (:73-85). It sets `strict_required_status_checks_policy:
  true` (:93-96).
- The phase executor's last act is the full suite
  (`plugins/super-fr/agents/fr-phase-executor.md:139`). It returns `tests_log: none`
  only for a failed or blocked phase (:147). It has a `tests: ci` mode (:150-159). A
  phase's `tests` is offered, not owed (`run_cmd._OFFERED_EVIDENCE`, :1706).

## Requirements

R1. While a CLI invocation is running (a scope that `fr.cli`'s entry opens and closes), `fr.git.remote_name` and `fr.git.remote_default_ref` answer a repeated question about the same repository from a cache, without starting git, as long as nothing they depend on has changed. A change made inside the invocation (a fetch, a `remote set-head`, a config or ref write, by fr or anything else) makes the next question go to git. Outside a CLI invocation scope, as when fr is used as a library, they never use the cache. A repository the cache cannot fingerprint is never cached.
R2. The fixtures that build a started run (`record_support.started_run`) and `test_run_cli.py`'s isolated workspace (one template per branch name) are built once per test worker, under the same sandboxed HOME and git config the per-test sandbox uses, and copied for each test. Every copy is an independent repository: a linked worktree where the fixture makes one, its own `origin` remote, and its own `LAST_BRIEF`. Every copy passes the same checks the original did.
R3. The twelve slowest files named in #1555 are each profiled (setup against assertion time, and subprocess count) and each gets a remedy or a recorded reason for none. Each file's single-file run time is measured before and after, on the same host, with the host load stated.
R4. A test case is merged or removed only when another test asserts the same claim on the same code path. Each merged or removed case is named in the plan journal with the test that still covers it, and no acceptance-matrix level ref loses its test.
R5. The tests of `tests/integration/test_install_sh.py` and the scenario tests of `tests/integration/test_scenarios.py` carry a `scenario` marker, and the default local run deselects it. `test_every_scenario_script_has_a_test_here` stays unmarked. CI's `collect` and sharded `test` jobs, the release's collect and shards, and the release's one-process staged suite all still run every test, scenarios included, and a test pins each of those command lines.
R6. A pytest option, `--fr-scope [<base-ref>]` (`tests/conftest.py`), runs a fast tier. `<base-ref>` defaults to `fr.git.remote_default_ref`. The tier selects: test files changed, added or untracked since the merge-base; test files whose imports (direct, or through the `tests/` helper modules they import) name a changed source module or one of its parent packages; test files importing a changed `tests/` helper; every test under the directory of a changed `conftest.py`; and the tests marked `smoke`. It never selects the `scenario` tier.
R7. A pytest session that does not run the whole configured suite prints the line `fr-scope: advisory — not deliver evidence` on a line of its own in its terminal summary. That is a session with `--fr-scope`, a non-empty effective `-m` or `-k`, explicit path arguments, `--lf` or `--sw`. The default local run is such a session because of R5, and `-m ""` runs the whole suite. fr refuses, at `deliver` and at a phase unit, a `tests` log with that exact line (a whole-line match), naming the line and the `-m ""` full-suite or `tests: ci` alternative. A phase log refused here never becomes a witness, so `tests: reuse` cannot carry one into `deliver`.
R8. `.fr/ci.yaml` may declare `tests: ci` beside `gate_checks`, read at HEAD; any other value of `tests` is refused, and other unknown keys stay ignored. When the repo declares it, the `deliver` brief names `tests: ci` as the repo's suite evidence (a local `-m ""` full-suite log stays accepted), and each `implement-phase` brief tells the executor to run the fast tier (R6) as its last act instead of the full suite, and to return `tests_log: none` with the fast tier's pass/fail summary. This repo's `.fr/ci.yaml` declares it.
R9. `ci-ok` is a required status check on `main`. The operator sets it in a back-loaded manual phase: `scripts/configure-main-protection.sh --stage bypass`, then a release pushed by the app, then `--stage require`, accepting that `require` also makes every PR be up to date with `main` before it merges.
R10. After track 1 lands, `.test_durations` is refreshed with `uv run pytest -m "" -n auto --no-cov --store-durations` (every test, scenarios included). AGENTS.md's refresh command (:436) and timing figures (:455) are replaced with that command and the measured figures, and AGENTS.md describes the fast tier, the `scenario` marker, `-m ""` and the declared `tests: ci` default.

## 3. Design

### 3.A A scoped git answer cache (R1)

`fr/git_cache.py` holds a context-local cache (a `contextvars.ContextVar`). It is
`None` unless a scope is active. `_FrGroup.invoke` (`fr/cli.py:69`) opens the scope
around each command and closes it afterwards. So a library caller such as
`fr_dispatch`'s tick, a runner adapter or a test body that calls the helpers
directly always goes to git, and a test pins that.

`remote_name` and `remote_default_ref` read through the cache. An entry is keyed on
`(resolved root, question)` and stores the answer and a **fingerprint** of what git
read to produce it. A lookup whose fresh fingerprint differs is a miss. The
fingerprint is computed without starting git:

- **Locate the repository.** Walk up from `root` to the nearest `.git`. If `.git` is
  a file, read its `gitdir:`. Then read `<gitdir>/commondir`, if present, for the
  common dir. If no `.git` is found, or the repository uses an unusual layout, the
  cache does not apply: a `GIT_DIR` or `GIT_COMMON_DIR` environment variable, a
  `<common>/reftable` directory, `extensions.worktreeConfig`, or an `[include` or
  `[includeIf` section in any config file read. The helper then runs git every time.
- **Config.** Record the `stat` (mtime_ns, size, inode, or "absent") of every
  config file git would read: the system file (none under `GIT_CONFIG_NOSYSTEM`;
  else `GIT_CONFIG_SYSTEM`; else the path git itself names, asked once per scope
  with `git config --system --list --show-origin`), the global file
  (`GIT_CONFIG_GLOBAL`, else `$XDG_CONFIG_HOME/git/config` and `~/.gitconfig`), the
  common dir's `config`, and any `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_*` values in the
  environment.
- **Refs.** Record the `stat` of `<common>/packed-refs`,
  `<common>/refs/remotes/<remote>/HEAD`, and every ref file the answer consulted
  (`refs/remotes/<remote>/<name>` for the named branch and each well-known name).
  A nested name such as `release/x/main` is just a deeper path.

A `GitRefusal` or a `GitUnavailableError` is never cached, and neither is a "not a
repository" answer.

The other git lookups (`rev-parse --git-dir`, `--show-toplevel`, `for-each-ref`)
are scattered over at least four runners (`commands/common.py:67`,
`isolation/marker.py:52`, `artifacts/commit.py`, `settings/load.py`, and others).
They stay out of scope here.

Tests:

- A unit test asks twice in one scope and starts git once.
- A unit test shows that each of these produces a fresh answer within one scope: a
  fetch that creates `refs/remotes/origin/main`, a `remote set-head`, a
  `checkout.defaultRemote` set in the global config, a remote added, a ref deleted
  from packed-refs, and a linked worktree.
- A unit test shows that an include or reftable repository is never cached.
- A unit test calls the helpers outside a scope and shows git starts every time.
- A call-count test pins the effect: the §2 test's git subprocesses fall from the
  measured 926 to at most 500.

### 3.B Template fixtures (R2)

A session-scoped factory (per xdist worker) builds each template once under
`tmp_path_factory`. While it builds, it applies the same environment the per-test
sandbox applies (`tests/conftest.py:238-266`: HOME, `GIT_CONFIG_GLOBAL`,
`FR_HOST_ID`, `FR_TRANSCRIPT_ROOT`, `FR_SKIP_MIGRATION`), through one shared helper
that both use. Each test gets a copy (`shutil.copytree`, symlinks kept) made like
this:

1. Copy the base, the bare `origin.git` and the linked worktree, so each copy has
   all three of its own.
2. Run `git remote set-url origin <copy>/origin.git`.
3. Run `git worktree repair <copied worktree>` from the copied base.
4. Rewrite the `.fr-isolation` marker's `toplevel`.
5. Restore the `LAST_BRIEF` captured with the template.

The `test_run_cli.py` template is keyed by branch name.

Tests:

- A copy passes `fr.isolation.marker.valid_workspace` and `fr run status`.
- A push in one copy leaves another copy's `origin.git` unchanged.
- A write in one copy leaves the template and the other copies unchanged.
- The template was built under the sandboxed HOME, not the operator's.

### 3.C Per-file remedies (R3, R4)

Phase 1 profiles each of the twelve files with `pytest --durations=0 -p no:xdist
<file>`, plus the subprocess counter of §2. It records the results in the plan
journal: setup seconds, assertion seconds, subprocess count, the remedy, and the
before and after times with the host load. Candidate remedies are the template
fixture, an in-process `CliRunner` call in place of a `fr` subprocess, a
module-scoped repository, and merged parametrized cases (under R4's rules).
`fr acceptance check` passing is R4's level-ref check.

### 3.D The scenario tier (R5)

`pyproject.toml` registers the `scenario` and `smoke` markers. Its `addopts` gains
`-m "not scenario"`. `test_install_sh.py` sets `pytestmark = pytest.mark.scenario`.
In `test_scenarios.py`, every test except the tripwire carries the mark, through a
module `pytestmark` that the tripwire's own test overrides. It is the cheap guard
that every script has a test.

CI and the release's shards and collect already replace `addopts`, so they do not
change. `scripts/release.py`'s `_run_staged_tests` passes `-m ""`.

A unit test parses `ci.yml`'s collect and test commands and `release.py`'s
`_collect_pytest_args`, `_shard_pytest_args` and `_run_staged_tests` argument lists.
It asserts that each one either replaces `addopts` with no `-m`, or passes `-m ""`.
It also asserts that a collect run with those options lists nodes from both
scenario files. `split-check` alone cannot show this, because collect and the
shards would shrink together. The `fr verification walk` scenarios run through the
walk, not pytest, and do not change.

### 3.E The fast tier and the advisory line (R6, R7)

`tests/conftest.py` adds `--fr-scope`. It builds the changed set from `git diff
--name-only <merge-base>` together with `git ls-files --others
--exclude-standard`. The import index comes from `ast` over `tests/**/*.py`. A test
file is selected when it imports a changed module or one of its parent packages,
either directly or through the `tests/` helper modules it imports, transitively
within `tests/` only. Transitive imports through source modules are not followed,
because nearly every test reaches `fr.cli`. Phase 2 marks a small `smoke` set: one
CLI round trip per top-level command group. The selection is advisory. It makes no
claim to be sound, because tests that start `fr` as a subprocess are invisible to
an import graph.

A `pytest_terminal_summary` hook prints the advisory line whenever the session is
not the whole configured suite (R7's list). `run_cmd._read_suite_log` refuses a log
in which some line, stripped, equals the advisory line. A test shows that a log
which only quotes the string inside other output is accepted.

### 3.F The declared default (R8)

`fr/run/ci_evidence.py` gains `declared_tests_mode(repo_root) -> Literal["ci"] |
None`. It reads `.fr/ci.yaml` at HEAD and refuses any `tests` value other than
`ci`. `load_gate_checks` and its return type do not change, and unknown keys stay
ignored. The key does not relax a gate, because a full local log stays accepted.
So reading it at HEAD lets this PR's own runs use it.

The `deliver` and `implement-phase` briefs gain a `tests` key when the repo
declares it:

```
{mode: ci, fast_tier: "uv run pytest --fr-scope <base> -n 2 -q --no-cov"}
```

`<base>` is the run's default ref, from `remote_default_ref`.

Text changes that go with it:

- **`plugins/super-fr/agents/fr-phase-executor.md`.**
  - The full-suite-last rule (:139) becomes conditional: with a brief `tests.mode:
    ci`, the last act is the fast tier.
  - The "`none` only when failed/blocked" rule (:147) gains that case.
  - The `tests: ci` mode (:150) is left for repos that do not declare it.
- **`plugins/super-fr/skills/fr-goal/SKILL.md`.**
  - §5 describes `tests_log` under the declared default.
  - §6 says the draft-PR-at-implement-start rule applies only to phases that use
    `tests: ci`, which these phases do not.
  - §8 names `tests: ci` as the declared default, and `-m ""` as the full local
    run.

The agent edit follows AGENTS.md's agents procedure:

1. Run `scripts/sync-agents-data.py`.
2. Move the `agents` kind's `current_version`.
3. Update `CANONICAL_SHA256` and `PINNED_AT_VERSION`.
4. Register a `rerender_migration` hop.
5. Run `fr migrate artifacts --yes`.
6. Run `scripts/sync-opencode.py` for the OpenCode agent mirror.

The skill edit runs `scripts/sync-opencode.py` and `scripts/sync-hermes.py`.

### 3.G Required CI (R9)

This is a `[manual]` last phase, done by the operator in this order:

1. `scripts/configure-main-protection.sh --stage bypass`.
2. A release pushed by the app (`FR_AUTOMATION_APP_ID` set). The next merge to
   `main` cuts one.
3. `--stage require`.

`require` turns on "branches must be up to date before merging". From then on,
every PR, the triage batch merges and the merge train among them, must be up to
date with `main` before it merges. The operator accepted that with this decision.
The PR ships with this phase not done.

### 3.H Change fragment

`.changes/perf-test-suite-cost.yaml`, `bump: minor`: a new `.fr/ci.yaml` key, new
brief behaviour, a new refusal of advisory logs, and the git cache.

## Verification

gate: developer
gate: ci-ok-required-on-main=developer
- git-answers-cached-per-invocation: none — (R1) unit tests in CI pin the single git start per scope, the fresh answer after each in-scope change, the uncached library path and the call-count drop; the candidate walk's smoke exercises the installed fr end to end
- template-fixture-copies-independent: none — (R2) unit tests in CI pin that a copy is a valid workspace, that copies share no origin or state, and that the template was built in the sandbox
- scenario-tier-deselected-locally: none — (R5) a unit test in CI parses every CI and release pytest command line and pins that each runs the scenario tier; another pins the local default deselection
- fast-tier-advisory-and-refused: none — (R6, R7) unit tests in CI drive the selection over a fixture repo, the advisory line's conditions, and the refusal at deliver and at a phase unit
- repo-declares-ci-tests-evidence: none — (R8) unit tests in CI pin `declared_tests_mode` and both briefs' `tests` key
- ci-ok-required-on-main: live — (R9) only the live GitHub ruleset shows the required check, set by the operator's manual phase

R3, R4 and R10 have no row. They are measurements and housekeeping of this repo's
own suite, not product behaviour. Their evidence is the plan journal's per-file
table (R3), its merge log together with a passing `fr acceptance check` (R4), and
the refreshed `.test_durations` and AGENTS.md diff (R10), all quoted in the PR body.

## Test Plan

- post-merge — operator-driven: after the manual phase, `gh api repos/derio-net/super-fr/rulesets/<id>` lists a `required_status_checks` rule naming `ci-ok`, and a test PR with a red `ci-ok` cannot merge (row `ci-ok-required-on-main`).

## 4. Out of scope

- Selecting tests by coverage map, or a sound local selection: CI is the evidence.
- Caching the other git lookups (`--git-dir`, `--show-toplevel`, `for-each-ref`).
- CI's own wall clock (#1340).
- A new CI job for scenarios: they stay in the balanced shards.
