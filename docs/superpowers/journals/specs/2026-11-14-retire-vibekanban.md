<!-- fr:journal-schema=4 -->
# Journal: 2026-11-14-retire-vibekanban

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-14T21:22:30+00:00 input=true -->
### operator-brief · discovery · Operator brief — batch retire-vk (super-fr#1459)

/fr-goal Retire VibeKanban support

Batch `retire-vk` of derio-net/super-fr: 1 issues, delivered as ONE pull request.

## super-fr#1459: Drop VibeKanban support (fr-vk adapter, bridge, VK dispatch conventions)
Decision recorded: drop VibeKanban (its only deployment retired 2026-11-13). Removes `packages/fr-vk/` (16 modules), ~78 test and fixture files (117 `.test_durations` entries), the `super-fr-dispatch` VK wording and the `fr-runner` skill's VK operations.
Note: Touches packaging, install.sh, tests and skill mirrors, so it conflicts with most batches: run it as its own wave. It also shrinks the suite, which helps #1428.

## Why these belong together
Decision recorded in #1459: the only VK deployment was retired 2026-11-13. Removes packages/fr-vk, its tests and fixtures, the VK dispatch wording and the fr-runner skill's VK operations. Runs alone first: it touches packaging, install.sh, tests and mirrors, which most later batches also touch, and it shrinks the suite (#1428).

## Delivery rules
- Work on branch `feat/batch-retire-vk`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1459
- Start the run (`fr run start` with `--issue 1459`) so it records its issue.
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

Never add the `approved-fr` label: it is the operator's approval to merge, and fr voids it on your next push.

Issue #1459 body (scope survey, done-when) is on the issue; its Done-when: no `vibe.?kanban|fr_vk|\bvk\b` outside implemented/ except intentional historical mentions; fr-dispatch, fr-cncd, fr-herdr tests pass unchanged; plugin installs without fr-vk; a version bump and changelog note.

<!-- fr:journal kind=decision scope=spec id=old-scaffolds-break-with-remedy created=2026-11-14T21:22:30+00:00 decided_by=operator -->
### old-scaffolds-break-with-remedy · decision · Scaffolded devcontainers naming fr-vk break, with a clear remedy

Q: devcontainers fr already scaffolded install packages/fr-vk from main; after removal their creation fails. A: break + clear remedy (recommended) — remove the package outright, fix this repo's own profiles, and have `fr isolation up`/`rebuild` refuse such a profile naming the segment to delete; the release note says it too. No tombstone stub, no migration repair. Spec R3, R4, R11.

<!-- fr:journal kind=decision scope=spec id=fr-runner-skill-deleted created=2026-11-14T21:22:30+00:00 decided_by=operator -->
### fr-runner-skill-deleted · decision · Delete the fr-runner skill

Q: the fr-runner skill is VK-only. A: delete it (recommended); its runner-agnostic facts (fr undispatch, unit_mismatch, reachability) move into fr-dispatch. Spec R6.

<!-- fr:journal kind=decision scope=spec id=installer-removes-vk-residue created=2026-11-14T21:22:30+00:00 decided_by=operator -->
### installer-removes-vk-residue · decision · install.sh removes the VK residue it wrote

Q: what install does with the existing vibe_kanban MCP entry and vk-bridge wrapper. A: remove what fr wrote (recommended), print a line per removal; `--install-bridge` refuses naming the removal. Spec R5.

<!-- fr:journal kind=decision scope=spec id=bump-major created=2026-11-14T21:22:30+00:00 decided_by=operator -->
### bump-major · decision · The change fragment is a major bump

Q: bump level. A: major (recommended) — a runner, a daemon and an installer flag are removed and old scaffolds break. Spec R11.

<!-- fr:journal kind=decision scope=spec id=verification-candidate-developer created=2026-11-14T21:22:30+00:00 decided_by=operator -->
### verification-candidate-developer · decision · Verified by the candidate walk, gate developer

Q: pre-merge verification. A: `candidate` strategy, gate developer (recommended): the walk installs the branch into a throwaway prefix and runs the smoke, proving the plugin installs without fr-vk; rows are CI-tested. Spec ## Verification.

<!-- fr:journal kind=decision scope=spec id=captured-fixtures-kept created=2026-11-14T21:22:30+00:00 decided_by=operator -->
### captured-fixtures-kept · decision · Captured forge fixtures that quote VibeKanban stay byte-identical

Decided from the code, not asked: tests/fixtures/github_rest/** and tests/scenarios/fixtures/** mention VibeKanban only inside recorded PR bodies/check names; they are API-shape evidence, not VK behaviour, and rewriting a capture is the fixture-composition defect the repo forbids. Spec R2.

<!-- fr:journal kind=finding scope=spec id=s-r1 created=2026-11-14T21:29:37+00:00 state=open review_scope=in -->
### s-r1 · finding [open] (reviewer: in scope) · The spec has no Test Plan or named test cases, although artifacts.test_plan is on

Spec headings ended at `## Verification`, and no test case was named for R4 (up, rebuild, customised postCreate, missing config), R5 (entry present or absent, fr-written or foreign wrapper, VK_BRIDGE_WRAPPER_PATH, --install-bridge, --uninstall) or the R10 allowlist.

<!-- fr:journal kind=finding scope=spec id=s-r2 created=2026-11-14T21:29:37+00:00 state=open review_scope=in -->
### s-r2 · finding [open] (reviewer: in scope) · R4 placement is wrong: rebuild has no config-exists check, and a check placed before save_state brings back gh#578

The up config-exists check (local.py:1231-1242) runs before save_state (:1247-1264). rebuild (:1402-1432) has no such check and calls the shared _devcontainer_up (:1292), which exec's resume (:1380) also calls. Name one placement, keep up recorded, and state the absent-config case and the default-branch remedy.

<!-- fr:journal kind=finding scope=spec id=s-r3 created=2026-11-14T21:29:37+00:00 state=open review_scope=in -->
### s-r3 · finding [open] (reviewer: in scope) · The Background inventory misses shipped places that name fr-vk, VK or fr-runner

.fr/candidate-install:36; HERMES.md:67,97; fr/commands/skills_cmd.py:78; scripts/readme-skill-summaries.yaml:18; fr/real_ghrestclient.py:916; fr/render.py:212,385, parser.py:47,130, workflow/shapes.py:3, isolation/local.py:1606; AGENTS.md's repo-shape bullet and bridge-audit rule.

<!-- fr:journal kind=finding scope=spec id=s-r4 created=2026-11-14T21:29:37+00:00 state=open review_scope=in -->
### s-r4 · finding [open] (reviewer: in scope) · fr-runner has no OpenCode/Hermes mirrors or install wiring; the real surfaces were unnamed

The only file is plugins/super-fr-dispatch/skills/fr-runner/SKILL.md. It is named by skills_cmd.py:78, readme-skill-summaries.yaml:18, README.md:74 and docs/explainers/fr-dispatch.md:2,13. fr-dispatch/SKILL.md:20-23,119 already states undispatch and reachability, so only unit_mismatch moves.

<!-- fr:journal kind=finding scope=spec id=s-r5 created=2026-11-14T21:29:37+00:00 state=open review_scope=in -->
### s-r5 · finding [open] (reviewer: in scope) · The test inventory is inaccurate and a 'test_bridge_*' glob would delete a kept test

44 files (not ~60). test_install_sh.py, test_runner_package_lists.py, test_install_atomic.py and test_install_worktree_settings_hooks.py assert VK pieces without importing fr_vk. test_bridge_prompt.py tests kept fr_dispatch.prompt. conftest.py:62-71 _default_vk_project_id. Unnamed mixed files: test_version_surfaces, test_tripwire_forge_adapter, test_forge_error_kind, test_tick_workitem, test_done_reconcile, test_cutover. The transcript fixture claude-code-background.jsonl is captured data.

<!-- fr:journal kind=finding scope=spec id=s-r6 created=2026-11-14T21:29:37+00:00 state=open review_scope=in -->
### s-r6 · finding [open] (reviewer: in scope) · The R10 tripwire misses roots, and its whole-file allowlist hides residue in local.py and install.sh

Unscanned: .github/workflows/ci.yml:35, .fr/candidate-install:36, pyproject.toml, HERMES.md. Whole-file allowance exempts local.py:2161-2162 and install.sh:1115. No VibeKanban or fr-runner needles, so plugin.json:3,14 and R6 go unguarded.

<!-- fr:journal kind=finding scope=spec id=s-r7 created=2026-11-14T21:29:37+00:00 state=open review_scope=in -->
### s-r7 · finding [open] (reviewer: in scope) · Rows cover no R2, R9 or R11, and stale-vk-profile-refused cites R3 without stating it

docs/acceptance/features/2026-11-14-retire-vibekanban.yaml:15-52. State the R3 claim in the row, and say that R2, R9 and R11 are verified by CI gates.

<!-- fr:journal kind=finding scope=spec id=s-r8 created=2026-11-14T21:29:37+00:00 state=open review_scope=in -->
### s-r8 · finding [open] (reviewer: in scope) · The fragment list misses 2026-09-19-gitlab-contents-ref-and-self-hosted-hosts, which cites test_pr_observe.py

docs/acceptance/features/2026-09-19-gitlab-contents-ref-and-self-hosted-hosts.yaml:45 cites a wholly-VK test that R2 deletes; it needs a drop-level amendment.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-14T21:29:37+00:00 -->
### spec-review-1 · review · independent spec review: 8 findings, all in scope, all fixed in the spec

Raised by the dispatched fr-spec-reviewer: s-r1 to s-r8, all in scope. Every recorded decision was honoured (old-scaffolds-break-with-remedy, fr-runner-skill-deleted, installer-removes-vk-residue, bump-major, verification-candidate-developer, captured-fixtures-kept). It confirmed that no kept code depends on fr_vk at runtime. Suggested lenses: tests and simplicity.

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-14T21:29:37+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · About 44 test files are deleted or trimmed, and the boundary between wholly-VK and mixed tests is easy to get wrong (test_bridge_prompt.py)

<!-- fr:journal kind=lens scope=spec id=lens-simplicity-1 created=2026-11-14T21:29:37+00:00 lens=simplicity step=spec-review -->
### lens-simplicity-1 · lens · The R10 allowlist and the R5 cleanup are the only new code; both should stay minimal and exact

<!-- fr:journal kind=finding scope=spec id=s-r1-resolved created=2026-11-14T21:29:37+00:00 state=fixed resolves=s-r1 -->
### s-r1-resolved · finding [fixed] · resolves s-r1: The spec has no Test Plan or named test cases, although artifacts.test_plan is on

Added a `## Tests` section naming every R4, R5, R6 and R10 case, and stating that R2, R9 and R11 are verified by CI gates. No `## Test Plan` section was added: under fr-goal it holds only post-merge rows that no pre-merge strategy can exercise, and this change has none (candidate walk plus CI cover every row).

<!-- fr:journal kind=finding scope=spec id=s-r2-resolved created=2026-11-14T21:29:37+00:00 state=fixed resolves=s-r2 -->
### s-r2-resolved · finding [fixed] · resolves s-r2: R4 placement is wrong: rebuild has no config-exists check, and a check placed before save_state brings back gh#578

R4 and the Design now place one check in `_devcontainer_up` (local.py:1292), so it covers up (after save_state, recorded per gh#578), rebuild and exec's resume. An absent config falls through, and the remedy names the default branch.

<!-- fr:journal kind=finding scope=spec id=s-r3-resolved created=2026-11-14T21:29:37+00:00 state=fixed resolves=s-r3 -->
### s-r3-resolved · finding [fixed] · resolves s-r3: The Background inventory misses shipped places that name fr-vk, VK or fr-runner

Background, R1, R7 and R8 now name .fr/candidate-install, HERMES.md, skills_cmd.py, readme-skill-summaries.yaml, real_ghrestclient.py, render.py, parser.py, shapes.py, local.py:1606, and AGENTS.md's repo-shape bullet and bridge-audit rule.

<!-- fr:journal kind=finding scope=spec id=s-r4-resolved created=2026-11-14T21:29:37+00:00 state=fixed resolves=s-r4 -->
### s-r4-resolved · finding [fixed] · resolves s-r4: fr-runner has no OpenCode/Hermes mirrors or install wiring; the real surfaces were unnamed

R6 and the Design name the real surfaces (the skill file, the fr skills row, the README summary source plus sync-readme, and the explainer's title, tldr and covers). Mirrors and install wiring are noted as not existing, and only unit_mismatch moves.

<!-- fr:journal kind=finding scope=spec id=s-r5-resolved created=2026-11-14T21:29:37+00:00 state=fixed resolves=s-r5 -->
### s-r5-resolved · finding [fixed] · resolves s-r5: The test inventory is inaccurate and a 'test_bridge_*' glob would delete a kept test

Background now says 44 files, classifies tests by what they exercise (test_bridge_prompt.py kept), names the install tests and test_runner_package_lists.py changes, both conftest fixtures and the mixed files, and adds the transcript fixture to the captured-data set.

<!-- fr:journal kind=finding scope=spec id=s-r6-resolved created=2026-11-14T21:29:37+00:00 state=fixed resolves=s-r6 -->
### s-r6-resolved · finding [fixed] · resolves s-r6: The R10 tripwire misses roots, and its whole-file allowlist hides residue in local.py and install.sh

R10 now scans .github/, .fr/, the root pyproject.toml and HERMES.md. It adds VibeKanban and fr-runner needles, allows by (file, line regex) pairs, and fails an allowlist entry that matches nothing. install.sh:1115 is named under R5.

<!-- fr:journal kind=finding scope=spec id=s-r7-resolved created=2026-11-14T21:29:37+00:00 state=fixed resolves=s-r7 -->
### s-r7-resolved · finding [fixed] · resolves s-r7: Rows cover no R2, R9 or R11, and stale-vk-profile-refused cites R3 without stating it

stale-vk-profile-refused is reworded to state the R3 claim. The spec's Tests section says that R2, R9 and R11 are verified by the suite, fr acceptance check and the change-fragment job.

<!-- fr:journal kind=finding scope=spec id=s-r8-resolved created=2026-11-14T21:29:37+00:00 state=fixed resolves=s-r8 -->
### s-r8-resolved · finding [fixed] · resolves s-r8: The fragment list misses 2026-09-19-gitlab-contents-ref-and-self-hosted-hosts, which cites test_pr_observe.py

Added 2026-09-19-gitlab-contents-ref-and-self-hosted-hosts to the Background's fragment list; its row gets a drop-level amendment under R9.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-14T21:29:39+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  dispatch-docs-name-no-vk: none
  installer-removes-vk-residue: none
  stale-vk-profile-refused: none
  vk-runner-removed: none
row_kinds:
  dispatch-docs-name-no-vk: none
  installer-removes-vk-residue: none
  stale-vk-profile-refused: none
  vk-runner-removed: none
run_gate: developer
run_kind: candidate
```
