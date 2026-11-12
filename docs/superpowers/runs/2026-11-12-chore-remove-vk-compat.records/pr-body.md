<!-- rendered by fr for run 2026-11-12-chore-remove-vk-compat; edit above this line only -->

## Findings

- `sr-1` (spec) — §3.D: the extra_locators seam does not exist, and the spec does not say which of the runner's four enumerations take it — **fixed**
- `sr-2` (spec) — Making the archive visible to the gate lets a frozen file refuse every gated command, and parses every archived _meta.yaml on every invocation — **fixed**
- `sr-3` (spec) — R10's rewrite rule corrupts the case it names: a block scalar's header line matches the pattern — **fixed**
- `sr-4` (spec) — The spec states its tests nowhere — **fixed**
- `sr-5` (spec) — R2 falsifies a merged acceptance row and has no row of its own — **fixed**
- `sr-6` (spec) — R6: dropping `superpowers-for-vk@` from the sibling-repo grep changes installer output, a pinned test seeds that id, and the row's wording is untrue — **fixed**
- `sr-7` (spec) — R3: shipped guidance still tells the user to run bare `fr isolation up`, which will exit 2 — **fixed**
- `sr-8` (spec) — R7, R9, R11: tests that pin the old behaviour are not named — **fixed**
- `sr-9` (spec) — §2 and §5 say 42 archived plans carry the key; 33 archived `_meta.yaml` files do — **fixed**
- `sr-10` (spec) — R14 is garbled, and R14/R15 miss text this change makes false — **fixed**
- `sr-11` (spec) — R9 changes behaviour for a historical read (`fr status`) and has no acceptance row — **fixed**
- `p1-r1` (plan, phase 1) — Three hook remedies still recommend a bare `fr isolation up` — **fixed**
- `p1-r2` (plan, phase 1) — The R17 tripwire could not see the Claude Code hooks or shell-escaped backticks — **fixed**
- `p1-r3` (plan, phase 1) — The amended row vk-legacy-fallbacks-removed contradicted R2 — **fixed**
- `p1-r4` (plan, phase 1) — The isolation rule and the phase-executor guard gave `fr isolation up --repo <path>` with no --branch — **fixed**
- `p1-r5` (plan, phase 1) — _UP_REMEDY sat between the fr-archive comment and the constant it documents — **fixed**
- `p1-r6` (plan, phase 1) — Small nits in the new tests and two docstrings — **fixed**
- `p1-r7` (plan, phase 1) — .test_durations not refreshed — **fixed**
- `p2-r1` (plan, phase 2) — An archived file whose dry check passes but whose write fails kept the repo stale — **fixed**
- `p2-r2` (plan, phase 2) — fr migrate artifacts said every artifact is current beside an unrepairable file — **fixed**
- `p2-r3` (plan, phase 2) — Test gaps against the spec's section 6 — **fixed**
- `p2-r4` (plan, phase 2) — A gitignored archived carrier lost the whole migration commit — **fixed**

## Out-of-scope findings

None.

## Pre-merge verification owed

None.

## Post-merge verification owed

None.

## Manual operations

None.

## Tests

Full suite run at delivery — `vk-compat-deliver2-suite.log@9a1a9f1d0422`.

## Proportionality

```text
proportionality: merge-base 1ba2b5e664d3a053ba2d362a0eb44a260e7e04be

## Unreferenced new files

- .changes/chore-remove-vk-compat.yaml

## Out-of-plan touches

- .claude/rules/fr-isolation-required.md
- plugins/super-fr/rules/fr-isolation-required.md — justified by p1-r4

## Size

31200 lines changed (+16798 -14402; fr artifacts excluded) against an estimate of 1800 (17.3×).
FLAG: above 2× the estimate — add a justification line to the PR body.

## Phases

2 agentic phases serve 8 of 20 requirements (R1, R3, R4, R6, R7, R10, R11, R13).
```

## Cost

| step | turns | cost | main turns | main cache-read / output | main cost | subagent turns | subagent cache-read / output | subagent cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| brainstorm | 11 | — | 11 | 1.8M / 20k | — | — | — | — |
| spec-review | 24 | — | 4 | 784k / 15k | — | 20 | 3.4M / 30k | — |
| plan | 6 | — | 6 | 1.4M / 14k | — | — | — | — |
| plan-review | — | — | — | — | — | — | — | — |
| implement | 247 | — | 52 | 9.5M / 41k | — | 195 | 26.9M / 124k | — |
| journal-check | — | — | — | — | — | — | — | — |
| deliver | — | — | — | — | — | — | — | — |
| (outside run) | 47 | — | 47 | 9.5M / 48k | — | — | — | — |
| **total** | | — | | | | | | |

| phase | tier | bound | ran | executor turns | executor cache-read / output | executor cost | reviewer turns | reviewer cache-read / output | reviewer cost | orchestrator turns | orchestrator cache-read / output | orchestrator cost |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | standard | claude-sonnet-5 | claude-sonnet-5-5 ≠ | 75 | 8.8M / 32k | — | 19 | 2.7M / 16k | — | 22 | 3.8M / 18k | — |
| 2 | hard | claude-opus-5-5 | claude-opus-5-5 | 85 | 13.2M / 50k | — | 16 | 2.3M / 26k | — | 30 | 5.7M / 22k | — |

_`ran` is shown only for an attempt that recorded its bound model; `≠` marks a phase that ran on a different model family._

Sessions: 1 read, 0 unavailable.

_Dollars are `—`: no cost recorded yet. A harness may write a session's cost only when the session ends (Claude Code does). `fr run cost 2026-11-12-chore-remove-vk-compat` reads it afterwards._
