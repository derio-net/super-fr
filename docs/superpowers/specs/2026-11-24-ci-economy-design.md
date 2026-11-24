# CI economy: superseded runs, landed combinations, generated conflicts, light lane

Issue: derio-net/super-fr#1647. Refs #1602, #1576, #1593.

## Background

A CI run of this repo is 21 jobs, about 37 job-minutes. An analysis of 651 CI and
Release runs (2026-11-12 to 2026-11-24) found four costs the wave merge queue
(spec `2026-11-19-wave-merge-queue`, archived under `docs/superpowers/implemented/specs/`)
leaves in place:

1. `ci.yml` has no `concurrency` group. A PR that receives several pushes in a row (fr's
   bookkeeping commits are 45% of PR CI runs) pays for full CI on every push, though
   only the last one counts. Only 2 of 454 PR runs were ever cancelled.
2. Under `queue.land: push`, `main` fast-forwards to a combination sha that already
   passed every required check on `fr-queue/**`. The push to `main` then runs CI on the
   identical sha again. The queue spec listed this as out of scope.
3. Queue spec R6 resolves only a version file and a lockfile while building a
   combination. Almost every PR edits the same generated files (`docs/reference/cli.md`,
   the OpenCode and Hermes mirrors) and the docs pages' `reviewed:` stamps, so a stray
   merge to `main` puts the open batch PRs back into conflict and spends their
   two-hand-back budget on files a script writes.
4. `ci.yml` has no path filter. A close-out, archive or triage-state export PR that only
   moves files under `docs/` runs the whole suite (53 PR runs, about 2,000 job-minutes,
   in the window).

What the code does today:

- `ci.yml`'s `ci-ok` job runs `if: always()` and fails when any needed job's result is
  `failure` or `cancelled` (`.github/workflows/ci.yml`, job `ci-ok`). `ci-ok` is the one
  required check of `main`'s ruleset and `.fr/ci.yaml`'s `gate_checks`.
- Every reader that turns a check into a verdict counts GitHub's `CANCELLED` as failing:
  `fr.triage.batch_drive.checks_verdict` (`_FAILING_BUCKETS`), `fr.triage.batch_merge`
  (`FAILING_BUCKETS`), `fr.settle.evaluate` (`_FAILING_BUCKETS`), `fr.triage.collect._bucket`,
  `fr.triage.queue_exec._state`, `fr.real_ghrestclient._BUCKET`/`_ci` and
  `fr.real_ghclient._CI_FAIL`.
- The combination builder (`fr.triage.queue_exec._combine`, `_merged_tree`, `_resolve`)
  calls `fr.triage.batch_merge.unresolvable`; any other conflicted path raises
  `MergeConflictError`, which hands the entry back through `conflict_decision`.
- `.fr/triage.yaml` already has `mirrors:` (`TriageConfig.mirrors`, argument lists), read
  today only by the conflict hand-back brief (`fr.triage.batch_dispatch`). super-fr's own
  `.fr/triage.yaml` declares none.
- `scripts/installable.py`'s `is_installable` is the one definition of an installable
  path: everything except `docs/`, `tests/`, `.github/`, `.changes/`, root-level `*.md`
  and `.test_durations`.
- `tests/fr_scope.py` (`--fr-scope <base>`) selects the tests a branch's changes reach.
- `release.yml` runs its own pre-publish suite on the release commit (`collect`, six
  shards, `split-check`) before `publish` pushes it.

## Requirements

R1. `ci.yml` cancels a pull-request run that a newer push to the same pull request supersedes. The concurrency group is per pull-request ref with `cancel-in-progress` only for `pull_request` events. A push to `main`, a push to `fr-queue/**` and a `merge_group` run each get a group of their own and are never cancelled.
R2. `ci-ok` reports no failure for a run cancelled because a newer push superseded it: it runs only when the run was not cancelled (`if: ${{ !cancelled() }}`). In a run that was not cancelled, any needed job that failed, timed out or was cancelled still fails `ci-ok`.
R3. Every reader that turns a forge check into a pass, pending or fail verdict reads a `CANCELLED` check as superseded, that is pending, never as failing. The readers are `checks_verdict`, the merge's and the queue's required-check readers, `fr pr settle`'s evaluation, `fr triage collect`'s check counts and both GitHub clients' check buckets and rollup state. `TIMED_OUT`, `FAILURE`, `ERROR`, `ACTION_REQUIRED` and `STARTUP_FAILURE` stay failing. The rule is defined once and every reader uses that definition.
R4. A cancelled check that no newer run replaces stays pending. The queue's existing `check_wait_minutes` Need reports it for a combination, and a PR waits as for any pending check.
R5. On a push to `main`, `ci.yml` skips every job except a first classifying job and `ci-ok` when the pushed sha already carries a successful `ci-ok` check run from another workflow run (a queue combination's run on `fr-queue/**`). `ci-ok` then succeeds and its log names the run it trusts. When no such check run exists, or the forge cannot be read, the push runs the full CI. Pull requests, `fr-queue/**` pushes and merge groups never skip by this rule.
R6. `release.yml` and its pre-publish suite are unchanged by this feature.
R7. The test-durations plan that `split-check` saves on a push to `main` is also saved from a successful run on a push to `fr-queue/**`, so a queue landing whose `main` run skips does not starve the shard plan.
R8. `.fr/triage.yaml` takes a new optional key, `generated:`, a list of path globs (`fnmatch`, `*` spans `/`) naming the files the repo's `mirrors:` commands write. A repo with no `generated:` behaves exactly as today.
R9. While building a combination (merge, squash or rebase), the builder sorts the conflicted paths into four kinds: the version and lockfile paths queue R6 already resolves; generated paths (matching a `generated:` glob); stamp paths (files whose every conflict hunk is one `reviewed: <ISO date> <note>` line on each side, inside YAML front matter); and real conflicts. Any real conflict hands the entry back exactly as today, naming only the real paths.
R10. A stamp path is resolved hunk by hunk to the side whose `reviewed:` date is later. On equal dates the entry's side is taken. Every other line of the file is git's own merge result.
R11. When at least one generated path conflicted and no real one did, the builder takes the combination's side of each generated path, then runs each `mirrors:` command, in order, as an argument list in the scratch worktree, then stages the files they wrote. A command that exits non-zero, a generated path still holding conflict markers, or a command that changed a path outside the `generated:` globs hands the entry back as a conflict. The reason names the paths and, for a failed command, the command. A generated conflict in a repo that declares no `mirrors:` is a real conflict.
R12. A combination resolved by R10 or R11 is built, pushed and tested like any other combination. No hand-back budget is spent on it.
R13. super-fr's `.fr/triage.yaml` declares the `mirrors:` commands that regenerate its generated files (`scripts/sync-readme.py`, `sync-opencode.py`, `sync-hermes.py`, `sync-agents-data.py`, `sync-lenses-data.py`) and the `generated:` globs of exactly the files those commands write in whole. `README.md` is not one of them, because it also holds hand-written prose.
R14. Adding `generated:` moves the triage `facts.json` stamp (`FACTS_SCHEMA`), as each earlier per-config key did. Older stamps still load and read `generated` as empty.
R15. A first `ci.yml` job classifies each run into one lane: `landed` (R5), `light` or `full`. A pull request is `light` when every path its diff changes against the merge base with its base branch is non-installable by `scripts/installable.py` and lies outside `tests/` and `.github/`. Every other pull request is `full`, and so is a pull request whose diff cannot be read. A `merge_group` run and a push to `fr-queue/**` are always `full`; a push to `main` is `landed` or `full`.
R16. In the `light` lane, CI runs `lint`, `typecheck`, `validate-artifacts`, `docs-check`, `site-build`, `version-sync`, `change-fragment`, `opencode-plugin-test` and a new `scoped-tests` job, which runs `pytest --fr-scope origin/<base>`. It skips `plan`, `collect`, `test`, `split-check` and `coverage`. The acceptance check (`acceptance-report.yml`) runs on every pull request as today.
R17. `ci-ok` always reports and reads the lane. In every lane, a needed job that failed or was cancelled fails it. In `full`, `collect`, `test`, `split-check` and `coverage` must have succeeded, and `scoped-tests` may be skipped. In `light`, `scoped-tests` must have succeeded, and only `plan`, `collect`, `test`, `split-check` and `coverage` may be skipped. In `landed`, every job but the classifier may be skipped. A missing or unknown lane fails `ci-ok`.
R18. Tests that read this repo's own tracked artifacts or pages (anything under `docs/`, `.fr/` or `.changes/`, read from this checkout) carry a pytest marker, `own_artifacts`. `--fr-scope` selects every `own_artifacts` test whenever a changed path lies under `docs/`, `.fr/` or `.changes/`.
R19. A tripwire fails when a test file that reads one of those paths from this checkout carries no `own_artifacts` marker.

## Design

### A. Superseded runs (R1-R4)

`ci.yml` gains a top-level `concurrency`:

```yaml
concurrency:
  group: ${{ github.event_name == 'pull_request' && format('ci-pr-{0}', github.ref) || format('ci-{0}-{1}', github.event_name, github.run_id) }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

`ci-ok`'s `if:` becomes `${{ !cancelled() }}`. A superseded run therefore leaves no
failing `ci-ok` on the old sha, and the newer run reports its own.

A new module, `fr/checkstate.py`, holds the one definition (R3): a function from a check's
GitHub state or conclusion to `pass | pending | fail`, with `CANCELLED` mapped to `pending`,
and the bucket sets derived from it (`FAILING_BUCKETS` without `cancel`). Every reader named
in the Background imports it instead of keeping its own set. A test greps the package for
the old literals so a second definition cannot return.

### B. Landed combinations (R5-R7)

The first job of `ci.yml`, `classify`, has `checks: read`. On a push to `main` it runs
`scripts/ci_lane.py landed --sha $GITHUB_SHA --run $GITHUB_RUN_ID`, which lists the sha's
check runs (`gh api repos/{repo}/commits/{sha}/check-runs`) and answers `landed` when one is
named `ci-ok` with conclusion `success` and belongs to another run. Any error answers `full`.
Every other job gains `needs: classify` and `if: needs.classify.outputs.lane != 'landed'`
(combined with its own condition). `split-check`'s two save steps also run on pushes to
`fr-queue/**` (R7). `release.yml` is not edited (R6).

### C. Generated files and stamps in the combination (R8-R14)

A new module, `fr/triage/regen.py`, holds the pure parts: `classify_conflicts(paths,
version, generated, read_conflicted)` and `resolve_stamps(text) -> str | None` (None: a hunk
is not a lone `reviewed:` line on each side, or not inside front matter). `queue_exec._resolve`
calls it in place of `unresolvable` alone: version paths keep their rule; stamp paths are
written resolved; generated paths take ours; then, if any generated path conflicted,
`Worktree.run_argv` runs each mirror command and `Worktree.changed_paths` checks R11's limits.
Both merge (`_merged_tree`) and rebase (`_combine`'s cherry-pick loop) go through it.
`TriageConfig.generated` is a `list[str]`; the executor already receives the repo's config,
which it passes on. `FACTS_SCHEMA` moves to 17 with the usual comment (R14).

The mirror commands run the combination's own code on the driver host. That is the same
trust the queue already gives `version.relock` and `post_merge`: the code is an approved PR's.

### D. The light lane (R15-R19)

`scripts/ci_lane.py` (stdlib only, imports `installable.is_installable`) has a `classify`
subcommand: for a pull request it reads `git diff --no-renames --name-only -z
<merge-base>..HEAD` and prints `lane=light` or `lane=full` to `$GITHUB_OUTPUT`; any git
failure prints `full`. The `classify` job runs both subcommands in one step, by event.

`plan`, `collect`, `test`, `split-check` and `coverage` gain `if: needs.classify.outputs.lane
== 'full'`. A new `scoped-tests` job runs `uv run pytest --fr-scope "origin/$BASE_REF" -q
--no-cov -n auto` when the lane is `light`. `ci-ok` reads `needs.classify.outputs.lane` and
each job's result through `scripts/ci_lane.py verdict` (lane and results in env), so the rule
of R17 is code with unit tests, not shell `case` arms.

`own_artifacts` is registered in `pyproject.toml`'s markers. `tests/fr_scope.py`'s selection
adds every item carrying it when a changed path is under `docs/`, `.fr/` or `.changes/`
(`keep_item` reads markers already). The tripwire (`tests/unit/test_tripwire_own_artifacts.py`)
scans test sources for a read of this checkout's root (`REPO_ROOT`, `Path(__file__).parents`)
joined with one of those directories and fails a file without the marker.

## Out of scope

- The operator's merge policy (wave-only or mixed merging, an express lane for stray PRs).
- `docs/explainers/index.md` and other hand-written conflicts: they stay real conflicts.
- `acceptance-report.yml`'s own `main` run: one job, left as it is.
- Cheaper CI per cycle beyond these four changes (#1555, #1340).

## Verification

strategy: none
- ci-superseded-runs: live — only GitHub cancels a run in a concurrency group; the workflow shape and `ci_lane.py verdict` are pinned by unit tests this PR's CI runs
- ci-cancelled-reads-pending: none — unit tests over each reader and the shared definition verify it in CI
- ci-landed-skip: live — only a real queue landing on `main` carries a prior `ci-ok` on the sha; `ci_lane.py landed` is unit-tested against recorded check-run payloads
- queue-regenerates-generated: none — the CI suite proves it over real bare git repositories with real mirror commands
- ci-light-lane: live — only a real docs-only pull request shows the skipped jobs and a green `ci-ok`; the classifier and the verdict are unit-tested
- own-artifacts-tests-selected: none — unit tests of `--fr-scope` selection and the tripwire run in CI
gate: tester

## Test Plan

- pre-merge — CI: unit tests of `fr.checkstate` and of each reader read `CANCELLED` as pending (row `ci-cancelled-reads-pending`).
- pre-merge — CI: queue builder tests over real bare git repos: a conflict in a generated file regenerates and builds, a stamp conflict takes the newer date, a mixed real conflict hands back naming only the real path, a failing or overreaching mirror command hands back (row `queue-regenerates-generated`).
- pre-merge — CI: `--fr-scope` selects `own_artifacts` tests for a docs change, and the tripwire passes over the repo (row `own-artifacts-tests-selected`).
- post-merge — operator-driven: two quick pushes to one PR leave the first run cancelled and no red `ci-ok` on its sha (row `ci-superseded-runs`).
- post-merge — operator-driven: the next queue landing's `main` run shows only `classify` and `ci-ok`, green, naming the `fr-queue/**` run (row `ci-landed-skip`).
- post-merge — operator-driven: the next close-out or archive PR runs `scoped-tests` and no shards, with a green `ci-ok` (row `ci-light-lane`).

## Implementation Plans
