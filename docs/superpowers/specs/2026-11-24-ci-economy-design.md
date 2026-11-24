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
R2. `ci-ok` keeps running in every run (`if: always()`) and fails when a needed job failed, timed out or was cancelled. A superseded run therefore ends with a failing `ci-ok` on the superseded sha only. That sha is no longer the head of any pull request, and GitHub's ruleset and every fr reader judge a pull request by its head, so the superseded run reads as superseded, not red. `ci-ok` is never skipped: a skipped required check counts as passing on GitHub and in fr, so a skipped `ci-ok` on a hand-cancelled head would let an untested change merge.
R3. Every reader that turns a GitHub check on a pull-request head or a combination into a pass, pending or fail verdict reads a `CANCELLED` check as superseded, that is pending, never failing. The readers are `checks_verdict`, the merge's required-check reader (`batch_merge`), the queue's combination reader (`queue_exec._state`), `fr pr settle`'s evaluation, `fr triage collect`'s check counts, the REST client's check buckets and rollup state, the DevOps gate's check read (`ops.gate._checks_green`) and `deliver`'s `tests: ci` witness (`verify_ci`, where a cancelled gate check means waiting, exit 75). `TIMED_OUT`, `FAILURE`, `ERROR`, `ACTION_REQUIRED`, `STARTUP_FAILURE` and `STALE` stay failing, as do the status-context states `error` and `failure`. The rule is defined once, and every reader uses that definition.
R4. A cancelled required check that no newer run replaces stays pending. On a combination it is reported like a check that never reported: once `queue.check_wait_minutes` have passed since the build, the queue raises a Needs-you entry naming it. This applies whether the repo declares required checks or not.
R5. On a push to `main`, `ci.yml` skips every job except a first classifying job, `validate-artifacts` (the strict check that only the default branch runs) and `ci-ok`. It does so when the pushed sha already has a successful run of this `CI` workflow, triggered by a push to a branch under `fr-queue/`. `ci-ok` then succeeds, and its log names the run it trusts. When no such run exists, or the forge cannot be read, the push runs the full CI. Pull requests, `fr-queue/**` pushes and merge groups never skip by this rule.
R6. `release.yml` and its pre-publish suite are unchanged by this feature.
R7. The test-durations plan saved on `main` stays fed without new saving. A push to `main` that runs the full CI still saves it: a hand merge, and the release commit pushed by the release app. Every pull-request run that restores the plan keeps the cache entry from expiring.
R8. `.fr/triage.yaml` takes a new optional key, `generated:`, a list of path globs (`fnmatch`, `*` spans `/`) naming the files the repo's `mirrors:` commands write in whole. A repo with no `generated:` and no `mirrors:` behaves exactly as today.
R9. While building a combination (merge, squash or rebase), the builder sorts each conflicted path into one of these kinds. Version and lockfile paths keep the rule queue R6 already applies. Whole generated paths match a `generated:` glob. Resolvable hunk paths are files whose conflict hunks are each either a stamp hunk or a generated-block hunk. A stamp hunk is one `reviewed: <ISO date> <note>` line on each side, inside YAML front matter. A generated-block hunk lies wholly between a `<!-- generated:NAME -->` line and its `<!-- /generated:NAME -->` line, on both sides. Every other path is a real conflict. Any real conflict hands the entry back exactly as today, naming only the real paths.
R10. A stamp hunk is resolved to the side whose `reviewed:` date is later. On equal dates the entry's side is taken. A generated-block hunk takes the combination's side. Every other line of the file is git's own merge result.
R11. When a whole generated path or a generated-block hunk conflicted, and no real conflict did, the builder first takes the combination's side of each whole generated path. It then runs each `mirrors:` command in order, as an argument list in the scratch worktree, with a 10-minute timeout per command, and stages what they wrote. The entry is handed back as a conflict, naming the paths and, for a failed command, the command, in any of these cases: a command exits non-zero or times out (a host without the command's program included); a file still holds conflict markers; or the commands changed a tracked path that is neither a `generated:` glob nor a change inside a generated block. A repo that declares no `mirrors:` treats every such path as a real conflict.
R12. A combination resolved by R10 or R11 is built, pushed and tested like any other combination. No hand-back budget is spent on it.
R13. super-fr's `.fr/triage.yaml` declares the `mirrors:` commands that regenerate its generated files, each run through `uv run --frozen` so the combination's own `fr` is imported and `uv.lock` is never rewritten: `scripts/sync-readme.py`, `sync-opencode.py`, `sync-hermes.py`, `sync-agents-data.py`, `sync-lenses-data.py`. It also declares the `generated:` globs of exactly the files those commands write in whole. `README.md` and `docs/reference/cli.md` are not among them: those commands write only their generated blocks, which R9 resolves.
R14. Adding `generated:` moves the triage `facts.json` stamp (`FACTS_SCHEMA`), as each earlier per-config key did. Older stamps still load and read `generated` as empty.
R15. A first `ci.yml` job, with full history, classifies each run into one lane: `landed` (R5), `light` or `full`. A pull request is `light` when every path its diff changes against the merge base with its base branch is non-installable by `scripts/installable.py` and lies outside `tests/` and `.github/`. Every other pull request is `full`, and so is a pull request whose diff cannot be read. A `merge_group` run and a push to `fr-queue/**` are always `full`. A push to `main` is `landed` or `full`.
R16. In the `light` lane, CI runs `lint`, `typecheck`, `validate-artifacts`, `docs-check`, `site-build`, `version-sync`, `change-fragment`, `opencode-plugin-test` and a new `scoped-tests` job. `scoped-tests` checks out full history and runs `pytest --fr-scope origin/<base>`. CI skips `plan`, `collect`, `test`, `split-check` and `coverage`. The acceptance check (`acceptance-report.yml`) runs on every pull request as today.
R17. `ci-ok` always reports and reads the lane. In every lane, a needed job that failed or was cancelled fails it. In `full`, `collect`, `test`, `split-check` and `coverage` must have succeeded, and `scoped-tests` may be skipped. In `light`, `scoped-tests` must have succeeded, and only `plan`, `collect`, `test`, `split-check` and `coverage` may be skipped. In `landed`, `validate-artifacts` must have succeeded, and every other job but the classifier may be skipped. A missing or unknown lane fails `ci-ok`.
R18. A green `ci-ok` in the `light` lane is valid `tests: ci` evidence for `deliver`, unchanged. The lane applies only when nothing installable, nothing under `tests/` and nothing under `.github/` changed, so the full suite would test the same code the base already passed. `verify_ci` does not read the lane.
R19. Tests that read this repo's own checkout carry a pytest marker, `own_artifacts`. `--fr-scope` selects every `own_artifacts` test whenever a changed path lies under `docs/`, `.fr/` or `.changes/`, or is a root-level `*.md` or `.test_durations`.
R20. A tripwire fails when a test module resolves this checkout's root and carries no `own_artifacts` marker. Resolving the root means naming the shared root constant (`REPO_ROOT` and its aliases in `tests/`), computing `Path(__file__)…parents[…]`, or importing a `tests/` helper that exposes the root. That covers tests that hand the root to an fr reader (`validate_repo`, `load_effective`) as well as tests that join it with a path. The tripwire does not see a test that reaches the checkout only through a subprocess whose working directory it does not pass.

## Design

### A. Superseded runs (R1-R4)

`ci.yml` gains a top-level `concurrency`:

```yaml
concurrency:
  group: ${{ github.event_name == 'pull_request' && format('ci-pr-{0}', github.ref) || format('ci-{0}-{1}', github.event_name, github.run_id) }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

`ci-ok` keeps `if: always()` (R2). A workflow-shape test pins both.

A new module, `fr/checkstate.py`, holds the one definition (R3). It maps a check's GitHub
state or conclusion (any case) to `pass | pending | fail`, with `CANCELLED` mapped to
`pending`. It also derives the bucket sets: the failing buckets are `{"fail"}`, and the
`cancel` bucket is pending. `batch_drive`, `batch_merge`, `settle.evaluate`,
`collect._bucket`, `queue_exec._state`/`_FAILED`, `real_ghrestclient._BUCKET`/`_ci`,
`ops.gate._checks_green` and `run.ci_evidence.verify_ci` import it. A tripwire scans
`packages/fr/src` for a check-state set: a literal set holding `"cancel"` beside `"fail"`, or
`"CANCELLED"` beside `"FAILURE"`, outside `fr/checkstate.py`. It does not look at the batch
lifecycle stage `cancelled`. Two readers are exempt on purpose. The GraphQL client's
`_coerce_ci_state` reads GitHub's aggregate `statusCheckRollup.state`, which has no
`CANCELLED` (GitHub folds it before fr sees it), and only feeds `list_linked_prs`' display
`ci`. GitLab and Gitea clients (`real_glabclient`) are outside this repo's queue (gh#611).

`slot_check` (R4) counts a required check whose latest run is cancelled as "not reported"
for the `late` list. With no required checks, a cancelled check left past `wait_minutes` is
reported late the same way.

### B. Landed combinations (R5-R7)

The first job of `ci.yml`, `classify`, has `permissions: {contents: read, actions: read}`
and checks out with `fetch-depth: 0`. On a push to `main` it runs `scripts/ci_lane.py landed
--sha $GITHUB_SHA --run $GITHUB_RUN_ID`. That lists the workflow runs for the sha (`gh api
repos/{repo}/actions/runs?head_sha=<sha>&event=push`) and answers `landed` only for a run
that meets all of these: its `path` is `.github/workflows/ci.yml`, its `head_branch` starts
with `fr-queue/`, its `conclusion` is `success`, and its id is not this run's. A successful
run means every job succeeded or skipped by its own condition, `ci-ok` included. Any error
answers `full`. Every other job gains `needs: classify` and an `if:` that keeps its own
condition and adds the lane rule, except `validate-artifacts`, which runs in the landed lane
too (R5, R17). `release.yml` is not edited (R6). `split-check`'s save steps are unchanged
(R7).

### C. Generated files and stamps in the combination (R8-R14)

A new module, `fr/triage/regen.py`, holds the pure parts. `classify_conflicts(paths,
version, generated, read)` sorts the paths into the R9 kinds. `resolve_hunks(text)` returns
the file with every stamp and generated-block hunk resolved, or None when one hunk is
neither. `outside_generated(before, after, generated)` lists the tracked paths a mirror run
changed outside the R11 limits, comparing file texts block by block. New plumbing:

- `Worktree.run_argv(argv, timeout)`: runs a mirror command, via the existing declared-command runner, as an argument list.
- `Worktree.snapshot_tracked()`: the tracked paths' texts in the index and working tree after the merge and before the mirrors run, so that `outside_generated` compares the working tree after the mirrors with that snapshot, not two refs.
- `QueuePorts` gains `mirrors` and `generated`, read from the repo's `TriageConfig`. They are threaded through `build`, `_combine`, `_merged_tree`, `_keeps_merge_content` and `_resolve`.

`_resolve` calls `classify_conflicts` in place of `unresolvable` alone. Version paths keep
their rule. Hunk paths are written resolved and staged. Whole generated paths take ours.
Then, if any generated kind conflicted, the mirrors run and the R11 limits are checked.
Merge (`_merged_tree`) and rebase (`_combine`'s cherry-pick loop) both go through it.
`TriageConfig.generated` is a `list[str]`. `FACTS_SCHEMA` moves to 17 with the usual comment
(R14).

The mirror commands run the combination's own code on the driver host. The queue already
gives `version.relock` and `post_merge` the same trust: the code is an approved PR's. The
`uv run --frozen` commands build a `.venv` inside the scratch worktree, which git ignores, and
reuse it while that worktree lives.

### D. The light lane (R15-R20)

`scripts/ci_lane.py` is stdlib only and imports `installable.is_installable`. Its `classify`
subcommand handles a pull request: it reads `git diff --no-renames --name-only -z
<merge-base>..HEAD^2`, with the merge base taken against `origin/<base>` (the PR head is the
merge commit's second parent), and prints `lane=light` or `lane=full` to `$GITHUB_OUTPUT`.
Any git failure prints `full`. The `classify` job runs `landed` or `classify` by event. A
workflow-shape test pins `fetch-depth: 0` on `classify` and `scoped-tests`.

`plan`, `collect`, `test`, `split-check` and `coverage` gain `if:
needs.classify.outputs.lane == 'full'`. A new `scoped-tests` job runs `uv run pytest
--fr-scope "origin/$BASE_REF" -q --no-cov -n auto` when the lane is `light`. `ci-ok` passes the
lane and `toJSON(needs)` to `scripts/ci_lane.py verdict`, so R17 is code with unit tests, not
shell `case` arms.

`own_artifacts` is registered in `pyproject.toml`'s markers. `tests/fr_scope.py`'s `select`
adds every item carrying it for the R19 paths (`keep_item` already reads markers). The
tripwire (`tests/unit/test_tripwire_own_artifacts.py`) parses each test module with `ast` and
applies R20's three patterns.

## Out of scope

- The operator's merge policy (wave-only or mixed merging, an express lane for stray PRs).
- `acceptance-report.yml`'s own `main` run: one job, left as it is.
- GitLab and Gitea check readers (gh#611), and the GraphQL aggregate rollup state (Design §A).
- Hand-written conflicts outside generated blocks, `docs/explainers/index.md` included: they stay real conflicts.
- Cheaper CI per cycle beyond these four changes (#1555, #1340).

## Verification

strategy: none
- ci-superseded-runs: live — only GitHub cancels a run in a concurrency group; the workflow shape is pinned by unit tests this PR's CI runs
- ci-cancelled-reads-pending: none — unit tests over the shared definition and each reader verify it in CI
- ci-landed-skip: live — only a real queue landing on `main` has a prior successful `fr-queue/**` run on the sha; `ci_lane.py landed` and the workflow shape are unit-tested
- queue-regenerates-generated: none — the CI suite proves it over real bare git repositories with real mirror commands
- ci-light-lane: live — only a real docs-only pull request shows the skipped jobs and a green `ci-ok`; the classifier, the verdict and the workflow shape are unit-tested
- own-artifacts-tests-selected: none — unit tests of `--fr-scope` selection and the tripwire run in CI
gate: tester

## Test Plan

- pre-merge — CI: unit tests of `fr.checkstate` and of each R3 reader read `CANCELLED` as pending and `STALE`/`TIMED_OUT` as failing, the check-state tripwire passes, and `slot_check` reports a cancelled required check late after `wait_minutes` (row `ci-cancelled-reads-pending`).
- pre-merge — CI: workflow-shape tests pin `ci.yml`'s concurrency block and `ci-ok`'s `if: always()` (row `ci-superseded-runs`).
- pre-merge — CI: `ci_lane.py landed` over recorded run payloads (an `fr-queue/**` success, a PR run, another workflow, an error) and the workflow shape of the landed lane (`validate-artifacts` kept) (row `ci-landed-skip`).
- pre-merge — CI: queue builder tests over real bare git repos: a whole generated file and a generated block regenerate and build, a stamp conflict takes the newer date, a mixed real conflict hands back naming only the real path, a failing, timed-out or overreaching mirror command hands back; `TriageConfig.generated` loads and facts schema 16 still reads (row `queue-regenerates-generated`).
- pre-merge — CI: `ci_lane.py classify` and `verdict` for each lane, and the workflow shape (`fetch-depth: 0`, lane conditions, `scoped-tests`) (row `ci-light-lane`).
- pre-merge — CI: `--fr-scope` selects `own_artifacts` tests for a docs change, and the tripwire passes over the repo and fails a fixture module that names the root unmarked (row `own-artifacts-tests-selected`).
- post-merge — operator-driven: two quick pushes to one PR leave the first run cancelled, and the PR's head shows only the second run's `ci-ok` (row `ci-superseded-runs`).
- post-merge — operator-driven: the next queue landing's `main` run shows `classify`, `validate-artifacts` and `ci-ok`, green, naming the `fr-queue/**` run (row `ci-landed-skip`).
- post-merge — operator-driven: the next close-out or archive PR runs `scoped-tests` and no shards, with a green `ci-ok` (row `ci-light-lane`).

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-11-24-ci-economy | `derio-net/super-fr` | `2026-11-24-ci-economy` | — |
