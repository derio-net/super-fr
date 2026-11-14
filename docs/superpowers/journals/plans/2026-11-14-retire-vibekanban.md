<!-- fr:journal-schema=4 -->
# Journal: 2026-11-14-retire-vibekanban

<!-- fr:journal kind=decision scope=plan id=p1-mixed-tests-onto-fakerunner created=2026-11-14T22:58:38+00:00 phase=1 -->
### p1-mixed-tests-onto-fakerunner · decision · Mixed tests where VkRunner was incidental now run on FakeRunner, not deleted (phase 1)

Classified by what each test exercises. test_bridge_metrics (MetricsPusher wire format and
tick's metric emission), test_bridge_e2e, test_bridge_no_issue_create, and two cases of
test_bridge_resilience (I7 renderer, I8 apply/tick race) assert kept fr_dispatch/fr
behaviour; they now use tests.unit.test_tick_workitem.FakeRunner and a neutral
MetricsPusher. test_bridge_lifecycle keeps the three invoke_lifecycle_hook cases
(called directly). Wholly-VK files (24) were deleted, as were FakeMcpClient and
vk_metrics in fakes.py. Runner-registry tests that used `vk` as the from_env-less runner
now use `cncd`.

<!-- fr:journal kind=decision scope=plan id=p1-acceptance-row-calls created=2026-11-14T22:58:38+00:00 phase=1 -->
### p1-acceptance-row-calls · decision · Eight VK-only rows retired; seven mixed rows drop their VK refs; one reworded (phase 1)

Retired: bridge-checkout-self-heal, bridge-pr-autoclose, bridge-done-issue-close,
vk-dispatch-unchanged-after-cutover, multibackend-vk-dispatch, vk-bridge-init-timeout-graceful,
vk-mcp-timeout-survives-slow-ops, vk-mcp-post-timeout-correctness. drop-level:
vk-legacy-fallbacks-removed (kept: the isolation spellings, test_isolation.py),
dispatch-unit-declared-by-shape, shape-resolution-fails-loud, runner-capability-refusal
(test_bridge_shape_binding drove the deleted daemon), gitlab-selfhosted-host-targeting
(test_pr_observe), forge-calls-through-adapter (the bridge rate-limit case),
installed-fr-carries-every-runner (test_install_bridge.py, plus a reword dropping vk and
--install-bridge from its statement). daemon-refuses-stale-artifacts and
archived-plans-survive-a-major-bump cite test_vk_bridge_discover.py, which tests the kept
fr_dispatch.discover_plans: unchanged.

<!-- fr:journal kind=finding scope=plan id=p1-staleness-guard-ignored-retired-rows created=2026-11-14T22:58:38+00:00 phase=1 state=fixed review_scope=in -->
### p1-staleness-guard-ignored-retired-rows · finding [fixed] (reviewer: in scope) · Retiring every row of a spec failed fr acceptance check's staleness guard (phase 1)

R9's retirements left docs/superpowers/implemented/specs/2026-07-24-vk-mcp-timeout-permit-leak-design.md
(a Test Plan) cited by no live row, and the guard counted only live rows, so the gate
failed with no honest fix. Fixed in fr.acceptance.check.check (new keyword `retired`,
fed from fr.acceptance.fold.effective(root).retired by `fr acceptance check`): a retired
row's origin still counts as a citation. Test:
tests/unit/test_acceptance_effective_readers.py::test_the_staleness_guard_counts_a_retired_rows_origin.
This is a gate change outside the plan's listed steps; worth the review's attention.

<!-- fr:journal kind=discovery scope=plan id=p1-docs-check-pages-for-phase-3 created=2026-11-14T22:58:38+00:00 phase=1 -->
### p1-docs-check-pages-for-phase-3 · discovery · fr docs check now flags pages phase 3 must edit or restamp (phase 1)

`fr docs check --base origin/main` reports a dead covers glob (fr-dispatch.md:
packages/fr-vk/src/**) and stale pages: docs/explainers/fr-dispatch.md,
fr-acceptance.md (the staleness-guard fix in check.py / acceptance_cmd.py),
fr-isolation.md (scaffold.py), docs/reference/{acceptance-matrix,cli,components,hermes}.md.
Phase 1 left docs wording to phase 3 as instructed. AGENTS.md's repo-shape bullet and
bridge-audit rule still name fr-vk (only the dev-commands line changed here).

<!-- fr:journal kind=discovery scope=plan id=p1-install-tests-left-for-phase-2 created=2026-11-14T22:58:38+00:00 phase=1 -->
### p1-install-tests-left-for-phase-2 · discovery · test_install_bridge is xfail(strict) until phase 2; VK MCP install assertions untouched (phase 1)

tests/integration/test_install_bridge.py now fails (install.sh's --install-bridge imports
fr_vk.bridge), so it is xfail(strict=True, "install.sh VK pieces removed in phase 2").
test_runner_package_lists.py's --install-bridge case now asserts only a non-zero exit and
no packages/fr-vk in its output. The vibe_kanban MCP assertions in test_install_sh.py,
test_install_atomic.py and test_install_worktree_settings_hooks.py are untouched and pass.
Some tests still use "vk" as an arbitrary queue_runner label (test_render_deps.py,
test_reachability.py, test_placement_*); they pass and exercise no VK code.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-14T22:58:38+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

A deletion plus one-token edits to manifests and lists; nothing new was written that could be cleaned

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-14T22:58:38+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

Deletions and trims only; the one rewrite (VkRunner -> the framework's FakeRunner) reuses existing helpers, and P1.T4.S2's refactor pass re-read the whole test diff

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-14T23:09:01+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · The staleness-guard change (a retired row counts as a citation) is not stated in spec R9 or in the acceptance-matrix rule (phase 1)

Commit af8c79cc0 changed what the gate means. The spec is the contract, so R9 and .claude/rules/acceptance-matrix.md:22-23 must say it.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-14T23:09:01+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · backfill_cmd computes its own uncited-spec set, which ignores retired rows and so disagrees with check.py (phase 1)

acceptance_cmd.py:1480-1499 looped over matrix.rows only. After this PR it would list the vk-mcp spec as uncited and invite rows for removed behaviour. Fix: one shared helper.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-14T23:09:01+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · vk-legacy-fallbacks-removed still claims VK_BRIDGE_* and VK_DERIO_OPS_PROJECT_ID and cites the deleted test_bridge_cli.py; daemon-refuses-stale-artifacts' note names bridge_cli.py (phase 1)

Both need amendments: a reword plus a notes-only set-status for the first row, and a notes-only set-status for the second.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-14T23:09:01+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · vk-runner-removed has no level refs, although its two phase 1 tests exist (phase 1)

tests/unit/test_vk_compat_removed.py::test_no_vk_runner_entry_point and ::test_apply_to_vk_is_unknown_runner.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-14T23:09:01+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · AGENTS.md:458 points at the deleted _fresh_vk_repo_cache fixture (phase 1)

Point it at a surviving autouse fixture.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-14T23:09:01+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · tests/unit/fakes.py:518 forge_of has no caller left (phase 1)

Its only users were the deleted test_bridge_pr_state.py and test_done_reconcile.py.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-11-14T23:09:01+00:00 phase=2 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · test_install_bridge_names_no_fr_vk passes on an import crash; phase 2 must assert the --install-bridge refusal text (phase 2)

tests/integration/test_runner_package_lists.py:92-104 asserts only a non-zero exit and that packages/fr-vk is not named. Today install.sh --install-bridge exits non-zero because importing fr_vk.bridge fails. Phase 2 (R5) makes it refuse by name, and must tighten this test to assert that refusal.

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-11-14T23:09:01+00:00 phase=1 state=open review_scope=out -->
### p1-r8 · finding [open] (reviewer: out of scope) · backfill_cmd recorded a logical origin's slug instead of its spec paths, so it listed logically cited specs as uncited (phase 1)

Predates this change: acceptance_cmd.py:1480-1490 passed spec:<slug>#R<n> through split_ref. The p1-r2 helper fixes it too.

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-11-14T23:09:01+00:00 phase=1 -->
### review-phase-1 · review · independent phase 1 review: 8 findings, 7 in scope, 1 out of scope (phase 1)

The reviewer confirmed that the package deletion (R1, R3) is complete. Tests were classified by what they import, and no test of kept code was deleted. The captured fixtures are byte-identical, every acceptance change is an amendment, and the fragment is major. It judged commit af8c79cc0 correct and minimal. p1-r1 to p1-r6 and p1-r8 are fixed on this branch. p1-r7 is carried to phase 2, which owns --install-bridge (R5). Suggested lens: docs-accuracy.

<!-- fr:journal kind=lens scope=plan id=lens-docs-accuracy-1 created=2026-11-14T23:09:01+00:00 phase=1 lens=docs-accuracy step=review-phase -->
### lens-docs-accuracy-1 · lens · the change rewrites dispatch, isolation and acceptance pages that phase 1 left stale (fr docs check flags seven) (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-14T23:09:01+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: The staleness-guard change (a retired row counts as a citation) is not stated in spec R9 or in the acceptance-matrix rule (phase 1)

Spec R9 and .claude/rules/acceptance-matrix.md now say that a retired row still cites its origin, for both the staleness guard and backfill. The OpenCode mirror is regenerated. Commit 08b125434.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-14T23:09:01+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: backfill_cmd computes its own uncited-spec set, which ignores retired rows and so disagrees with check.py (phase 1)

check.py has cited_spec_paths(rows, own), which check() and backfill_cmd both call with live plus retired rows. test_the_staleness_guard_counts_a_retired_rows_origin now also asserts that backfill does not list the spec. Both tests were red on the old code. Commit 81410d6fb.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-14T23:09:01+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: vk-legacy-fallbacks-removed still claims VK_BRIDGE_* and VK_DERIO_OPS_PROJECT_ID and cites the deleted test_bridge_cli.py; daemon-refuses-stale-artifacts' note names bridge_cli.py (phase 1)

Amendments in this feature's fragment. vk-legacy-fallbacks-removed is reworded to the isolation spellings, and its note no longer cites test_bridge_cli.py. daemon-refuses-stale-artifacts' note no longer names bridge_cli.py.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-14T23:09:01+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: vk-runner-removed has no level refs, although its two phase 1 tests exist (phase 1)

Both tests from test_vk_compat_removed.py were added as unit levels by amendment. The status stays not-implemented until the R10 tripwire lands in phase 3.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-14T23:09:01+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: AGENTS.md:458 points at the deleted _fresh_vk_repo_cache fixture (phase 1)

AGENTS.md now points at _fresh_forge_policy_cache. Commit 08b125434.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-14T23:09:01+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: tests/unit/fakes.py:518 forge_of has no caller left (phase 1)

forge_of deleted from tests/unit/fakes.py. Commit 08b125434.

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-11-14T23:09:01+00:00 phase=1 state=fixed resolves=p1-r8 -->
### p1-r8-resolved · finding [fixed] · resolves p1-r8: backfill_cmd recorded a logical origin's slug instead of its spec paths, so it listed logically cited specs as uncited (phase 1)

Fixed by the p1-r2 helper: a logical origin now adds its candidate spec paths. test_backfill_counts_a_logical_citation pins this, live and archived.
