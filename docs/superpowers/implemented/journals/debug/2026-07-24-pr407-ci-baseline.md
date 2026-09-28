# Journal: 2026-07-24-pr407-ci-baseline

<!-- fr:journal kind=repro scope=debug id=pr407-ci-repro created=2026-07-24T21:46:43 -->
### pr407-ci-repro · repro · PR #407 test job failed on merged-but-unarchived tripwire

GitHub Actions run 30124924483 failed only tests/unit/test_tripwire_unarchived_plans.py::test_no_merged_but_unarchived_plans: origin/main had merged 2026-07-24-vk-mcp-timeout-permit-leak complete but still under plans/. CI totals were 1759 passed, 81 skipped, 1 failed; all other jobs passed.

<!-- fr:journal kind=root-cause scope=debug id=pr407-ci-root-cause created=2026-07-24T21:46:43 -->
### pr407-ci-root-cause · root-cause · Failure came from stale branch base, not Hermes changes

The PR run used the pre-archive origin/main. Current origin/main commit 9d74a5c archives the VK plan, removing the exact tripwire offender. Current main also tags 3.15.2, colliding with the Hermes branch release number; rebase plus bump to 3.15.3 is required.

<!-- fr:journal kind=finding scope=debug id=pr407-ci-3-17-archive created=2026-07-25T04:25:54 state=fixed -->
### pr407-ci-3-17-archive · finding [fixed] · Current-main archive tripwire cleared after v3.17.0 merge

While refreshing PR #407 onto origin/main v3.17.0, the merged-but-unarchived backstop identified the newly merged 2026-07-24-acceptance-dual-reports plan. Ran the repository-prescribed fr archive operation in a separate CI-unblock change, moving its plan, spec, and journal to implemented/. The Hermes repair remains independently identifiable and ships as 3.17.1.
