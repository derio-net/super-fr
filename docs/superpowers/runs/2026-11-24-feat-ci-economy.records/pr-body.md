<!-- rendered by fr for run 2026-11-24-feat-ci-economy; edit above this line only -->

## Findings

- `s-r1-1` (spec) — R13 'written in whole' excludes docs/reference/cli.md; README stays a real conflict — **fixed**
- `s-r1-2` (spec) — Mirror commands import the combination's fr; no command line or environment named — **fixed**
- `s-r1-3` (spec) — `if: !cancelled()` leaves a SKIPPED ci-ok that GitHub and fr read as passing — **fixed**
- `s-r1-4` (spec) — R4 claims check_wait_minutes reports a cancelled check; slot_check only reports missing ones — **fixed**
- `s-r1-5` (spec) — R3's reader list misses ops/gate and verify_ci; a bare grep tripwire would hit stage 'cancelled' — **fixed**
- `s-r1-6` (spec) — GraphQL statusCheckRollup.state has no CANCELLED; R3 cannot be met by editing _CI_FAIL — **fixed**
- `s-r1-7` (spec) — R7 cache saved on fr-queue/** is invisible to PR and main runs — **fixed**
- `s-r1-8` (spec) — The landed lane drops main's strict fr validate artifacts — **fixed**
- `s-r1-9` (spec) — R5 trusts any successful ci-ok from another run, PR or foreign app included — **fixed**
- `s-r1-10` (spec) — A light-lane ci-ok is tests: ci deliver evidence; the spec is silent — **fixed**
- `s-r1-11` (spec) — R19's tripwire heuristic misses tests that hand REPO_ROOT to an fr reader — **fixed**
- `s-r1-12` (spec) — classify and scoped-tests need full history or the light lane never fires — **fixed**
- `s-r1-13` (spec) — Test Plan lacks pre-merge lines for the unit tests the Verification rows cite, R4 and R14 — **fixed**
- `s-r1-14` (spec) — Design names Worktree.run_argv/changed_paths and config plumbing that do not exist — **fixed**
- `s-r1-15` (spec) — R3's stay-failing list omits STALE and status-context error — **fixed**
- `p1-r1` (plan, phase 1) — verify_ci waits forever (exit 75) on a cancelled gate nothing replaces — **fixed**
- `p1-r2` (plan, phase 1) — settle/evaluate.py still compared bucket == 'pending' for `running` — **fixed**
- `p1-r3` (plan, phase 1) — the check-state tripwire only paired cancel with fail/failure and skipped lists — **fixed**
- `p1-r4` (plan, phase 1) — queue_exec._unreplaced keyed on name alone — **fixed**
- `p2-r1` (plan, phase 2) — test_validate_artifacts_runs_in_every_lane does not pin the strict step's if — **fixed**
- `p2-r2` (plan, phase 2) — landed_run's exact path match is unverified for real fr-queue runs — **fixed**
- `p2-r3` (plan, phase 2) — classify installs uv and Python 3.14 at the head of every run's critical path — **fixed**
- `p2-r5` (plan, phase 2) — light-lane soundness for docs-only PRs depends on R19/R20 (a later phase) — **refuted**
- `p3-r1` (plan, phase 3) — _is_marked counted a mark on one test as marking the whole module — **fixed**
- `p3-r2` (plan, phase 3) — _climbs missed a name holding .parents then indexed, negative indexes and ../.. joins — **fixed**
- `p3-r3` (plan, phase 3) — ROOT_ALIASES is a hand-kept list — **refuted**
- `p4-s1` (plan, phase 4) — A conflicted path with no marker hunk, or not two regular blobs, counted as hunk-resolved — **fixed**
- `p4-s2` (plan, phase 4) — Mirrors run PR-controlled code with the driver's whole environment — **fixed**
- `p4-s3` (plan, phase 4) — A mirror could write the common git dir's hooks or config, which later git calls run — **fixed**
- `p4-s4` (plan, phase 4) — Mirrors inherited the operator's HOME, reaching ~/.config/gh, ~/.ssh, ~/.netrc — **fixed**
- `p4-s5` (plan, phase 4) — Mirrors kept every UV_* not named like a credential, index URLs included — **fixed**
- `p4-s7` (plan, phase 4) — The git-state guard's cached dirs could be redirected through `.git` or `commondir` — **fixed**
- `p4-s8` (plan, phase 4) — The git-state restore followed symlinks in hooks/ — **fixed**
- `p4-s9` (plan, phase 4) — A background child of a mirror could write after the comparison (TOCTOU) — **fixed**
- `p4-acceptance-anchor` (plan, phase 4) — ci-cancelled-reads-pending cited a test the phase 1 review renamed — **fixed**
- `p4-r1` (plan, phase 4) — Worktree.read/write_resolved translated CRLF to LF, rewriting a hunk-resolved CRLF file whole — **fixed**
- `p4-r2` (plan, phase 4) — An unclosed generated-block open marker let later hunks resolve as ours and hid the file tail from _skeleton — **fixed**
- `p4-r3` (plan, phase 4) — An OSError from export_tracked/snapshot_export was not caught, so no abort and no clean hand-back — **fixed**
- `p4-r4` (plan, phase 4) — A mirror's mode-only change is invisible to the stray check and the copy-back — **refuted**
- `l-security-r1` (plan) — A mirror could write a path with a .git component that matches a generated glob, and git add --all ran over it — **fixed**
- `l-security-r2` (plan) — The new lane jobs had no permissions block and kept checkout credentials; GH_TOKEN reached the PR's own ci_lane.py — **fixed**
- `l-security-r3` (plan) — landed_run trusted the API's head_sha filter without re-checking each run — **fixed**
- `l-errors-r1` (plan) — ci_lane fell back to the full lane silently on gh, git and parse failures — **fixed**
- `l-errors-r2` (plan) — settle reported a stranded cancelled check as still running, naming neither it nor the re-run — **fixed**
- `l-errors-r3` (plan) — The ops gate collapsed a cancelled, unreplaced check into pending — **fixed**
- `l-errors-r4` (plan) — verify_ci could wait on a gate holding a cancelled and a successful check with nothing running — **fixed**
- `l-tests-r1` (plan) — Workflow if: conditions were pinned by substring, so `<full> || true` passed — **fixed**
- `l-tests-r2` (plan) — verdict was not tested with failed or cancelled shard jobs or scoped-tests — **fixed**
- `l-tests-r3` (plan) — landed_run was not tested against cancelled/skipped conclusions or another sha — **fixed**
- `l-docs-accuracy-r1` (plan) — Pages said the early conflict probe uses the merge's own rules; it resolves only version and lock files — **fixed**
- `l-docs-accuracy-r2` (plan) — Two places said mirrors run in the combination's worktree; they run in a git-less copy — **fixed**

## Out-of-scope findings

- `p1-r5` (plan, phase 1) — real_glabclient._CI_FAIL still treats canceled as failing — **deferred** → https://github.com/derio-net/super-fr/issues/1670
- `p2-r4` (plan, phase 2) — a manual re-run of an older run in a PR's concurrency group cancels the newer in-progress run — **deferred** → https://github.com/derio-net/super-fr/issues/1671
- `p4-s6` (plan, phase 4) — Mirrors run as the driver's user on its host; no container or VM isolates them — **deferred** → https://github.com/derio-net/super-fr/issues/1672
- `p4-r5` (plan, phase 4) — The mirror shares the operator's uv cache and python installs, which queued code could poison — **deferred** → https://github.com/derio-net/super-fr/issues/1673
- `p4-r6` (plan, phase 4) — Mirror timeout is per command, output is uncapped, killpg after reap has a pid-reuse window — **deferred** → https://github.com/derio-net/super-fr/issues/1674
- `l-out-workflow-permissions` (plan) — ci.yml has no workflow-level permissions block; the older jobs run with the repo's default token — **deferred** → https://github.com/derio-net/super-fr/issues/1675
- `l-out-probe-rules` (plan) — The early conflict probe resolves only version and lock files, so a stamp or generated conflict outside a queue slot still costs a hand-back — **deferred** → https://github.com/derio-net/super-fr/issues/1676

## Review lenses

| Lens | Why | Files examined | Findings |
| --- | --- | --- | --- |
| docs-accuracy | rule `docs/explainers/*.md, docs/*.md, docs/reference/*.md` (docs/explainers/fr-devops-gate.md) | 15 | l-docs-accuracy-r1 fixed, l-docs-accuracy-r2 fixed |
| errors | review-phase phase 1: "every new pending path (verify_ci, queue, settle) must bound its wait and say who is told" | 7 | l-errors-r1 fixed, l-errors-r2 fixed, l-errors-r3 fixed, l-errors-r4 fixed |
| security | spec-review: "queue builds run mirror commands from PR code on the driver host, and main's CI skip trusts a prior run" | 7 | l-security-r1 fixed, l-security-r2 fixed, l-security-r3 fixed |
| tests | spec-review: "the feature changes which tests CI runs and what a green ci-ok certifies" | 5 | l-tests-r1 fixed, l-tests-r2 fixed, l-tests-r3 fixed |

## Pre-merge verification owed

None.

## Post-merge verification owed

- `ci-superseded-runs` — A pull-request CI run superseded by a newer push to the same pull request is cancelled, and the pull request's head reports only the newer run's ci-ok; pushes to main and fr-queue/** and merge groups are never cancelled, and ci-ok is never skipped — only GitHub cancels a run in a concurrency group; the workflow shape is pinned by unit tests this PR's CI runs
- `ci-landed-skip` — A push to main of a sha that already has a successful CI run from an fr-queue push runs only the strict artifact validation and reports a green ci-ok naming that run; any other push to main runs full CI, and the release's pre-publish suite is unchanged — only a real queue landing on `main` has a prior successful `fr-queue/**` run on the sha; `ci_lane.py landed` and the workflow shape are unit-tested
- `ci-light-lane` — A pull request that changes only non-installable paths outside tests/ and .github/ runs the light lane (no shards, collect, split-check or coverage, plus scoped tests) and ci-ok reads the skipped jobs as passing only for that lane — only a real docs-only pull request shows the skipped jobs and a green `ci-ok`; the classifier, the verdict and the workflow shape are unit-tested

## Manual operations

None.

## PR settle

- `git.settle.conflicts`: `fix` (default)
- `git.settle.ci`: `fix` (default)

The repo setting applies.

## Owed actions discharged

None.

## Tests

CI (`ci-ok`) green on `64c1b7a756cccd1c67dc217309ed89c3126c8944` merged with `0160e4677f456c77fe157f3401444d3a2aee9440`.

## Proportionality

```text
proportionality: merge-base 0160e4677f456c77fe157f3401444d3a2aee9440

## Unreferenced new files

- .changes/feat-ci-economy.yaml

## Out-of-plan touches

- docs/herdr-control-sessions.md
- docs/ops.md
- tests/conftest.py
- tests/fixtures/ci_lane/README.md
- tests/fixtures/ci_lane/run_pull_request.json
- tests/fixtures/ci_lane/runs_main_push.json
- tests/fr_scope.py
- tests/scenarios/fixtures/cancelled-terminal-facts.json
- tests/scenarios/fixtures/claims-expired-facts.json
- tests/scenarios/fixtures/claims-held-facts.json
- tests/scenarios/fixtures/config-skew-facts.json
- tests/scenarios/fixtures/retire-sync-facts.json
- tests/scenarios/fixtures/settle-facts.json

## Size

4646 lines changed (+4430 -216; fr artifacts excluded) against an estimate of 2450 (1.9×).

## Phases

4 agentic phases serve 20 of 20 requirements (R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15, R16, R17, R18, R19, R20).
```

## Cost

| step | turns | cost | main turns | main cache-read / output | main cost | subagent turns | subagent cache-read / output | subagent cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| brainstorm | 24 | — | 24 | 4.0M / 29k | — | — | — | — |
| spec-review | 40 | — | 8 | 1.8M / 19k | — | 32 | 3.4M / 34k | — |
| plan | 8 | — | 8 | 2.1M / 20k | — | — | — | — |
| plan-review | — | — | — | — | — | — | — | — |
| implement | 510 | — | 86 | 21.6M / 54k | — | 424 | 62.6M / 307k | — |
| journal-check | — | — | — | — | — | — | — | — |
| lens-review | 103 | — | 30 | 7.0M / 26k | — | 73 | 7.6M / 51k | — |
| deliver | 1 | — | 1 | 265k / 563 | — | — | — | — |
| (outside run) | 53 | — | 53 | 15.5M / 22k | — | — | — | — |
| **total** | | — | | | | | | |

| phase | tier | bound | ran | executor turns | executor cache-read / output | executor cost | reviewer turns | reviewer cache-read / output | reviewer cost | orchestrator turns | orchestrator cache-read / output | orchestrator cost |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | standard | claude-sonnet-5 | claude-opus-5-5 ≠ | 92 | 12.4M / 51k | — | 14 | 1.4M / 14k | — | 32 | 9.3M / 15k | — |
| 2 | hard | claude-opus-5-5 | claude-opus-5-5 | 59 | 7.6M / 43k | — | 4 | 257k / 14k | — | 17 | 5.5M / 11k | — |
| 3 | standard | claude-sonnet-5 | claude-opus-5-5 ≠ | 92 | 10.3M / 47k | — | 8 | 559k / 7.1k | — | 13 | 2.6M / 10k | — |
| 4 | standard | claude-sonnet-5 | claude-opus-5-5 ≠ | 148 | 29.6M / 117k | — | 7 | 478k / 13k | — | 24 | 4.3M / 18k | — |

_`ran` is shown only for an attempt that recorded its bound model; `≠` marks a phase that ran on a different model family._

Sessions: 1 read, 0 unavailable.

_Dollars are `—`: no cost recorded yet. A harness may write a session's cost only when the session ends (Claude Code does). `fr run cost 2026-11-24-feat-ci-economy` reads it afterwards._
