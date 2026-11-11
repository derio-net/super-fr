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

<!-- fr:journal kind=review scope=plan id=p2-review-1 created=2026-11-11T15:12:11+00:00 phase=2 -->
### p2-review-1 · review · Phase 2 review: docs witness at deliver, shipped rule, skills, CI job (phase 2)

A separate reviewer read the phase 2 diff against R9-R11. No bypass of the deliver gate was found: a caller-passed docs witness is refused, every git, base or config failure exits 2, `none` is stored only without .fr/docs.yaml, and fr docs check and the gate share one evaluation. No artifact shape moved. Two findings: one in scope (fixed), one out of scope.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-11T15:12:11+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · docs-currency-every-flow at ci while its R24 origin is unbuilt (phase 2)

The row cites R24, which phase 3 implements, but phase 3 did not list the row, so no phase would attach R24 evidence to it.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-11T15:12:11+00:00 phase=2 state=open review_scope=out -->
### p2-r2 · finding [open] (reviewer: out of scope) · install.sh delivers no rules to OpenCode consumers (phase 2)

scripts/install.sh installs skills, commands, agents and the plugin for OpenCode, and no instructions. A shipped rule therefore loads under OpenCode only in this repo's own checkout. True of every shipped rule, fr-isolation-required included.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-11T15:12:11+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: docs-currency-every-flow at ci while its R24 origin is unbuilt (phase 2)

Phase 3 now lists docs-currency-every-flow in its acceptance, so the phase that builds R24 adds its evidence to the row.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-11T15:12:11+00:00 phase=2 state=open resolves=p2-r2 out_of_scope=true -->
### p2-r2-resolved · finding [out-of-scope] · resolves p2-r2: install.sh delivers no rules to OpenCode consumers (phase 2)

Not caused by this change: install.sh has never delivered an instruction file to OpenCode, for any shipped rule. The new rule is delivered exactly as the existing ones are.

<!-- fr:journal kind=discovery scope=plan id=p3-blog-craft-visibility created=2026-11-11T15:25:26+00:00 phase=3 -->
### p3-blog-craft-visibility · discovery · Pinned renderer checkout assumes blog-craft is readable by the workflow token (phase 3)

pages.yml and the site-build job check derio-net/blog-craft out with the default token, as the spec says. That works only if the repository is readable by it (public, or internal with access granted). It could not be checked from this session (no access to the repo via gh). The first CI run of site-build is the evidence; if it fails on checkout the fix is a token input, not a script change.

<!-- fr:journal kind=decision scope=plan id=p3-drop-leading-h1 created=2026-11-11T15:25:26+00:00 phase=3 -->
### p3-drop-leading-h1 · decision · The build drops a body's leading H1 (phase 3)

Guides in docs/*.md open with an H1 that repeats the title front matter, and the renderer prints the title itself, so the page showed it twice. build-site.py removes a leading H1 from the body at build time (drop_leading_h1, tested); the source files keep it so they read well on GitHub.

<!-- fr:journal kind=decision scope=plan id=p3-index-list-links created=2026-11-11T15:25:26+00:00 phase=3 -->
### p3-index-list-links · decision · The index list is filled with source-relative links before the rewrite (phase 3)

fill_pages emits links to each page's source path relative to the index, and the single link rewrite then turns them into routes, so the list and hand-written links share one rule and one failure mode.

<!-- fr:journal kind=discovery scope=plan id=p3-fr-isolation-drift created=2026-11-11T15:25:26+00:00 phase=3 -->
### p3-fr-isolation-drift · discovery · fr-isolation page corrected against the rule (phase 3)

The hand-authored page described a three-step staircase with mode exactly worktree. The rule now has worktree and external modes (container evidence), the HEAD-drift check and a host-worktree mode; fr-isolation.md states those. Page claims otherwise kept.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-11T15:25:26+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

Content-only task (page sources and front matter); no code to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-11-11T15:25:26+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

Workflow YAML and its pinning test were written once to the target shape; nothing to clean.

<!-- fr:journal kind=review scope=plan id=p3-review-1 created=2026-11-11T15:29:31+00:00 phase=3 -->
### p3-review-1 · review · Phase 3 review: site build from Markdown sources (phase 3)

A separate reviewer read the phase 3 diff against R12-R17, R23, R24 and built the site (10 pages). Routes, link rewriting, the page list, failure behaviour, the workflows and the fidelity of the two rewritten pages against the old HTML were verified. Seven findings: five fixed, one refuted by CI, one out of scope and fixed anyway.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-11T15:29:31+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · blog-craft checkout with the default token unverified (phase 3)

pages.yml and the site-build job check out derio-net/blog-craft with the default token; if it were not readable every deploy and every PR's site-build would fail.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-11T15:29:31+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · index.md says the diagram marks the human steps (phase 3)

The flowchart carries no such marking; the old page's colouring was lost in the conversion.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-11T15:29:31+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · site-builds-from-sources cites no ref that builds the real site (phase 3)

The unit tests cover pure functions; the CI job that builds every page was not cited.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-11-11T15:29:31+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · herdr guide covers too little (phase 3)

It documents fr triage batch replace/drive but covered only packages/fr-herdr/src/**.

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-11-11T15:29:31+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · rewrite_markdown ignores three link shapes (phase 3)

Reference-style definitions, images and raw HTML links were neither rewritten nor checked; indented code blocks are not recognised.

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-11-11T15:29:31+00:00 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · Garbled trigger sentence in explainers-currency.md (phase 3)

'Triggers are the shipped rule docs-currency; ...'

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-11-11T15:29:31+00:00 phase=3 state=open review_scope=out -->
### p3-r7 · finding [open] (reviewer: out of scope) · index.md says every run is in a sealed container (phase 3)

Untrue in host-worktree and external modes; the old page said the same.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-11T15:29:31+00:00 phase=3 state=refuted resolves=p3-r1 -->
### p3-r1-resolved · finding [refuted] · resolves p3-r1: blog-craft checkout with the default token unverified (phase 3)

The site-build job checked out blog-craft at the pinned ref with the default token and passed on f65d6ed6 (check runs site-build, docs-check and ci-ok: success), so the repo is readable by the workflow token.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-11T15:29:31+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: index.md says the diagram marks the human steps (phase 3)

The sentence now says the diagram shows the order and the list says which steps are the reader's.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-11T15:29:31+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: site-builds-from-sources cites no ref that builds the real site (phase 3)

The row cites .github/workflows/ci.yml (job site-build) at the int level and its note says the CI job is the proof of the real build.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-11-11T15:29:31+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: herdr guide covers too little (phase 3)

covers now includes packages/fr/src/fr/triage/batch*.py and commands/triage_batch_cmd.py.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-11-11T15:29:31+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: rewrite_markdown ignores three link shapes (phase 3)

A relative reference definition, image or raw HTML href/src is refused with a BuildError naming the fix; the docstring states the indented-code limit. Tests: test_a_relative_link_in_a_shape_the_build_does_not_rewrite_is_refused, test_absolute_links_in_those_shapes_and_code_samples_pass.

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-11-11T15:29:31+00:00 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: Garbled trigger sentence in explainers-currency.md (phase 3)

Reworded; OpenCode mirror regenerated.

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-11-11T15:29:31+00:00 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: index.md says every run is in a sealed container (phase 3)

Out of scope by origin, but the page is rewritten here, so it now says the container is the default and names the two docker-less modes, linking fr-isolation.

<!-- fr:journal kind=decision scope=plan id=p4-one-page-per-flow created=2026-11-11T15:44:10+00:00 phase=4 -->
### p4-one-page-per-flow · decision · Skills are grouped into nine pages by flow, not one page per skill (phase 4)

fr-brainstorming, fr-plan and fr-execute share a page (one flow), as do fr-triage with fr-origins and fr-dispatch with fr-runner; each page's covers names every skill it describes, so must_cover is satisfied for all fifteen skills.

<!-- fr:journal kind=finding scope=plan id=p4-runner-env-var created=2026-11-11T15:44:10+00:00 phase=4 state=fixed review_scope=in -->
### p4-runner-env-var · finding [fixed] (reviewer: in scope) · fr-runner SKILL.md named a recovery env var the code does not read (phase 4)

The skill said VK_BRIDGE_RECOVER_ORPHAN_CARDS; fr_vk.workspaces reads FR_BRIDGE_RECOVER_ORPHAN_CARDS. Found while checking the dispatch page's claims against the code; the skill is corrected and the page uses the code's spelling.

<!-- fr:journal kind=discovery scope=plan id=p4-docs-check-reads-committed-head created=2026-11-11T15:44:10+00:00 phase=4 -->
### p4-docs-check-reads-committed-head · discovery · fr docs check judges committed HEAD, so new pages count only once committed (phase 4)

Staged or untracked pages do not satisfy a stale or uncovered finding; commit the pages, then re-run the check.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-11-11T15:44:10+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

Content task: the read-back against sources (S3) was the cleanup; no code to restructure beyond the one new test file, written once.

<!-- fr:journal kind=review scope=plan id=p4-review-1 created=2026-11-11T15:48:45+00:00 phase=4 -->
### p4-review-1 · review · Phase 4 review: a page per skill (phase 4)

Two separate reviewers fact-checked the ten new pages claim by claim against the skills, the code and the CLI's --help, five pages each, plus must_cover, its test, the matrix row and the fr-runner env var fix. No false command, flag, exit code or status was found. Twelve findings, all in scope, all fixed: one wrong path, two examples that could not be run as written, and wording and newcomer gaps.

<!-- fr:journal kind=finding scope=plan id=p4a-r1 created=2026-11-11T15:48:45+00:00 phase=4 state=open review_scope=in -->
### p4a-r1 · finding [open] (reviewer: in scope) · fr plan create example shows no phases file (phase 4)

fr-brainstorming-and-plan.md passed --phases-file with no content shown.

<!-- fr:journal kind=finding scope=plan id=p4a-r2 created=2026-11-11T15:48:45+00:00 phase=4 state=open review_scope=in -->
### p4a-r2 · finding [open] (reviewer: in scope) · Debug journal path carries a date the code does not add (phase 4)

fr-debugging.md said debug/<date>-<slug>.md; the code writes debug/<slug>.md.

<!-- fr:journal kind=finding scope=plan id=p4a-r3 created=2026-11-11T15:48:45+00:00 phase=4 state=open review_scope=in -->
### p4a-r3 · finding [open] (reviewer: in scope) · fr journal add shown without its required flags (phase 4)

--slug and --title were omitted.

<!-- fr:journal kind=finding scope=plan id=p4a-r4 created=2026-11-11T15:48:45+00:00 phase=4 state=open review_scope=in -->
### p4a-r4 · finding [open] (reviewer: in scope) · fr-triage example leaves the file location and terms undefined (phase 4)

Where judgements.yaml lives, severity, cx, wave, merge train and intent anchor.

<!-- fr:journal kind=finding scope=plan id=p4a-r5 created=2026-11-11T15:48:45+00:00 phase=4 state=open review_scope=in -->
### p4a-r5 · finding [open] (reviewer: in scope) · Each requirement gets a row overstates (phase 4)

The skill says one row per requirement or closely related group.

<!-- fr:journal kind=finding scope=plan id=p4a-r6 created=2026-11-11T15:48:45+00:00 phase=4 state=open review_scope=in -->
### p4a-r6 · finding [open] (reviewer: in scope) · fr plan rework precondition omitted (phase 4)

The parent must be complete and archived.

<!-- fr:journal kind=finding scope=plan id=p4a-r7 created=2026-11-11T15:48:45+00:00 phase=4 state=open review_scope=in -->
### p4a-r7 · finding [open] (reviewer: in scope) · docs-currency guide has no adoption path (phase 4)

No step-by-step sequence, and no statement that only tracked files are read.

<!-- fr:journal kind=finding scope=plan id=p4a-r8 created=2026-11-11T15:48:45+00:00 phase=4 state=open review_scope=in -->
### p4a-r8 · finding [open] (reviewer: in scope) · Pin the checkout's full history (phase 4)

Should say fetch (fetch-depth: 0).

<!-- fr:journal kind=finding scope=plan id=p4a-r9 created=2026-11-11T15:48:45+00:00 phase=4 state=open review_scope=in -->
### p4a-r9 · finding [open] (reviewer: in scope) · Structure-only stated unconditionally (phase 4)

It holds with no --base on the default branch, or when HEAD is the merge base.

<!-- fr:journal kind=finding scope=plan id=p4a-r10 created=2026-11-11T15:48:45+00:00 phase=4 state=open review_scope=in -->
### p4a-r10 · finding [open] (reviewer: in scope) · Config sample omits docs/reference/*.md (phase 4)

The repo's own config lists it and the page describes that route.

<!-- fr:journal kind=finding scope=plan id=p4b-r1 created=2026-11-11T15:48:45+00:00 phase=4 state=open review_scope=in -->
### p4b-r1 · finding [open] (reviewer: in scope) · fr-audit says report writes only under the cache (phase 4)

report -o writes where it is pointed.

<!-- fr:journal kind=finding scope=plan id=p4b-r2 created=2026-11-11T15:48:45+00:00 phase=4 state=open review_scope=in -->
### p4b-r2 · finding [open] (reviewer: in scope) · fr-dispatch example hits the reachability refusal (phase 4)

fr apply --to vk --yes was shown before the precondition that plan and spec are merged.

<!-- fr:journal kind=finding scope=plan id=p4a-r1-resolved created=2026-11-11T15:48:45+00:00 phase=4 state=fixed resolves=p4a-r1 -->
### p4a-r1-resolved · finding [fixed] · resolves p4a-r1: fr plan create example shows no phases file (phase 4)

The page shows a one-phase phases.yaml; fr plan create and self-review were run on exactly that file in a scratch repo and passed.

<!-- fr:journal kind=finding scope=plan id=p4a-r2-resolved created=2026-11-11T15:48:45+00:00 phase=4 state=fixed resolves=p4a-r2 -->
### p4a-r2-resolved · finding [fixed] · resolves p4a-r2: Debug journal path carries a date the code does not add (phase 4)

Path is debug/<slug>.md.

<!-- fr:journal kind=finding scope=plan id=p4a-r3-resolved created=2026-11-11T15:48:45+00:00 phase=4 state=fixed resolves=p4a-r3 -->
### p4a-r3-resolved · finding [fixed] · resolves p4a-r3: fr journal add shown without its required flags (phase 4)

The command carries --slug, --title and --body.

<!-- fr:journal kind=finding scope=plan id=p4a-r4-resolved created=2026-11-11T15:48:45+00:00 phase=4 state=fixed resolves=p4a-r4 -->
### p4a-r4-resolved · finding [fixed] · resolves p4a-r4: fr-triage example leaves the file location and terms undefined (phase 4)

The example says where the file lives, sets severity, and defines tier, severity, cx, wave, merge train and intent anchor.

<!-- fr:journal kind=finding scope=plan id=p4a-r5-resolved created=2026-11-11T15:48:45+00:00 phase=4 state=fixed resolves=p4a-r5 -->
### p4a-r5-resolved · finding [fixed] · resolves p4a-r5: Each requirement gets a row overstates (phase 4)

Says each requirement or closely related group, and that a row states what the product does.

<!-- fr:journal kind=finding scope=plan id=p4a-r6-resolved created=2026-11-11T15:48:45+00:00 phase=4 state=fixed resolves=p4a-r6 -->
### p4a-r6-resolved · finding [fixed] · resolves p4a-r6: fr plan rework precondition omitted (phase 4)

States the precondition.

<!-- fr:journal kind=finding scope=plan id=p4a-r7-resolved created=2026-11-11T15:48:45+00:00 phase=4 state=fixed resolves=p4a-r7 -->
### p4a-r7-resolved · finding [fixed] · resolves p4a-r7: docs-currency guide has no adoption path (phase 4)

New section 'Adopting it in your repo', five steps, including that only tracked files are read.

<!-- fr:journal kind=finding scope=plan id=p4a-r8-resolved created=2026-11-11T15:48:45+00:00 phase=4 state=fixed resolves=p4a-r8 -->
### p4a-r8-resolved · finding [fixed] · resolves p4a-r8: Pin the checkout's full history (phase 4)

Reworded.

<!-- fr:journal kind=finding scope=plan id=p4a-r9-resolved created=2026-11-11T15:48:45+00:00 phase=4 state=fixed resolves=p4a-r9 -->
### p4a-r9-resolved · finding [fixed] · resolves p4a-r9: Structure-only stated unconditionally (phase 4)

Reworded to the exact condition.

<!-- fr:journal kind=finding scope=plan id=p4a-r10-resolved created=2026-11-11T15:48:45+00:00 phase=4 state=fixed resolves=p4a-r10 -->
### p4a-r10-resolved · finding [fixed] · resolves p4a-r10: Config sample omits docs/reference/*.md (phase 4)

Sample lists the third glob.

<!-- fr:journal kind=finding scope=plan id=p4b-r1-resolved created=2026-11-11T15:48:45+00:00 phase=4 state=fixed resolves=p4b-r1 -->
### p4b-r1-resolved · finding [fixed] · resolves p4b-r1: fr-audit says report writes only under the cache (phase 4)

Names report -o as the exception.

<!-- fr:journal kind=finding scope=plan id=p4b-r2-resolved created=2026-11-11T15:48:45+00:00 phase=4 state=fixed resolves=p4b-r2 -->
### p4b-r2-resolved · finding [fixed] · resolves p4b-r2: fr-dispatch example hits the reachability refusal (phase 4)

The example states the precondition and points at the section.

<!-- fr:journal kind=decision scope=plan id=p5-readme-section-map created=2026-11-11T16:07:30+00:00 phase=5 -->
### p5-readme-section-map · decision · Where every old README section now lives (phase 5)

The old 552-line README, section by section.
Title, badges, intro: README (front door; four badges kept, the Acceptance one pinned by test_pages_workflow).
Quickstart 1 Install: README keeps the one command; channels table, OpenCode plugin and git-resolution paragraphs, Hermes pointer, CLI-only route and uninstall moved to docs/reference/install.md (new page, an eighth beyond the plan's seven).
Quickstart 2 first goal: README, shortened.
Skills (two tables): README generated skills table (all 15 skills, from front matter), plus per-skill pages already on the site.
How it works, Flow 1 diagram and the manual-phase and Test Plan prose: already in 01-fr-goal.md and index.md (diagram plus the numbered flow); not repeated.
Flow 2 sequence diagram: dropped as a diagram; the same steps are prose in fr-dispatch.md (worked example, tracking versus queueing, reachability); the multi-backend note is in components.md (forge services).
Isolation overview, exec-bridge discipline, lifecycle commands: already in fr-isolation.md. The where-worktrees-live table, statusline scripts, fr-init-on-missing-profile and down-refuses-open-PR were not there and were added to fr-isolation.md.
Reference fr CLI tables: docs/reference/cli.md (generated full tree) and README generated top-level table; the old two hand-kept tables were stale (missing most groups) and are dropped.
Plan model: docs/reference/plan-model.md. Workflow shapes and resolution order: workflow-shapes.md. Label lifecycle, reachability gate, per-repo profile and fr repos sync: dispatch-lifecycle.md. Acceptance matrix: acceptance-matrix.md. Hermes: hermes.md. Components table, Requirements, Services, self-hosted forges: components.md. For maintainers: README Contributing link to AGENTS.md.
Dropped as false or duplicated: the claim the plugins ship eleven skills (fifteen now), the `fr run` command list in the README (reshape/adopt/check kept in workflow-shapes.md, the rest generated), the 2026-07-09 multi-backend spec pointer.

<!-- fr:journal kind=decision scope=plan id=p5-skills-table-column created=2026-11-11T16:07:30+00:00 phase=5 -->
### p5-skills-table-column · decision · The skills table column is "What it is for", cut at a clause (phase 5)

Several skill descriptions open with "Use when ..." (they are trigger language), so a column headed "What it does" read wrong. The generated column is "What it is for". A first sentence over 150 characters has its parentheticals dropped, then is cut at the last clause boundary with an ellipsis. The fix for an unhelpful row is to improve the skill's description, not to edit the table.

<!-- fr:journal kind=discovery scope=plan id=p5-cli-help-quality created=2026-11-11T16:07:30+00:00 phase=5 -->
### p5-cli-help-quality · discovery · Some fr help lines are thin ("v2 plan editing commands.") (phase 5)

The generated CLI table prints each group's own help line, so thin ones (`plan`, `spec`, `migrate`) now show on the front page. Left as is: the table is a mirror of the code, and rewording help text is a CLI behaviour change outside this phase.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t1 created=2026-11-11T16:07:30+00:00 phase=5 -->
### no-refactor-p5-t1 · discovery · no-refactor-because P5.T1 (phase 5)

Generator and tripwire written once to the target shape; nothing to clean.

<!-- fr:journal kind=review scope=plan id=p5-review-1 created=2026-11-11T16:16:22+00:00 phase=5 -->
### p5-review-1 · review · Phase 5 review: README front door, reference pages, generated tables (phase 5)

Two separate reviewers: one walked the old README section by section to confirm nothing true was lost and checked the new README, sync-readme.py and its tripwire; the other fact-checked the eight reference pages against install.sh, the code and the CLI help and built the site. The section map held. Twenty-one findings: twenty in scope, all fixed; one out of scope.

<!-- fr:journal kind=decision scope=plan id=p5-skill-summaries-file created=2026-11-11T16:16:22+00:00 phase=5 -->
### p5-skill-summaries-file · decision · The skills table takes its line from a summaries file (phase 5)

A skill's description tells an agent when to load it and reads badly as a table cell. scripts/readme-skill-summaries.yaml holds one line per skill; the sync fails when a skill has none or a line names no skill, and each name links to the explainer that covers it. Spec R21 says so.

<!-- fr:journal kind=finding scope=plan id=p5a-r1 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5a-r1 · finding [open] (reviewer: in scope) · README says every merge publishes all of docs/ (phase 5)

pages.yml publishes only the page sources and only when a merge touches them.

<!-- fr:journal kind=finding scope=plan id=p5a-r2 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5a-r2 · finding [open] (reviewer: in scope) · sync-readme.py depends on the locale (phase 5)

read_text/write_text with no encoding crash under a C locale.

<!-- fr:journal kind=finding scope=plan id=p5a-r3 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5a-r3 · finding [open] (reviewer: in scope) · Skill cells read as trigger language (phase 5)

Rows began 'Use when asked...' or were cut mid-clause.

<!-- fr:journal kind=finding scope=plan id=p5a-r4 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5a-r4 · finding [open] (reviewer: in scope) · CLI rows expose internal wording (phase 5)

A spec id and 'v2 ...' in the Typer help strings.

<!-- fr:journal kind=finding scope=plan id=p5a-r5 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5a-r5 · finding [open] (reviewer: in scope) · sync-readme.py tracebacks on an unusable skill file (phase 5)

Missing description or front matter raised KeyError/IndexError; split('---') was brittle.

<!-- fr:journal kind=finding scope=plan id=p5a-r6 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5a-r6 · finding [open] (reviewer: in scope) · README promises a page per skill under Read more (phase 5)

fr-origins, fr-execute and fr-runner are covered inside other pages.

<!-- fr:journal kind=finding scope=plan id=p5a-r7 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5a-r7 · finding [open] (reviewer: in scope) · README prerequisites omit git, jq, rsync (phase 5)

The installer preflights them.

<!-- fr:journal kind=finding scope=plan id=p5a-r8 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5a-r8 · finding [open] (reviewer: in scope) · First-run and close-out sentences imprecise (phase 5)

The interview applies only to devcontainer mode without a profile; close-out is a separate session.

<!-- fr:journal kind=finding scope=plan id=p5a-r9 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5a-r9 · finding [open] (reviewer: in scope) · Small facts dropped with the old README (phase 5)

fr migrate's preview default and flags, fr validate artifacts --kind, two issue pointers.

<!-- fr:journal kind=finding scope=plan id=p5a-r10 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=out -->
### p5a-r10 · finding [open] (reviewer: out of scope) · Skill descriptions are trigger-optimised (phase 5)

A design tension in the skills themselves, not caused by this change.

<!-- fr:journal kind=finding scope=plan id=p5b-r1 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5b-r1 · finding [open] (reviewer: in scope) · fr-isolation.md contradicts itself on profiles (phase 5)

'No devcontainer profile is a stop' beside two modes that need none.

<!-- fr:journal kind=finding scope=plan id=p5b-r2 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5b-r2 · finding [open] (reviewer: in scope) · Weekly issue misnamed (phase 5)

The workflow runs fr debt issue and files 'Technical debt'.

<!-- fr:journal kind=finding scope=plan id=p5b-r3 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5b-r3 · finding [open] (reviewer: in scope) · cli.md says file-changing commands preview by default (phase 5)

plan create/edit, acceptance add/set-status and isolation up act at once.

<!-- fr:journal kind=finding scope=plan id=p5b-r4 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5b-r4 · finding [open] (reviewer: in scope) · unit attributed to each step (phase 5)

It is one field of the manifest.

<!-- fr:journal kind=finding scope=plan id=p5b-r5 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5b-r5 · finding [open] (reviewer: in scope) · install.md says fr refuses a 1.x OpenCode session (phase 5)

It reports the session as unreadable and says to upgrade.

<!-- fr:journal kind=finding scope=plan id=p5b-r6 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5b-r6 · finding [open] (reviewer: in scope) · install.md claims MCP config is installed (phase 5)

Only with the optional VibeKanban MCP binary present.

<!-- fr:journal kind=finding scope=plan id=p5b-r7 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5b-r7 · finding [open] (reviewer: in scope) · Generated CLI tree carries internal ids and cut lines (phase 5)

19 issue/spec references and 10 truncated help lines.

<!-- fr:journal kind=finding scope=plan id=p5b-r8 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5b-r8 · finding [open] (reviewer: in scope) · Requirements omit git, jq, rsync and the devcontainer CLI (phase 5)

components.md.

<!-- fr:journal kind=finding scope=plan id=p5b-r9 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5b-r9 · finding [open] (reviewer: in scope) · No uninstall route without a checkout (phase 5)

install.md.

<!-- fr:journal kind=finding scope=plan id=p5b-r10 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5b-r10 · finding [open] (reviewer: in scope) · Undefined terms (phase 5)

fr-cncd, herdr, tick, runner.

<!-- fr:journal kind=finding scope=plan id=p5b-r11 created=2026-11-11T16:16:22+00:00 phase=5 state=open review_scope=in -->
### p5b-r11 · finding [open] (reviewer: in scope) · covers globs miss the code the reference pages describe (phase 5)

hermes.py, labels.py, item_state.py, apply_cmd.py, plan/**, the OpenCode plugin's package.json, the command modules.

<!-- fr:journal kind=finding scope=plan id=p5a-r1-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5a-r1 -->
### p5a-r1-resolved · finding [fixed] · resolves p5a-r1: README says every merge publishes all of docs/ (phase 5)

Says the site is rebuilt from the three source locations when a merge changes them.

<!-- fr:journal kind=finding scope=plan id=p5a-r2-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5a-r2 -->
### p5a-r2-resolved · finding [fixed] · resolves p5a-r2: sync-readme.py depends on the locale (phase 5)

UTF-8 everywhere; test_the_script_does_not_depend_on_the_locale runs --check under LC_ALL=C.

<!-- fr:journal kind=finding scope=plan id=p5a-r3-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5a-r3 -->
### p5a-r3-resolved · finding [fixed] · resolves p5a-r3: Skill cells read as trigger language (phase 5)

Decision p5-skill-summaries-file; tests cover a missing and an unknown entry.

<!-- fr:journal kind=finding scope=plan id=p5a-r4-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5a-r4 -->
### p5a-r4-resolved · finding [fixed] · resolves p5a-r4: CLI rows expose internal wording (phase 5)

Reworded the help of fr plan, spec, migrate, skills and ops.

<!-- fr:journal kind=finding scope=plan id=p5a-r5-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5a-r5 -->
### p5a-r5-resolved · finding [fixed] · resolves p5a-r5: sync-readme.py tracebacks on an unusable skill file (phase 5)

SourceError names the file; front matter read by one anchored regex; test_an_unusable_skill_file_is_named_not_a_traceback.

<!-- fr:journal kind=finding scope=plan id=p5a-r6-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5a-r6 -->
### p5a-r6-resolved · finding [fixed] · resolves p5a-r6: README promises a page per skill under Read more (phase 5)

Each skill name in the table links to the explainer that covers it; test_every_shipped_skill_row_links_to_a_page.

<!-- fr:journal kind=finding scope=plan id=p5a-r7-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5a-r7 -->
### p5a-r7-resolved · finding [fixed] · resolves p5a-r7: README prerequisites omit git, jq, rsync (phase 5)

Listed.

<!-- fr:journal kind=finding scope=plan id=p5a-r8-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5a-r8 -->
### p5a-r8-resolved · finding [fixed] · resolves p5a-r8: First-run and close-out sentences imprecise (phase 5)

Reworded both sentences.

<!-- fr:journal kind=finding scope=plan id=p5a-r9-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5a-r9 -->
### p5a-r9-resolved · finding [fixed] · resolves p5a-r9: Small facts dropped with the old README (phase 5)

cli.md states migrate's preview default, --yes, --adopt and validate artifacts --kind. The two issue pointers stay out: the behaviour is documented and a ticket number explains nothing to a reader.

<!-- fr:journal kind=finding scope=plan id=p5a-r10-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=open resolves=p5a-r10 out_of_scope=true -->
### p5a-r10-resolved · finding [out-of-scope] · resolves p5a-r10: Skill descriptions are trigger-optimised (phase 5)

Not caused by this change: descriptions are written for skill selection. The table no longer depends on them.

<!-- fr:journal kind=finding scope=plan id=p5b-r1-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5b-r1 -->
### p5b-r1-resolved · finding [fixed] · resolves p5b-r1: fr-isolation.md contradicts itself on profiles (phase 5)

Scoped to the default devcontainer mode.

<!-- fr:journal kind=finding scope=plan id=p5b-r2-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5b-r2 -->
### p5b-r2-resolved · finding [fixed] · resolves p5b-r2: Weekly issue misnamed (phase 5)

Names fr debt issue and the Technical debt issue.

<!-- fr:journal kind=finding scope=plan id=p5b-r3-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5b-r3 -->
### p5b-r3-resolved · finding [fixed] · resolves p5b-r3: cli.md says file-changing commands preview by default (phase 5)

Lists which commands preview and which act at once.

<!-- fr:journal kind=finding scope=plan id=p5b-r4-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5b-r4 -->
### p5b-r4-resolved · finding [fixed] · resolves p5b-r4: unit attributed to each step (phase 5)

Says the unit belongs to the shape.

<!-- fr:journal kind=finding scope=plan id=p5b-r5-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5b-r5 -->
### p5b-r5-resolved · finding [fixed] · resolves p5b-r5: install.md says fr refuses a 1.x OpenCode session (phase 5)

Reworded.

<!-- fr:journal kind=finding scope=plan id=p5b-r6-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5b-r6 -->
### p5b-r6-resolved · finding [fixed] · resolves p5b-r6: install.md claims MCP config is installed (phase 5)

Claim removed.

<!-- fr:journal kind=finding scope=plan id=p5b-r7-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5b-r7 -->
### p5b-r7-resolved · finding [fixed] · resolves p5b-r7: Generated CLI tree carries internal ids and cut lines (phase 5)

The generator drops parentheticals and trailing clauses that only point at an issue, spec or requirement, and the tree is no longer truncated; two tests pin it on a fixture and on the repo.

<!-- fr:journal kind=finding scope=plan id=p5b-r8-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5b-r8 -->
### p5b-r8-resolved · finding [fixed] · resolves p5b-r8: Requirements omit git, jq, rsync and the devcontainer CLI (phase 5)

Listed.

<!-- fr:journal kind=finding scope=plan id=p5b-r9-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5b-r9 -->
### p5b-r9-resolved · finding [fixed] · resolves p5b-r9: No uninstall route without a checkout (phase 5)

Gives the managed clone's path.

<!-- fr:journal kind=finding scope=plan id=p5b-r10-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5b-r10 -->
### p5b-r10-resolved · finding [fixed] · resolves p5b-r10: Undefined terms (phase 5)

Defined or linked.

<!-- fr:journal kind=finding scope=plan id=p5b-r11-resolved created=2026-11-11T16:16:22+00:00 phase=5 state=fixed resolves=p5b-r11 -->
### p5b-r11-resolved · finding [fixed] · resolves p5b-r11: covers globs miss the code the reference pages describe (phase 5)

covers widened on hermes, dispatch-lifecycle, plan-model, components and cli; fr docs check finds no dead glob.

<!-- fr:journal kind=finding scope=plan id=p5a-r10-resolved-2 created=2026-11-11T16:28:08+00:00 phase=5 state=fixed resolves=p5a-r10 -->
### p5a-r10-resolved-2 · finding [fixed] · resolves p5a-r10: Skill descriptions are trigger-optimised (phase 5)

The consequence the reviewer raised (descriptions make poor table cells) is removed in this change: the README table takes its line from scripts/readme-skill-summaries.yaml. The descriptions themselves are written for skill selection on purpose and nothing is owed on them.
