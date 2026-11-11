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

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-11-11T14:42:29+00:00 phase=1 -->
### p1-review-1 · review · Phase 1 review: fr docs check/status (phase 1)

A separate reviewer read the phase 1 diff against R1-R8. Globs, front matter handling, read-only git, rename parsing, exit codes and the no-write property were verified. Three findings, all in scope, all fixed with tests.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-11T14:42:29+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · R6 not met with unpushed commits on the default branch (phase 1)

changed_paths only went structure-only when merge-base == HEAD, so local main ahead of origin/main ran the stale check.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-11T14:42:29+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Rename test proved only the old side (phase 1)

test_a_rename_counts_both_sides asserted the old path only; a rename into a covered path and a deleted covered file were untested.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-11T14:42:29+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · A config selecting no page passed silently (phase 1)

A pages glob matching no tracked file printed 0 page(s) current and exited 0.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-11T14:42:29+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: R6 not met with unpushed commits on the default branch (phase 1)

With no --base, HEAD on the default branch's local branch is structure only (load.on_default_branch); test_unpushed_commits_on_the_default_branch_are_structure_only. Spec R6 says pushed or not.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-11T14:42:29+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Rename test proved only the old side (phase 1)

Added test_a_rename_into_a_covered_path_counts_the_new_side and test_a_deleted_covered_file_makes_its_page_stale.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-11T14:42:29+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: A config selecting no page passed silently (phase 1)

fr docs check exits 2 when the config selects no page; test_a_config_that_selects_no_page_exits_2. Spec R1 states it.

<!-- fr:journal kind=decision scope=plan id=p2-docs-gate-module created=2026-11-11T14:59:39+00:00 phase=2 -->
### p2-docs-gate-module · decision · fr.docs.gate.evaluate is the one evaluation shared by the command and the deliver witness (phase 2)

`fr docs check` and `deliver`'s `docs` witness differ only in how they pick the base, so the
selection (tracked files, pages, the no-page refusal, changed paths, check) moved into
`fr/docs/gate.py`'s `evaluate(root, config, base)`, base None meaning structure only.
`load.merge_base_of` was split out of `changed_paths` so the witness can name its merge base.
The witness stores `<merge-base>:<sha256>` of `status_json` over the current pages, `none`
with no `.fr/docs.yaml`.

<!-- fr:journal kind=decision scope=plan id=p2-witness-base-helper created=2026-11-11T14:59:39+00:00 phase=2 -->
### p2-witness-base-helper · decision · _witness_base shares the base lookup and its refusal between proportionality and docs (phase 2)

P2.T1.S3: `_witness_base(key, repo_root, name, *, announce)` wraps `_proportionality_base`
with the no-base refusal and the fallback notice, worded with the witness's name, so
proportionality's output is unchanged. `docs` announces a fallback base only when the step
does not also declare `proportionality`, so the notice prints once.

<!-- fr:journal kind=decision scope=plan id=p2-docs-evidence-position created=2026-11-11T14:59:39+00:00 phase=2 -->
### p2-docs-evidence-position · decision · docs sits after proportionality in deliver.evidence (phase 2)

Both shapes now read `[tests, proportionality, docs, visual, walk]`; the tripwire's
`evidence[-2] == "visual"` pin and the drift test's replacement string were updated.
Drift compares ids only, so in-flight runs are unaffected.

<!-- fr:journal kind=discovery scope=plan id=p2-fr-debugging-line-cap created=2026-11-11T14:59:39+00:00 phase=2 -->
### p2-fr-debugging-line-cap · discovery · fr-debugging's SKILL.md sits at the 120-line cap (phase 2)

test_skill_validation caps a SKILL.md at 120 lines and fr-debugging was at 118; the R10
sentence was folded into existing lines to land at exactly 120. The next addition there
has to shorten something.

<!-- fr:journal kind=discovery scope=plan id=p2-every-flow-row-r24 created=2026-11-11T14:59:39+00:00 phase=2 -->
### p2-every-flow-row-r24 · discovery · docs-currency-every-flow moved to ci while its R24 origin is still owed (phase 2)

The row also cites R24 (the explainers-currency rule rewrite and tripwires), which is a
later phase's. Its note says so; that phase should add its refs to the row.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-11T14:59:39+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

prose and wiring only: one new rule file, one sentence per skill, one list entry in install.sh and sync-hermes.py; nothing duplicated to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-11-11T14:59:39+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

one CI job copied from change-fragment's pins, which a test now pins equal; nothing to clean
