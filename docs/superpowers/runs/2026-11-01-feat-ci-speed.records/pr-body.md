## Summary

super-fr's CI took a median **810 s** and a release that cut something **600–1000 s** (max 1795 s). This PR finds where the time went, with CI data, and removes it without weakening any gate.

| | before | after (this PR's CI) |
|---|---|---|
| CI wall clock | 810 s median (30 runs) | **261 s** with runners free (run 41340117422); 375–450 s while 3 runs competed for runners (jobs queued 40–120 s) |
| slowest test shard | 792 s (`py3.11, 2`) | 197–216 s |
| `test_dispatch_lint_corpus::…own_plans` | 418.6 s on CI | ~12 s on a loaded laptop |
| release (cutting runs) | 600–1000 s, re-run up to 3× when `main` moved | sharded; walked on first real release (Test Plan 1) |

What was slow, and what changed:
1. **One test was CI's critical path.** It spent 98% of its time in pure-Python PyYAML re-parsing the 10k-line `docs/acceptance/matrix.yaml`, once per plan, for 164 plans. New `fr.yamlio` uses libyaml when present: 4.6 s → 0.25 s per parse, identical result. `parse_matrix` reuses one parse per text and gives each caller its own deep copy. Every consumer repo gets this speed-up (patch fragment).
2. **`.test_durations` was stale**: 6,413 of 13,703 tests, recorded on a laptop. The shard weights now come from CI's own measurements. A `plan` job hands one durations file to every shard, and main's CI saves a fresh one to the Actions cache; the committed file, regenerated here, is the fallback. A new **`split-check`** job fails CI unless the shards together ran exactly the collected tests, each once. It is the guard that makes the faster split safe.
3. **Six shards per leg, coverage on 3.14.** On 3.11, coverage's `settrace` tracer cost ~40%. The fail-under-75 gate now runs on the 3.14 leg (`sys.monitoring`), and 3.11 runs `--no-cov`. Every test and release job has a `timeout-minutes`.
4. **The release is a job graph**: prepare → collect + 6 token-free test shards on the exact staged commit (bundle hand-off, sha verified, `origin/main` pinned to the base, version probe per shard) → split-check → publish. If `main` moved, the release stops as **superseded**: exit 0, and the newest run recomputes. A dispatched `--version` instead exits non-zero with the re-dispatch command. The 3× re-test loop is gone. A rerun after a landed push now tags instead of reporting superseded.
5. **The CI budget watcher had never filed an issue.** `gh api -f ref=` sends a POST, which returned 404, which the watcher read as "renamed?" on every run since 2026-09-26. That is how CI drifted from 155 s to 810 s without an alert. It now uses `-X GET`. Budgets: ci.yml 360 s, release.yml 600 s.

Spec: `docs/superpowers/specs/2026-11-01-ci-speed-design.md` · Plan: `docs/superpowers/plans/2026-11-01-ci-speed/`

## Decisions (operator, two question rounds)

- Long-tail fix: a libyaml helper in `fr`, for all clients. The helper is routed through the matrix path now; the other 104 `safe_load` sites are standardized in #1286 (narrowed because parallel goal runs own those files). The matrix stays one file.
- Shard weights are CI-derived and self-healing · 6 shards per leg · coverage gate on 3.14.
- Release: shard the staged suite · superseded instead of retry.
- Merge queue (round 2, requested by the operator): a design issue, **#1287**, extending #1238, rather than part of this PR. The light-PR / full-queue CI split is decided there.
- Verification: `candidate` (walk passed) + `gate: tester`; the release rows are walked on first real use.

## Issues filed

#1286 (standardize YAML on `fr.yamlio`) · #1287 (merge-queue design) · #1288 (timeouts on the remaining CI jobs) · #1289 (`base_ref` interpolation in change-fragment) · #1290 (tag without GitHub Release on rerun) · #1291 (pending `--version` dispatch dropped by concurrency)

## Operator gates

```
brainstorm: operator gate answered by the operator
```

## Test Plan (post-merge — operator-driven)

1. **First real release after merge** (cost: none — walked on first real use). The release run this merge triggers (an RC while `gate:tester` holds) shows `prepare` → 6 `test` shards → `split-check` → `publish`, and the tag and GitHub Release exist. Record its wall clock beside the 600–1000 s baseline with `fr acceptance set-status --walk … --status walked`.
2. **Superseded** (cost: none — walked on first real use). The first time two merges land within a release's test window, the older run's `publish` logs `superseded` and exits green, and the newer run cuts the release.
3. **Budget watcher** (cost: none). After the merge's CI run, the `CI time budget` workflow's log no longer says `not found … (renamed?)`; a breach opens or updates a `ci-budget` issue.

## Acceptance

- Debt: `ci: 475, walk-owed: 22, not-implemented: 32, …` (`fr acceptance status`). This PR adds 6 rows: 3 are `ci`, and 3 are `walk-owed`, because only post-merge runs exercise them (Test Plan 1–3). They are not CI gaps.
- Rows added since brainstorm: `matrix-parse-libyaml`, `ci-shards-complete`, `ci-coverage-newest-leg` (each `ci`, proven by this PR's CI); `release-staged-suite-sharded`, `release-superseded-not-retried`, `ci-budget-watcher-files-breach` (each `walk-owed`, unit-pinned, with the live proof owed post-merge).

## Notes

- **Proportionality, 13× the estimate:** 20,185 of the 22,510 lines are the regenerated `.test_durations` (13,770 CI-measured entries). The rest is 2,163 added and 162 deleted across 21 files, about 1.3× the 1,730-line estimate. `tests/unit/test_ci_shards.py` changed outside the plan because it pins the old 4-way layout.
- **Job count:** CI went from 17 to 25 jobs. With free runners the critical path is ~4 min. When several PRs push at once, jobs queue against the org's concurrent-job limit (40–120 s seen here). #1287's lighter PR CI is the lever if that becomes the norm.

## Ready checklist (the operator's, not the agent's)

- [ ] CI green
- [ ] Explicit review ok from the operator
- [ ] No commits since that ok (fr's own `chore(fr):` record commits excepted)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<!-- rendered by fr for run 2026-11-01-feat-ci-speed; edit above this line only -->

## Findings

- `sr-1` (spec) — Existing release-script tests pin the recompute loop the spec removes; spec claimed R11 pinned by them unchanged — **fixed**
- `sr-2` (spec) — R14's 600s budget breaks test_release_workflow's >=900 pin; single-job tripwires miss the new jobs — **fixed**
- `sr-3` (spec) — R9 'no forge token' not met by contents: read alone — **fixed**
- `sr-4` (spec) — A superseded --version dispatch silently drops the override; superseded rule stated too broadly — **fixed**
- `sr-5` (spec) — Release split-check has no collect job, no durations source, no timeouts — **fixed**
- `sr-6` (spec) — Release shards see a different origin/main; publish never gets the staged commit — **fixed**
- `sr-7` (spec) — Shard and collect commands under-specified — **fixed**
- `sr-8` (spec) — Coverage-leg pin selects the first upload step (now the junit upload) — **fixed**
- `sr-9` (spec) — Wrong reason given for keeping _StrictLoader pure-Python — **fixed**
- `sr-10` (spec) — R2's shared 'immutable' Matrix still has a mutable dict on Row.levels — **fixed**
- `sr-11` (spec) — Factual slips about the code — **fixed**
- `p1-r1` (plan, phase 1) — Phase acceptance row matrix-parse-libyaml left not-implemented — **fixed**
- `p1-r2` (plan, phase 1) — Change fragment promised repo-internal, unmeasured CI/release speed — **fixed**
- `p1-r3` (plan, phase 1) — Two real-matrix tests each did a full pure-Python parse — **fixed**
- `p1-r4` (plan, phase 1) — Fallback test asserted only loader identity — **fixed**
- `p1-r5` (plan, phase 1) — Invalid-YAML test did not pin the message — **fixed**
- `p1-r6` (plan, phase 1) — yamlio.safe_load returned Any instead of the spec's object — **fixed**
- `p1-r7` (plan, phase 1) — parse_matrix docstring cited R1 for memoization — **fixed**
- `p2-r1` (plan, phase 2) — split_check.py merge wrote cache/test-durations.json without creating cache/ — **fixed**
- `p2-r2` (plan, phase 2) — No test tied the merge -o path to cache/save and cache/restore — **fixed**
- `p2-r3` (plan, phase 2) — split-check hardcoded legs 3.11 3.14 — **fixed**
- `p2-r4` (plan, phase 2) — xdist integration test started from no durations file — **fixed**
- `p2-r5` (plan, phase 2) — test_ci_shards weakened the --group pin — **fixed**
- `p2-r6` (plan, phase 2) — Stale docstring in test_ci_shards — **fixed**
- `p3-r1` (plan, phase 3) — publish rerun after a landed push reported superseded and never tagged — **fixed**
- `p3-r2` (plan, phase 3) — No real non-fast-forward push was tested as race then superseded — **fixed**
- `p3-r3` (plan, phase 3) — test-shard and collect did not self-check HEAD == staged_sha — **fixed**
- `p3-r4` (plan, phase 3) — test-shard/collect bypassed the Commands seam — **fixed**
- `p3-r5` (plan, phase 3) — --dry-run and top-level --version were silently ignored with a subcommand — **fixed**
- `p3-r6` (plan, phase 3) — RC, floor and gate-unknown outcomes were untested through the job graph — **fixed**
- `p3-r7` (plan, phase 3) — Least-privilege publish env was unpinned — **fixed**
- `p3-r8` (plan, phase 3) — Docs overstated 'no token at all' and omitted the cron fallback — **fixed**
- `p3-r9` (plan, phase 3) — AGENTS.md still described a single-process release — **fixed**

## Out-of-scope findings

- `p2-r7` (plan, phase 2) — Pre-existing CI jobs have no timeout-minutes — **deferred** → https://github.com/derio-net/super-fr/issues/1288
- `p2-r8` (plan, phase 2) — change-fragment interpolates github.base_ref into run: — **deferred** → https://github.com/derio-net/super-fr/issues/1289
- `p3-r10` (plan, phase 3) — A gh release create failure after the tag push leaves a tag with no GitHub Release — **deferred** → https://github.com/derio-net/super-fr/issues/1290
- `p3-r11` (plan, phase 3) — Concurrency cancels a pending workflow_dispatch --version run — **deferred** → https://github.com/derio-net/super-fr/issues/1291

## Pre-merge verification owed

None.

## Post-merge verification owed

- `ci-budget-watcher-files-breach` — The CI budget watcher reads the run's workflow file at its commit and files or updates a ci-budget issue when the run is over budget — the watcher runs only on `workflow_run` events in this repo; walked on its first run after merge
- `release-staged-suite-sharded` — A release proves its exact staged commit with the full suite in 6 token-free shards, each checking the new fr version, and pushes only when all are green; every existing release outcome still happens — only a real Release run on `main` exercises prepare → sharded test → publish with the app token and the bundle hand-off; walked on first real use (an RC cut counts)
- `release-superseded-not-retried` — When main moved past the commit a release was staged on, the release exits green as superseded without pushing, and the run that push triggered releases instead — needs two pushes to `main` racing a real release run; walked on first real use, unit tests pin the decision

## Manual operations

None.

## Tests

CI (`ci-ok`) green on `f4dcad32edd7a812e27bed41877a0c47e4bc04aa` merged with `unknown`.

## Proportionality

```text
proportionality: merge-base d0d7af454250142f713dbaaeb15d06c9acddc631

## Unreferenced new files

- .changes/feat-ci-speed.yaml

## Out-of-plan touches

- AGENTS.md — justified by p3-r9, p3-r9-resolved
- tests/unit/test_ci_shards.py

## Size

22510 lines changed (+15934 -6576; fr artifacts excluded) against an estimate of 1730 (13.0×).
FLAG: above 2× the estimate — add a justification line to the PR body.

## Phases

3 agentic phases serve 6 of 14 requirements (R1, R4, R7, R8, R10, R13).
```

## Cost

| step | turns | cost | main turns | main cache-read / output | main cost | subagent turns | subagent cache-read / output | subagent cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| brainstorm | 60 | — | 60 | 10.8M / 54k | — | — | — | — |
| spec-review | 42 | — | 10 | 2.5M / 14k | — | 32 | 3.2M / 34k | — |
| plan | 8 | — | 8 | 2.3M / 12k | — | — | — | — |
| plan-review | — | — | — | — | — | — | — | — |
| implement | 240 | — | 49 | 16.1M / 35k | — | 191 | 18.6M / 169k | — |
| journal-check | — | — | — | — | — | — | — | — |
| deliver | — | — | — | — | — | — | — | — |
| (outside run) | 13 | — | 13 | 3.3M / 6.7k | — | — | — | — |
| **total** | | — | | | | | | |

| phase | tier | bound | ran | executor turns | executor cache-read / output | executor cost | reviewer turns | reviewer cache-read / output | reviewer cost | orchestrator turns | orchestrator cache-read / output | orchestrator cost |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | standard | sonnet | claude-sonnet-5-5 ≠ | 21 | 1.6M / 8.4k | — | 22 | 1.0M / 13k | — | 17 | 5.1M / 11k | — |
| 2 | standard | sonnet | claude-sonnet-5-5 ≠ | 25 | 2.4M / 20k | — | 15 | 842k / 22k | — | 17 | 5.6M / 12k | — |
| 3 | hard | opus | claude-opus-5-5 ≠ | 39 | 5.1M / 49k | — | 25 | 2.1M / 30k | — | 15 | 5.3M / 12k | — |

_`ran` is shown only for an attempt that recorded its bound model; `≠` marks a phase that ran on a different model family._

Sessions: 1 read, 0 unavailable.

_Dollars are `—`: no cost recorded yet. A harness may write a session's cost only when the session ends (Claude Code does). `fr run cost 2026-11-01-feat-ci-speed` reads it afterwards._
