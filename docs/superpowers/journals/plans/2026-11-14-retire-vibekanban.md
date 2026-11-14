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
