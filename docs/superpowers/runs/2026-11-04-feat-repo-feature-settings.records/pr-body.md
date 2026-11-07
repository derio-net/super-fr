<!-- rendered by fr for run 2026-11-04-feat-repo-feature-settings; edit above this line only -->

## Findings

- `sr1-1` (spec) — R11 ask gate reuses a predicate that cannot observe answers on most harnesses — **fixed**
- `sr1-2` (spec) — git.pr ask has no fr-owned seam: agents open the PR — **fixed**
- `sr1-3` (spec) — pr_body minimal checks fr's render against itself and the render is deleted — **fixed**
- `sr1-4` (spec) — Repo settings revision unspecified: a branch could turn off its own controls — **fixed**
- `sr1-5` (spec) — Quiet switch: network dependence and fail-open on deleted branch, old fr, plan-1 loaders — **fixed**
- `sr1-6` (spec) — fr branch orphan-ness, contention, solo pushes and append-only underspecified — **fixed**
- `sr1-7` (spec) — Stealth: commands in the target workspace cannot know the run is stealth; CAS push only warns — **fixed**
- `sr1-8` (spec) — Stealth forge-write contradiction and settings precedence undefined — **fixed**
- `sr1-9` (spec) — Stale-base amendments can land; fold ordering and quiet merged-status are wrong — **fixed**
- `sr1-10` (spec) — Fragment migration does not fit the single-file matrix kind; record kind also changes — **fixed**
- `sr1-11` (spec) — Branch self-migration cannot ride the CLI-entry trigger — **fixed**
- `sr1-12` (spec) — squash-unpushed undefined on first push; breaks migration own-commit and merges — **fixed**
- `sr1-13` (spec) — fr push does not own every push fr makes — **fixed**
- `sr1-14` (spec) — Pages visibility check has no reader, is scaffold-time only, ignores GitLab/Gitea — **fixed**
- `sr1-15` (spec) — Derived-report CI/Pages/badge not scoped to repo placement; scaffolded CI files issues — **fixed**
- `sr1-16` (spec) — acceptance off with row gates and walks incoherent — **fixed**
- `sr1-17` (spec) — R7/R8 refusals sit in plan self-review, after spec-review — **fixed**
- `sr1-18` (spec) — Plan split: R18 needs plan-3 resolver; quiet/stealth parts in plan 1 — **fixed**
- `sr1-19` (spec) — OpenCode plugin and Hermes hook detection omitted — **fixed**
- `sr1-20` (spec) — Quiet/stealth artifacts never reach origin/HEAD: dispatch reachability always refuses — **fixed**
- `sr1-21` (spec) — tracking none checks miscounted — **fixed**
- `sr1-22` (spec) — settings exemption justified falsely; paths command missing from R3 — **fixed**
- `sr1-24` (spec) — §3.D names fr/acceptance/ci.py as holding CI templates — **fixed**
- `p1-r1` (plan, phase 1) — load.py _show treats any git show failure as file absent — **fixed**
- `p1-r2` (plan, phase 1) — push-ask driven-triage check read the working tree and passed on parse error — **fixed**
- `p1-r3` (plan, phase 1) — origin present but default unresolved fell back to a local branch — **fixed**
- `p1-r4` (plan, phase 1) — schema: true passed Literal[1] — **fixed**
- `p1-r5` (plan, phase 1) — settings show truncated values to 40 chars — **fixed**
- `p2-o1` (plan, phase 2) — A depth-1 CI PR checkout made fr acceptance check die with a SettingsError traceback — **fixed**
- `p2-r1` (plan, phase 2) — SettingsError surfaced as a raw traceback (exit 1) at most new call sites — **fixed**
- `p2-r2` (plan, phase 2) — A never-fetched remote blocked bootstrap writers (acceptance init/add, debt, archive, deliver) — **fixed**
- `p2-r3` (plan, phase 2) — R15 incomplete: fr-plan, fr-spec-reviewer, fr-progress, fr-devops-gate did not read settings — **fixed**
- `p2-r4` (plan, phase 2) — spec_policy_problems elif reported only one problem — **fixed**
- `p2-r5` (plan, phase 2) — Test gaps in policy-off branches — **fixed**
- `p2-r6` (plan, phase 2) — acceptance: off surface inconsistencies; nag hook spawned fr in every repo — **fixed**
- `p3-residual-triage-forge-writes` (plan, phase 3) — triage claim/approval/closeout label writes and tracker/github.py are not gated by forge_allows — **fixed**
- `p3-r1` (plan, phase 3) — Gate ledger exempted from tracking: none in gate pass but not in deliver's label sync — **fixed**
- `p3-r2` (plan, phase 3) — Ungated forge writes remained; no-checkout gates failed open to defaults — **fixed**
- `p3-r3` (plan, phase 3) — No tripwire for a new ungated forge write — **fixed**
- `p3-r4` (plan, phase 3) — fr-goal §8 filing wording contradicted the code — **fixed**
- `p3-r5` (plan, phase 3) — New quiet write paths untested — **fixed**
- `p3-r6` (plan, phase 3) — fr debt issue's zero-debt close commented under comments: off — **fixed**
- `p3-r7` (plan, phase 3) — forge.issues: off skipped fr debt's forge reads — **fixed**
- `p4-r1` (plan, phase 4) — squash() one-commit shortcut left the commit in the segment — **fixed**
- `p4-r2` (plan, phase 4) — Migration and bookkeeping commits went unrecognised under a template without {type}/{scope} — **fixed**
- `p4-r3` (plan, phase 4) — An ask approval was not tied to the request it approved — **fixed**
- `p4-r4` (plan, phase 4) — fr pr create ignored the run's recorded PR; the pr-<branch> id could be approved only once — **fixed**
- `p4-r5` (plan, phase 4) — push/pr ask required a spec journal, so debugging runs could never push or open a PR — **fixed**
- `p4-r6` (plan, phase 4) — Staleness diff followed renames — **fixed**
- `p4-deliver-r1` (plan, phase 4) — Default commit template refuses scope-less conventional subjects at fr push — **fixed**

## Out-of-scope findings

- `sr1-23` (spec) — DevOps gate already force-pushes with a lease — **deferred** → https://github.com/derio-net/super-fr/issues/1378

## Pre-merge verification owed

None.

## Post-merge verification owed

- `repo-settings-quiet-repo-live` — On a real forge, quiet and stealth fr-goal runs leave no fr trace in the product repo or on its forge — only a real forge and real fr-goal runs in quiet and stealth placements show that no fr trace reaches the product repo or its forge; walked after release

## Manual operations

None.

## Tests

Full suite run at delivery — `deliver-full-suite.log@3e400575aab8`.

## Proportionality

```text
proportionality: merge-base e9f60f460e4834d468ae4fc0a18ce7371528c449

## Unreferenced new files

- .changes/feat-repo-feature-settings.yaml
- packages/fr/src/fr/git_policy/ask.py
- tests/scenarios/fixtures/repo-settings-forge-quiet/bin/gh

## Out-of-plan touches

- .claude/rules/artifact-versioning.md
- packages/fr-dispatch/src/fr_dispatch/__init__.py
- packages/fr-opencode-plugin/src/nag.ts
- packages/fr-opencode-plugin/test/nag.test.ts
- packages/fr-vk/src/fr_vk/pr_state.py
- packages/fr/src/fr/artifacts/agents_kind.py
- packages/fr/src/fr/artifacts/run_usage_split.py
- packages/fr/src/fr/isolation/rename.py
- packages/fr/src/fr/isolation/scaffold.py
- packages/fr/src/fr/ops/trust.py
- packages/fr/src/fr/run/observed.py
- packages/fr/src/fr/run/telemetry.py
- packages/fr/src/fr/tracker/github.py
- packages/fr/src/fr/triage/approval.py
- packages/fr/src/fr/triage/claim_writes.py
- packages/fr/src/fr/triage/gitseam.py
- packages/fr/src/fr/triage/ledger.py
- packages/fr/src/fr/triage/state_ref.py
- plugins/super-fr/agents/fr-spec-reviewer.md
- plugins/super-fr/skills/fr-plan/SKILL.md
- plugins/super-fr/skills/fr-progress/SKILL.md
- tests/conftest.py
- tests/scenarios/cloud-triage-repo-agents.sh
- tests/scenarios/fixtures/merge-train-label-gate/bin/gh
- tests/scenarios/fixtures/triage-closed-settle/bin/gh
- tests/unit/fakes.py
- tests/unit/settings_repo.py
- tests/unit/test_agents_artifact.py
- tests/unit/test_answer_pairs.py
- tests/unit/test_archive_cmd.py
- tests/unit/test_bridge_pr_state.py
- tests/unit/test_debt_cmd.py
- tests/unit/test_debt_issue.py
- tests/unit/test_debt_owed.py
- tests/unit/test_deliver_pr_body_forges.py
- tests/unit/test_exit_label_sync.py
- tests/unit/test_fr_debugging_journal.py
- tests/unit/test_gate_cmd.py
- tests/unit/test_gatebackfill_apply.py
- tests/unit/test_hooks_acceptance_nag.py
- tests/unit/test_merge_train_gate.py
- tests/unit/test_merge_train_label_board.py
- tests/unit/test_migration_run_bound_model.py
- tests/unit/test_migration_run_driver.py
- tests/unit/test_migration_run_fr_version.py
- tests/unit/test_migration_run_v7.py
- tests/unit/test_migration_runner.py
- tests/unit/test_ops_exit_promotion.py
- tests/unit/test_ops_trust.py
- tests/unit/test_run_cli.py
- tests/unit/test_run_closeout.py
- tests/unit/test_run_review_return_resolve.py
- tests/unit/test_skills_read_settings.py
- tests/unit/test_spec_reviewer_inputs.py
- tests/unit/test_tick_workitem.py
- tests/unit/test_tracker.py
- tests/unit/test_tracking_none.py
- tests/unit/test_triage_batch_dispatch.py
- tests/unit/test_triage_batch_drive_cmd.py
- tests/unit/test_triage_batch_merge.py
- tests/unit/test_triage_claim_writes.py
- tests/unit/test_triage_collected_closeout_drive.py
- tests/unit/test_triage_exit_gates_drive.py
- tests/unit/test_triage_state_ref.py
- tests/unit/test_tripwire_forge_writes.py
- tests/unit/test_undispatch_cmd.py

## Size

8577 lines changed (+8262 -315; fr artifacts excluded) against an estimate of 3550 (2.4×).
FLAG: above 2× the estimate — add a justification line to the PR body.

## Phases

4 agentic phases serve 4 of 29 requirements (R2, R6, R9, R11).
```

## Cost

| step | turns | cost | main turns | main cache-read / output | main cost | subagent turns | subagent cache-read / output | subagent cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| brainstorm | 144 | — | 35 | 4.6M / 37k | — | 109 | 8.9M / 41k | — |
| spec-review | 53 | — | 29 | 5.8M / 65k | — | 24 | 2.2M / 34k | — |
| plan | 15 | — | 15 | 4.3M / 21k | — | — | — | — |
| plan-review | 12 | — | 12 | 3.8M / 5.5k | — | — | — | — |
| implement | 1,236 | — | 74 | 13.0M / 69k | — | 1,162 | 202.1M / 698k | — |
| journal-check | — | — | — | — | — | — | — | — |
| deliver | — | — | — | — | — | — | — | — |
| (outside run) | 86 | — | 60 | 10.5M / 29k | — | 26 | 2.3M / 19k | — |
| **total** | | — | | | | | | |

| phase | tier | bound | ran | executor turns | executor cache-read / output | executor cost | reviewer turns | reviewer cache-read / output | reviewer cost | orchestrator turns | orchestrator cache-read / output | orchestrator cost |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | standard | claude-sonnet-5 | claude-sonnet-5-5 ≠ | 66 | 7.7M / 57k | — | 7 | 629k / 9.2k | — | 16 | 3.4M / 13k | — |
| 2 | standard | claude-sonnet-5 | claude-sonnet-5-5 ≠ | 111 | 16.7M / 57k | — | 25 | 2.9M / 15k | — | 25 | 4.0M / 26k | — |
| 3 | hard | claude-opus-5-5 | claude-opus-5-5 | 188 | 35.3M / 106k | — | 40 | 5.3M / 24k | — | 17 | 3.4M / 16k | — |
| 4 | hard | claude-opus-5-5 | claude-opus-5-5 | 210 | 48.8M / 139k | — | 38 | 3.8M / 28k | — | 16 | 2.2M / 15k | — |

_`ran` is shown only for an attempt that recorded its bound model; `≠` marks a phase that ran on a different model family._

Sessions: 1 read, 0 unavailable.

_Dollars are `—`: no cost recorded yet. A harness may write a session's cost only when the session ends (Claude Code does). `fr run cost 2026-11-04-feat-repo-feature-settings` reads it afterwards._
