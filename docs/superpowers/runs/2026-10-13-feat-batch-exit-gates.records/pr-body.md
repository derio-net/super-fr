## Summary

Batch `exit-gates`. Each PR now declares how it exits, and fr routes it from that declaration instead of from prose.

- **The exit.** A run's verification kinds and its gates (`developer`, `reviewer`, `tester`, `devops`, `owner`, `security`) are computed from the spec's `## Verification` section. That includes new `gate:` lines, a manifest `gate:` at schema 2, and a `.fr/triage.yaml` `exit:` remap. `fr verification exit` prints it.
- **Labels and downgrade guard.** The PR carries `verification:<kind>` and `gate:<g>` labels, synced at brainstorm, spec-review and deliver. `fr verification set` changes the exit, and lowering it after spec-review needs the operator. That holds for hand edits too: `deliver` compares against a baseline recorded when spec-review resolved.
- **`deliver` accounts for leftovers.** It refuses any out-of-scope finding, owed entry, owed row or narrowing that no post-merge gate holds and no filed issue tracks; `fr journal file` files it. It refuses `Closes #n` for an issue that a gated or post-merge row holds open, or that an agent-decided narrowing names. New decision tokens `decided_by=` / `remainder_tracked_by=` are invisible to released fr; the record kind moves 9 → 10.
- **Driver routing.** A merged batch carrying `gate:tester|devops` is never closed out until the gate passes, by its rows being walked on `main` or by `fr gate pass`. `post_merge` now runs at merge for every landed batch, so testers walk the merged build.
- **Board lanes.** Needs you · Developer / Reviewer / Tester / DevOps, read from the run cursor and the gate labels, never from session status. A CONFLICTING or DIRTY PR never reads `merge ready`.
- **Collected close-out (#667).** `fr triage batch closeout` handles one session and one housekeeping PR per repo. The PR merges without `approved-fr` only at the exact head, file set (archive paths only), members and `Closes` set that the verb recorded on the operator's host; anything else needs review. It gets one hand-back, then the operator.
- **Release gating.** Each push cuts `vX.Y.Z-rc.N` (a pre-release, consuming no fragment) while any change merged since the last final still waits on a post-merge gate, and cuts the final once none does. An unknown gate state means an RC. `release.py` does the one credentialed forge read; `fr release status` decides from it with no token.
- **Install channels.** `bootstrap.sh --version` takes nothing (latest release), `RC`, `X.Y.Z`, `X.Y.Z-RC`, `X.Y.Z-rc.N` or `main`. `install.sh` accepts a clean checkout at a release tag.
- **#1155.** A row's own `verify:` is checked even when its spec has no `## Verification` section.

Spec: `docs/superpowers/specs/2026-10-14-exit-gates-design.md` · Plan: `docs/superpowers/plans/2026-10-14-exit-gates`

Closes derio-net/super-fr#1189
Closes derio-net/super-fr#1155
Closes derio-net/super-fr#667

### Decisions

These are the operator's answers from two question rounds; full text is in the spec journal.

- **Labels and gates.** One label per kind; the gate is declared apart from the kind; manifest `gate:` plus a `.fr/triage.yaml` remap, with a spec `gate:` line overriding both.
- **Gate passes.** A gate passes by its rows walked on `main` or by `fr gate pass`. The merged PR's labels are the ledger.
- **Leftovers and narrowing.** Leftovers are filed at `deliver`, so close-out decides nothing. A narrowing must be the operator's answer.
- **Close-out.** One collected close-out per queue, ready once clean, no `approved-fr`. A gated batch stays out of close-out until it passes.
- **Releases.** An RC is a commit plus a tag with RC versions. The final is automatic once nothing waits.
- **Install channel.** The channel lives in `bootstrap.sh`.
- **Verification.** `candidate`, plus `live` rows for the real forge, driver and release.

**Note on `Closes` vs `Refs`.** This feature's own rule says an issue held by a post-merge gate gets `Refs`. The batch's delivery rules ask for `Closes` on all three members, so no acceptance row here cites a member issue, and merging closes all three. The four live rows stay walk-owed in the matrix, so nothing is lost.

**Note on `main`'s protection (#1200).** `main` has no required review or checks today. On this repo, the close-out auto-merge guards are therefore the only barrier on that path. Consider `scripts/configure-main-protection.sh --stage require` (docs/merge-protection.md).

**Proportionality.** 2.1× the estimate is justified. Four review rounds hardened security-relevant paths well beyond the plan: the close-out trust anchor, credential isolation in release, provenance of operator decisions, and old-reader compatibility tests that vendor fr 5.26's reader. Each fix carries red-first tests, and roughly 60% of the added lines are tests.

### Out-of-scope findings filed

#1197 (sr-25), #1198 (p3-r10), #1199 (p5-r11), #1200 (p6b-r11), #1201 (p7-r8), #1202 (p8-r6).

### Operator gates

```
brainstorm: operator gate answered by the operator
```

### Test Plan (post-merge — operator-driven)

1. **Labels.** Open a batch whose spec says `strategy: candidate` and `gate: tester`. Its PR carries `verification:candidate` and `gate:tester`. After spec-review, `fr verification set --gate none` without `--answered-by operator` is refused.
2. **Routing.** Merge that batch. It shows under Needs you · Tester. It is not closed out, and its `Refs` issue stays open with `fr:awaiting-live`. Walk its row with `set-status --walk` and merge that walk. The next drive pass swaps the label to `gate:tester-passed`.
3. **Collected close-out.** With two or more landed batches that are not gated, one collected close-out opens ONE housekeeping PR. The driver marks it ready and merges it once it is clean. The passed batch's Test Plan outcomes are recorded, and its `Refs` issue closes.
4. **Release.** While step 2's PR is unpassed, a push to `main` cuts `vX.Y.Z-rc.N` as a pre-release. After the pass, the next run cuts the final `vX.Y.Z`. `bootstrap.sh --version RC` installs the RC; with no argument it installs the final.

### Acceptance

- **Rows added (10), all citing the spec's requirements.**
  - `exit-gates-declared-exit`, `-set-downgrade`, `-verify-without-section`: `ci`, candidate scenarios walked pre-merge. Business claim: the exit and its guard are computable offline.
  - `exit-gates-deliver-accounting`, `-board-lanes`, `-install-channels`: `ci`. Business claim: what `deliver`, the board and the installer guarantee to the operator.
  - `exit-gates-pr-labels`, `-driver-routing`, `-collected-closeout`, `-release-gating`: `walk-owed`. Only the real forge, driver and release show them, which is the Test Plan above.
- **Acceptance debt (repo-wide):** `ci: 444, manual: 1, not-implemented: 32, scheduled: 1, unwired: 1, walk-owed: 19, walked: 23`. Of that, this PR adds four walk-owed rows.

### Ready checklist (operator)

- [ ] CI green
- [ ] Explicit review ok from the operator on this PR
- [ ] No commits since that ok (fr's own `chore(fr):` record commits excepted)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<!-- rendered by fr for run 2026-10-13-feat-batch-exit-gates; edit above this line only -->

## Findings

- `sr-1` (spec) — R19 (never plan merge for a CONFLICTING PR) removes the trigger of the conflict hand-back it says is unchanged, and stops version-file auto-resolution — **fixed**
- `sr-2` (spec) — R1 builds the gate set from rows alone, so a DevOps gate with no row or a run-level gate: on a run with no rows can never be declared — **fixed**
- `sr-3` (spec) — Release tooling cannot read an RC version once one is on main: the next final crashes, and the version-sync check reports drift — **fixed**
- `sr-4` (spec) — §G's 'nothing new merged since the newest tag → no-op' blocks the final that R20, q10 and Test Plan step 4 promise after a gate pass — **fixed**
- `sr-5` (spec) — Tag channels fail on any tag whose install.sh predates R23, including the default channel right after this PR — **fixed**
- `sr-6` (spec) — An RC install (X.Y.ZrcN) does not satisfy fr_version floors that name the predicted final — **fixed**
- `sr-7` (spec) — R10/§C misdescribe the archive filer: --issues files follow-up issues, fr:owed is the separate owed-entry path, and --no-issues still files — **fixed**
- `sr-8` (spec) — The collected close-out leaves out Test Plan outcomes, so fr archive holds every plan whose spec has a Test Plan — **fixed**
- `sr-9` (spec) — attributed does not compare the PR head with event.archive, so a shared close-out branch is not attributed — **fixed**
- `sr-10` (spec) — 'Existing hand-back machinery with a budget of one' for the collected close-out PR is undefined — **fixed**
- `sr-11` (spec) — §C's claim that 'held by a post-merge gate' is a superset of 'post-merge' is false under remaps, which weakens the existing Closes guard — **fixed**
- `sr-12` (spec) — PR label sync and gate-pass comments have no adapter method for MRs — **fixed**
- `sr-13` (spec) — Adding gate: to StrategyManifest is not free: extra=forbid with schema Literal[1] — **fixed**
- `sr-14` (spec) — The per-row gate= token makes an older fr raise SectionError on the spec — **fixed**
- `sr-15` (spec) — §C leaves the record-kind stamp to plan time, but the rule already decides it — **fixed**
- `sr-16` (spec) — R11/R12's 'answered by the operator' has no mechanism for a decision entry, and narrows= encoding is unspecified — **fixed**
- `sr-17` (spec) — R9's 'deferred item' is accounted by definition; owed entries and rows tracked by issues: are not addressed — **fixed**
- `sr-18` (spec) — R15 does not say which Refs issues a close-out closes; issues R11 kept as Refs (narrowed) would be closed — **fixed**
- `sr-19` (spec) — R24 widens the brainstorm warning to all four row checks, but it only ran the install check; the reason-check fix changes other rows — **fixed**
- `sr-20` (spec) — 'held' already names three other states in the driver, and 'gate' already names the workflow step gate: operator — **fixed**
- `sr-21` (spec) — Background says the board does not read mergeable/mergeStateStatus, but the triage page and kanban already do, with a different conflict test — **fixed**
- `sr-22` (spec) — TriageConfig.exit also moves FACTS_SCHEMA, and an older fr refuses a .fr/triage.yaml that sets it — **fixed**
- `sr-23` (spec) — An operator-approved narrowing still allows Closes with no follow-up (the audit's first pattern) — **fixed**
- `sr-24` (spec) — The new release group's migration-gate status and fr verification set's insert behaviour are unspecified — **fixed**
- `p1-r1` (plan, phase 1) — a gate: <row>= line naming a row id no row citing the spec has is silently ignored, so a typo drops a post-merge gate — **fixed**
- `p1-r2` (plan, phase 1) — remap_problem is only a CLI stderr warning: missing from --json, UnicodeDecodeError not caught, later consumers need to fail closed — **fixed**
- `p1-r3` (plan, phase 1) — a section with only gate: lines exists for this fr but not for a released fr, so effective strategies diverge under version skew — **fixed**
- `p1-r4` (plan, phase 1) — the brainstorm warning passes shape_default=None, so rows on the shape default miss reason/scenario checks — **fixed**
- `p1-r5` (plan, phase 1) — Exit.rank is a max over kinds, so R8's per-row downgrade guard cannot use it; expose per-row kinds — **fixed**
- `p1-r6` (plan, phase 1) — the remap is read from the working tree while the driver reads the default branch; deliver and the driver could compute different exits — **fixed**
- `p1-r7` (plan, phase 1) — exit.gates remap keys are unvalidated (a typo'd kind, or none) and ignored silently — **fixed**
- `p1-r8` (plan, phase 1) — spec §A says an older collector refuses exit:; since gh#998 parse_triage_config drops unknown top-level keys — **fixed**
- `p2-r1` (plan, phase 2) — early label sync never fires: _emitted_pr finds only deliver's pr; tests monkeypatched it — **fixed**
- `p2-r2` (plan, phase 2) — guard/early sync keyed on literal step id spec-review; fr-goal-light's spec-plan-review leaves the R8 guard off — **fixed**
- `p2-r3` (plan, phase 2) — hand-editing ## Verification after spec-review lowers the exit unchecked — **fixed**
- `p2-r4` (plan, phase 2) — operator-answer window is since spec-review done — **fixed**
- `p2-r5` (plan, phase 2) — unverified advisory not persisted in the exit-change decision — **fixed**
- `p2-r6` (plan, phase 2) — unreadable exit only warns at deliver — **fixed**
- `p2-r7` (plan, phase 2) — deliver warns on any PrNotFound incl. GitHub no-open-PR — **fixed**
- `p2-r8` (plan, phase 2) — post-merge gate swapped for another is not a lowering — **fixed**
- `p2-r9` (plan, phase 2) — set accepts an unresolvable strategy — **fixed**
- `p2-r10` (plan, phase 2) — row change overwrites rationale; gate-only set inexpressible — **fixed**
- `p2-r11` (plan, phase 2) — labels created before the forge is known to support them — **fixed**
- `p2-r12` (plan, phase 2) — a no-op set still journals and commits — **fixed**
- `p2-r13` (plan, phase 2) — set_cmd prints spec_rel with Rich markup — **fixed**
- `p3-older-fr-refuses-decision-tokens` (plan, phase 3) — A released fr refuses answered_by= and tracked_by= on a decision, so spec §C's "an older fr ignores them" holds only for gate= and narrows= — **fixed**
- `p3-r1` (plan, phase 3) — released fr refuses answered_by=/tracked_by= on a decision; every operator-answered spec journal would become unparseable — **fixed**
- `p3-r2` (plan, phase 3) — brainstorm-gate stamp marks unasked narrows= decisions operator, waiving R11 — **fixed**
- `p3-r3` (plan, phase 3) — stamp reads the claimed answered_by, not the derived provenance — **fixed**
- `p3-r4` (plan, phase 3) — _journals silently drops an unparseable journal — **fixed**
- `p3-r5` (plan, phase 3) — an owed row's tracking issue can be closed by Closes #n — **fixed**
- `p3-r6` (plan, phase 3) — plan_filing defers in-scope open findings — **fixed**
- `p3-r7` (plan, phase 3) — old-reader test never exercised answered_by/tracked_by — **fixed**
- `p3-r8` (plan, phase 3) — migration description omits filed_as — **fixed**
- `p3-r9` (plan, phase 3) — no e2e deliver under tracking none with an unfiled finding — **fixed**
- `p4-gated-post-merge-delayed` (plan, phase 4) — A gated batch's post_merge waits for its gate, yet the tester walks the merged build — **fixed**
- `p4-r1` (plan, phase 4) — failed merged-PR label read leaves the batch ungated and closes it out (fail-open) — **fixed**
- `p4-r2` (plan, phase 4) — gated batch's post_merge deferred until its gate passes; needs_you hid it — **fixed**
- `p4-r3` (plan, phase 4) — run-level gate no row inherits auto-passed via an unrelated row gate — **fixed**
- `p4-r4` (plan, phase 4) — pass_gate swaps labels before commenting; a failed comment is lost — **fixed**
- `p4-r5` (plan, phase 4) — fr gate pass accepts an unmerged PR — **fixed**
- `p4-r6` (plan, phase 4) — fr gate pass --repo always builds a github.com client — **fixed**
- `p4-r7` (plan, phase 4) — per-pass cost: pr_view per batch, fetch per gated batch, worktree in plan mode — **fixed**
- `p4-r8` (plan, phase 4) — awaiting-live re-added every pass, spec said first pass — **fixed**
- `p4-r9` (plan, phase 4) — release command printed while other gates still hold — **fixed**
- `p5-r1` (plan, phase 5) — merge stops never reach Needs you now; board lane and Needs-you disagree (§F) — **fixed**
- `p5-r2` (plan, phase 5) — ledger-unread batch placed in Needs you · Developer — **fixed**
- `p5-r3` (plan, phase 5) — duplicate approve-pr and needs-reviewer rows — **fixed**
- `p5-r4` (plan, phase 5) — reviewer lane hint outranks red-CI hints — **fixed**
- `p5-r5` (plan, phase 5) — stop vs gate precedence differs between hint and column — **fixed**
- `p5-r6` (plan, phase 5) — Tester/DevOps reason names one gate and not what is owed — **fixed**
- `p5-r7` (plan, phase 5) — conflicting hint covers only merge, not enqueue — **fixed**
- `p5-r8` (plan, phase 5) — matrix row cites one test for R17+R19 — **fixed**
- `p5-r9` (plan, phase 5) — SKILL lanes paragraph left the --refresh parenthetical dangling — **fixed**
- `p5-r10` (plan, phase 5) — Need.kind comment missing the lane kinds — **fixed**
- `p6-r1` (plan, phase 6) — undeclared holds taken back and re-collected every pass, no Needs-you row — **fixed**
- `p6-r2` (plan, phase 6) — take-back last-event-only and skipped on fail/crash; leftover event marks a held batch archived — **fixed**
- `p6-r3` (plan, phase 6) — closeout-held only in the driver Snapshot; board disagrees — **fixed**
- `p6-r4` (plan, phase 6) — one unreadable member fails the whole verb — **fixed**
- `p6-r5` (plan, phase 6) — collected PR closed unmerged wedges the repo — **fixed**
- `p6-r6` (plan, phase 6) — auto-merge with no file allowlist after a code-fixing hand-back — **fixed**
- `p6-r7` (plan, phase 6) — verify-merge exit 2 tolerance too broad — **fixed**
- `p6-r8` (plan, phase 6) — issues closed at PR open, not merge — **fixed**
- `p6-r9` (plan, phase 6) — re-run on a pushed branch fails non-ff with no recovery — **fixed**
- `p6b-r1` (plan, phase 6) — review-free allowlist admitted workflows/verifications (code execution) and acceptance status — **fixed**
- `p6b-r2` (plan, phase 6) — fabricated green CI with no check results — **fixed**
- `p6b-r3` (plan, phase 6) — forge file list truncated, rename-blind, unbound to the merge head — **fixed**
- `p6b-r4` (plan, phase 6) — membership and Closes from the editable PR body — **fixed**
- `p6b-r5` (plan, phase 6) — resume trusted a fork PR on the branch name — **fixed**
- `p6b-r6` (plan, phase 6) — a failed hand run leaves an open marker that wedges the repo — **fixed**
- `p6b-r7` (plan, phase 6) — named or hand run while a close-out is in flight collides — **fixed**
- `p6b-r8` (plan, phase 6) — --branch not validated — **fixed**
- `p6b-r9` (plan, phase 6) — transient read error became a durable hold — **fixed**
- `p6b-r10` (plan, phase 6) — unbounded hand-backs with no members; reopened PR never re-observed — **fixed**
- `p7-r1` (plan, phase 7) — untagged RC at HEAD recomputes the same RC; every later run refuses — **fixed**
- `p7-r2` (plan, phase 7) — merged-PR read trusts the eventually consistent search index; no --base main — **fixed**
- `p7-r3` (plan, phase 7) — bump and lock-check inherit write tokens while the spec claims otherwise — **fixed**
- `p7-r4` (plan, phase 7) — FR_RELEASE_STATUS_TOKEN described as read-only but is the write-capable github.token — **fixed**
- `p7-r5` (plan, phase 7) — failed or capped gate read blocks RCs too — **fixed**
- `p7-r6` (plan, phase 7) — removed major fragment moves the version backwards — **fixed**
- `p7-r7` (plan, phase 7) — human fr release status truncates silently and reads unfetched tags — **fixed**
- `p8-r1` (plan, phase 8) — installable_tags returns 1 when the lexically-last tag is unmarked; --version X.Y.Z/RC exit 1 silently under set -e — **fixed**
- `p8-r2` (plan, phase 8) — bootstrap.sh header and clone comment describe the old main-only behaviour — **fixed**
- `p8-r3` (plan, phase 8) — refusal listing ranks a final below its own RCs — **fixed**
- `p8-r4` (plan, phase 8) — install.sh accepts any ^v[0-9] tag, looser than bootstrap — **fixed**
- `p8-r5` (plan, phase 8) — no test for Channel: main on main, nor for a forwarded argument with spaces — **fixed**

## Out-of-scope findings

- `sr-25` (spec) — The triage page counts mergeStateStatus BLOCKED as a conflict — **deferred** → https://github.com/derio-net/super-fr/issues/1197
- `p3-r10` (plan, phase 3) — verify_operator_answer opens its window at 1970 on an empty journal and accepts any answer since the journal last moved — **deferred** → https://github.com/derio-net/super-fr/issues/1198
- `p5-r11` (plan, phase 5) — a run blocked on a gate before its batch PR exists cannot reach Needs you · Developer — **deferred** → https://github.com/derio-net/super-fr/issues/1199
- `p6b-r11` (plan, phase 6) — main has no required review or checks, so the auto-merge guards are the only barrier once approved-fr is bypassed — **deferred** → https://github.com/derio-net/super-fr/issues/1200
- `p7-r8` (plan, phase 7) — fr.cloud._version_tuple cannot parse X.Y.ZrcN; the cloud doctor's fr-version check reports ok on an RC install — **deferred** → https://github.com/derio-net/super-fr/issues/1201
- `p8-r6` (plan, phase 8) — untracked files in the managed cache survive a channel switch, so preflight refuses until a manual clean — **deferred** → https://github.com/derio-net/super-fr/issues/1202

## Pre-merge verification owed

None.

## Post-merge verification owed

- `exit-gates-pr-labels` — A run's PR carries one verification:<kind> label per kind and one gate:<gate> label per post-merge gate, kept in sync as the spec changes. — only a real forge shows the labels a real run's PR carries
- `exit-gates-driver-routing` — A merged batch held by a post-merge gate is not closed out and keeps its Refs issues open under its Needs-you lane until its rows are walked on main or fr gate pass records the pass, which swaps the label to gate:<g>-passed. — a gated batch and its gate pass need a real merged PR, driver and matrix on main
- `exit-gates-collected-closeout` — Every landed, not-held batch of a repo closes out in one session with one housekeeping PR that the driver marks ready and merges once clean, closing passed batches' Refs issues; one reconcile attempt, then the operator. — one close-out over a real merged queue needs real merges and a real housekeeping PR
- `exit-gates-release-gating` — A push to main cuts a vX.Y.Z-rc.N pre-release while any change merged since the last final waits on a post-merge gate, and the final vX.Y.Z once none does; fr release status lists what still waits. — an RC and the final after it need release.yml on the real main

## Tests

CI (`ci-ok`) green on `563c1dceadf01b3130742a6b9465409b106e8519` merged with `unknown`.

## Proportionality

```text
proportionality: merge-base 0cafb9a9e2123e92df0c58625cb8cce22126909d

## Unreferenced new files

- .changes/feat-batch-exit-gates.yaml
- packages/fr/src/fr/verification/set.py

## Out-of-plan touches

- .claude/rules/artifact-versioning.md
- .opencode/instructions/artifact-versioning.md
- AGENTS.md — justified by p7-r4-resolved
- packages/fr/src/fr/commands/triage_kanban_cmd.py
- packages/fr/src/fr/journal/operator.py
- packages/fr/src/fr/run/telemetry.py
- packages/fr/src/fr/triage/cursor.py
- packages/fr/src/fr/triage/lanes.py
- packages/fr/src/fr/triage/ledger.py
- packages/fr/src/fr/triage/render.py
- packages/fr/src/fr/verifications/live.yaml
- scripts/versions.py
- tests/conftest.py
- tests/integration/test_fr_goal_shape.py
- tests/integration/test_install_channels.py
- tests/scenarios/fixtures/cancelled-terminal-facts.json
- tests/scenarios/fixtures/claims-expired-facts.json
- tests/scenarios/fixtures/claims-held-facts.json
- tests/scenarios/fixtures/config-skew-facts.json
- tests/unit/fakes.py
- tests/unit/test_deliver_leftovers.py
- tests/unit/test_deliver_pr_body.py
- tests/unit/test_exit_label_sync.py
- tests/unit/test_exit_label_sync_points.py
- tests/unit/test_exit_pr_adapter.py
- tests/unit/test_fr_triage_skill_example.py
- tests/unit/test_merge_train_approval.py
- tests/unit/test_merge_train_commands.py
- tests/unit/test_row_verification_issues.py
- tests/unit/test_skill_services_prose.py
- tests/unit/test_spec_section_rewrite.py
- tests/unit/test_version_rc.py
- tests/unit/triage_fixtures.py

## Size

14049 lines changed (+13494 -555; fr artifacts excluded) against an estimate of 6850 (2.1×).
FLAG: above 2× the estimate — add a justification line to the PR body.

## Phases

8 agentic phases serve 17 of 27 requirements (R1, R5, R7, R8, R9, R11, R13, R14, R15, R16, R17, R19, R20, R21, R22, R23, R24).
```

## Cost

| step | turns | cost | main turns | main cache-read / output | main cost | subagent turns | subagent cache-read / output | subagent cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| brainstorm | 41 | — | 41 | 7.1M / 51k | — | — | — | — |
| spec-review | 61 | — | 8 | 2.0M / 28k | — | 53 | 7.2M / 1.3k | — |
| plan | 9 | — | 9 | 2.6M / 18k | — | — | — | — |
| plan-review | — | — | — | — | — | — | — | — |
| implement | 1,521 | — | 164 | 69.4M / 106k | — | 1,357 | 323.9M / 20k | — |
| journal-check | — | — | — | — | — | — | — | — |
| deliver | — | — | — | — | — | — | — | — |
| (outside run) | 13 | — | 13 | 5.3M / 6.1k | — | — | — | — |
| **total** | | — | | | | | | |

| phase | tier | bound | ran | executor turns | executor cache-read / output | executor cost | reviewer turns | reviewer cache-read / output | reviewer cost | orchestrator turns | orchestrator cache-read / output | orchestrator cost |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | standard | sonnet | claude-sonnet-5-5 ≠ | 46 | 5.3M / 555 | — | 19 | 2.1M / 420 | — | 25 | 7.9M / 16k | — |
| 2 | standard | sonnet | claude-sonnet-5-5 ≠ | 143 | 30.3M / 1.5k | — | 37 | 4.6M / 379 | — | 28 | 10.0M / 17k | — |
| 3 | hard | opus | claude-opus-5-5 ≠ | 273 | 79.4M / 4.5k | — | 30 | 3.5M / 432 | — | 20 | 7.9M / 14k | — |
| 4 | hard | opus | claude-opus-5-5 ≠ | 188 | 56.2M / 2.8k | — | 26 | 3.2M / 577 | — | 15 | 6.3M / 10k | — |
| 5 | standard | sonnet | claude-sonnet-5-5 ≠ | 51 | 6.3M / 752 | — | 30 | 3.6M / 433 | — | 15 | 6.7M / 8.8k | — |
| 6 | hard | opus | claude-opus-5-5 ≠ | 254 | 90.7M / 3.5k | — | 22 | 2.6M / 363 | — | 29 | 13.8M / 20k | — |
| 7 | hard | opus | claude-opus-5-5 ≠ | 119 | 23.0M / 1.7k | — | 25 | 3.0M / 307 | — | 17 | 8.7M / 12k | — |
| 8 | standard | sonnet | claude-sonnet-5-5 ≠ | 24 | 2.0M / 339 | — | 16 | 1.6M / 181 | — | 15 | 8.0M / 8.3k | — |

_`ran` is shown only for an attempt that recorded its bound model; `≠` marks a phase that ran on a different model family._

Sessions: 1 read, 0 unavailable.

_Dollars are `—`: no cost recorded yet. A harness may write a session's cost only when the session ends (Claude Code does). `fr run cost 2026-10-13-feat-batch-exit-gates` reads it afterwards._
