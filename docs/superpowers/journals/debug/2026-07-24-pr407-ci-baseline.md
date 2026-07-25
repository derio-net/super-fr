# Journal: 2026-07-24-pr407-ci-baseline

<!-- fr:journal kind=repro scope=debug id=pr407-ci-repro created=2026-07-24T21:46:43 -->
### pr407-ci-repro · repro · PR #407 test job failed on merged-but-unarchived tripwire

GitHub Actions run 30124924483 failed only tests/unit/test_tripwire_unarchived_plans.py::test_no_merged_but_unarchived_plans: origin/main had merged 2026-07-24-vk-mcp-timeout-permit-leak complete but still under plans/. CI totals were 1759 passed, 81 skipped, 1 failed; all other jobs passed.

<!-- fr:journal kind=root-cause scope=debug id=pr407-ci-root-cause created=2026-07-24T21:46:43 -->
### pr407-ci-root-cause · root-cause · Failure came from stale branch base, not Hermes changes

The PR run used the pre-archive origin/main. Current origin/main commit 9d74a5c archives the VK plan, removing the exact tripwire offender. Current main also tags 3.15.2, colliding with the Hermes branch release number; rebase plus bump to 3.15.3 is required.
