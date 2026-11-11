<!-- fr:journal-schema=3 -->
# Journal: 2026-11-11-docs-currency

<!-- fr:journal kind=decision scope=plan id=p1-no-skills-list-edit created=2026-11-11T14:40:12+00:00 phase=1 -->
### p1-no-skills-list-edit · decision · fr skills lists per-skill commands, not groups (phase 1)

The plan said to add an `fr docs` line where `fr skills` lists command groups if hand-kept. skills_cmd.py lists one row per skill with its commands, not command groups (debt, gate and release are absent too), so no line was added.

<!-- fr:journal kind=discovery scope=plan id=p1-acceptance-level-int created=2026-11-11T14:40:12+00:00 phase=1 -->
### p1-acceptance-level-int · discovery · Scenario test refs go under the int level (phase 1)

`fr acceptance set-status --level` accepts unit|api|int|ui only; the test_scenarios.py refs were recorded as `int`.

<!-- fr:journal kind=discovery scope=plan id=p1-suite-env-failures created=2026-11-11T14:40:12+00:00 phase=1 -->
### p1-suite-env-failures · discovery · Full suite: 7 environment failures, none in fr docs (phase 1)

14411 passed, 132 skipped, 7 failed in 2h01. The failures are test_artifact_atomic read-only-file, test_bindings_catalogue and test_bindings_probe write-failure tests and test_validate_artifacts unreadable-artifact (all rely on a permission-denied write, which root defeats), plus three test_isolation_container_verbs tests that expect devcontainer mode but run in host-worktree mode. None touches fr.docs. The baseline run was not completed to compare. The install.sh integration tests run a real `npm install -g @devcontainers/cli` over the proxy (their PATH hides the installed devcontainer), which makes the tail of the suite take about two hours.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-11T14:40:12+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

check.py was written once, pure and already split; nothing to clean beyond folding duplicate uncovered findings, done inline

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-11T14:40:12+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

load/render/command were written as separate small modules with no duplication; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-11T14:40:12+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

scenarios share one _docs_fixture.sh from the start; nothing to clean
