<!-- fr:journal-schema=3 -->
# Journal: 2026-11-11-docs-currency

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-11T12:17:36+00:00 input=true -->
### operator-brief · discovery · The operator's brief, as typed

there is documentation for this project, in Readme and in https://derio-net.github.io/super-fr/. I want to substantially improve both the repo documentation and the published pages. I think one of the published pages is raw html, these pages should be generated and stay up to date with all PRs (I think this is already the case, via an installed skill or a fr verb - which? are there blind spots e.g. only via fr-goal but not fr-debugging, what about future flows?).

<!-- fr:journal kind=decision scope=spec id=d-generator created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-generator · decision · Pages are rendered at deploy from Markdown with pinned blog-craft

Operator chose 'Render at deploy' (asked before the gate opened, restated in the spec): committed .html deleted; the two hand-authored pages become Markdown and lose their bespoke layout. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-enforcement created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-enforcement · decision · Currency is enforced by a shipped fr verb for all repos

Operator chose 'Shipped fr verb for all repos' over a repo-local CI gate. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-scope created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-scope · decision · Pipeline, gate, README and every new page in one PR

Operator chose 'Everything in one PR'. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-verification created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-verification · decision · Verification strategy is candidate

Round 1 question 1: 'candidate'. The published site is a post-merge Test Plan row gated tester. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-waiver created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-waiver · decision · A PR waives a page with a reviewed stamp in its front matter

Round 1 question 2: 'Reviewed stamp in the page'. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-readme created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-readme · decision · The README becomes a short front door

Round 1 question 3: 'Short front door'; reference sections move to published pages. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-depth created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-depth · decision · New explainers are concise

Round 1 question 4: 150 to 300 lines each. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-model-mechanical created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-model-mechanical · decision · mechanical tier runs on haiku

Round 1 question 5. old: unbound, new: haiku, reason: unbound tier, decider: operator, rule: brief unbound_tiers. Applied with fr models set.

<!-- fr:journal kind=decision scope=spec id=d-model-standard created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-model-standard · decision · standard tier runs on sonnet

Round 1 question 6. old: unbound, new: sonnet, reason: unbound tier, decider: operator, rule: brief unbound_tiers. Applied with fr models set.

<!-- fr:journal kind=decision scope=spec id=d-model-hard created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-model-hard · decision · hard tier runs on opus

Round 1 question 7. old: unbound, new: opus, reason: unbound tier, decider: operator, rule: brief unbound_tiers. Applied with fr models set.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-11T12:26:10+00:00 -->
### spec-review-1 · review · independent spec review: 12 findings (all in scope)

Checked against the spec journal's decisions (d-generator, d-enforcement, d-scope, d-waiver,
d-readme, d-depth, d-verification, d-model-*): each is honoured and none contradicted. Checked
against the code (run_cmd.py drift and derived evidence, trigger.py READ_ONLY_COMMANDS, cli.py,
sync-opencode.py, sync-hermes.py, install.sh, pages.yml, ci.yml, the three tripwires, the 15
skills, the seven guides, fr-debugging's delivery, the matrix rows) and the pinned renderer,
and against itself. Findings raised: sr-f1 to sr-f12.

<!-- fr:journal kind=finding scope=spec id=sr-f1 created=2026-11-11T12:26:10+00:00 state=open review_scope=in -->
### sr-f1 · finding [open] (reviewer: in scope) · `docs/*.md` with `*` spanning `/` makes every Markdown file under docs/ a page; reference pages missing from the config

Under fnmatch semantics (proportionality.py:25) `docs/*.md` matches docs/superpowers/**, so R4 fails on day one and the site would publish specs. Config lists no docs/reference/*.md. Fix: segment-aware globs, add the reference glob, same matcher in build-site.py with an equality test.

<!-- fr:journal kind=finding scope=spec id=sr-f2 created=2026-11-11T12:26:10+00:00 state=open review_scope=in -->
### sr-f2 · finding [open] (reviewer: in scope) · The `deliver` drift question is left to the plan, but the code already answers it

`_check_step_drift` (run_cmd.py:845-889) compares ids only, so an evidence key never drifts a run; journal-check drifted because it was a new step. Decide on listing the key; name DERIVED_EVIDENCE, _VERIFIABLE_EVIDENCE, _DERIVED_FROM, the derive call, both manifest copies and the pinned tuples.

<!-- fr:journal kind=finding scope=spec id=sr-f3 created=2026-11-11T12:26:10+00:00 state=open review_scope=in -->
### sr-f3 · finding [open] (reviewer: in scope) · Base resolution via `git remote set-head origin --auto` breaks R8 and needs the network

set-head writes refs/remotes/origin/HEAD and asks the remote. Use fr.git.remote_default_ref (git.py:179-206), exit 2 on None; deliver reuses _proportionality_base.

<!-- fr:journal kind=finding scope=spec id=sr-f4 created=2026-11-11T12:26:10+00:00 state=open review_scope=in -->
### sr-f4 · finding [open] (reviewer: in scope) · The `docs-check` CI job leaves out fetch depth, base and events

ci.yml runs on push, pull_request and merge_group; change-fragment (ci.yml:297-306) shows fetch-depth 0 and origin/base_ref are needed. Spec each event and how the job gets fr.

<!-- fr:journal kind=finding scope=spec id=sr-f5 created=2026-11-11T12:26:10+00:00 state=open review_scope=in -->
### sr-f5 · finding [open] (reviewer: in scope) · `docs/reference/cli.md` is both wholly generated and a page with a hand-maintained stamp

A stamp edit would make sync --check report the file stale. Generate only a marked block; keep front matter hand-owned; define its covers.

<!-- fr:journal kind=finding scope=spec id=sr-f6 created=2026-11-11T12:26:10+00:00 state=open review_scope=in -->
### sr-f6 · finding [open] (reviewer: in scope) · The new rule does not reach Hermes unless `SHIPPED_RULE_NAMES` is edited

sync-hermes.py:45-50 mirrors only allowlisted names; install.sh:169-174 CLAUDE_RULES likewise. Name both edits; correct the Background line.

<!-- fr:journal kind=finding scope=spec id=sr-f7 created=2026-11-11T12:26:10+00:00 state=open review_scope=in -->
### sr-f7 · finding [open] (reviewer: in scope) · The link rewrite does not say what happens to links to repo files that are not pages

docs/herdr-control-sessions.md:23 links ../packages/fr-herdr/README.md. Pick one rule: tracked non-page file becomes a github.com blob URL at the built SHA; untracked path fails.

<!-- fr:journal kind=finding scope=spec id=sr-f8 created=2026-11-11T12:26:10+00:00 state=open review_scope=in -->
### sr-f8 · finding [open] (reviewer: in scope) · Fallback-page detection misses the renderer's silent degradations

render_explainer.py:252-260 continues without fonts, exit 0. Pass --fonts-dir explicitly and fail when the output has no embedded @font-face data URI.

<!-- fr:journal kind=finding scope=spec id=sr-f9 created=2026-11-11T12:26:10+00:00 state=open review_scope=in -->
### sr-f9 · finding [open] (reviewer: in scope) · Tests the change breaks are not named

test_pages_workflow.py:53-54, :87-89, :92-95 and test_tripwire_fr_goal_question_rounds.py:42-44 read the cp step, index.html, the README badge and 01-fr-goal.html. Add the badge to R20, the acceptance link to R17, and list the tests with new targets.

<!-- fr:journal kind=finding scope=spec id=sr-f10 created=2026-11-11T12:26:10+00:00 state=open review_scope=in -->
### sr-f10 · finding [open] (reviewer: in scope) · R20's 200-line bound, R13's single pin and R16's URLs have no automated check

Add assertions to the readme sync tripwire, test_pages_workflow.py and a build-site unit test.

<!-- fr:journal kind=finding scope=spec id=sr-f11 created=2026-11-11T12:26:10+00:00 state=open review_scope=in -->
### sr-f11 · finding [open] (reviewer: in scope) · Two acceptance rows cite R6/R8 but their text and scenarios do not exercise them

matrix.yaml rows docs-check-flags-uncovered-change and docs-check-structure. Extend them or give R6/R8 their own row.

<!-- fr:journal kind=finding scope=spec id=sr-f12 created=2026-11-11T12:26:10+00:00 state=open review_scope=in -->
### sr-f12 · finding [open] (reviewer: in scope) · The `pages.yml` trigger `docs/**` is broader than R23

Nearly every fr-goal PR touches docs/superpowers/**. Use the page globs plus the config, build script, pin and acceptance inputs.

<!-- fr:journal kind=finding scope=spec id=sr-f1-resolved created=2026-11-11T12:26:10+00:00 state=fixed resolves=sr-f1 -->
### sr-f1-resolved · finding [fixed] · resolves sr-f1: `docs/*.md` with `*` spanning `/` makes every Markdown file under docs/ a page; reference pages missing from the config

§3.A: segment-aware globs via fr.docs.globs.match, docs/reference/*.md added, build-site.py copy with a page-set equality test.

<!-- fr:journal kind=finding scope=spec id=sr-f2-resolved created=2026-11-11T12:26:10+00:00 state=fixed resolves=sr-f2 -->
### sr-f2-resolved · finding [fixed] · resolves sr-f2: The `deliver` drift question is left to the plan, but the code already answers it

§3.B decides: `docs` listed in deliver.evidence in both shapes and both copies; the four code edits and the pinned tuples are named.

<!-- fr:journal kind=finding scope=spec id=sr-f3-resolved created=2026-11-11T12:26:10+00:00 state=fixed resolves=sr-f3 -->
### sr-f3-resolved · finding [fixed] · resolves sr-f3: Base resolution via `git remote set-head origin --auto` breaks R8 and needs the network

§3.A: base from fr.git.remote_default_ref, no writing git command; deliver reuses _proportionality_base.

<!-- fr:journal kind=finding scope=spec id=sr-f4-resolved created=2026-11-11T12:26:10+00:00 state=fixed resolves=sr-f4 -->
### sr-f4-resolved · finding [fixed] · resolves sr-f4: The `docs-check` CI job leaves out fetch depth, base and events

§3.B: fetch-depth 0, --base origin/base_ref on pull_request, no base on push and merge_group, uv run fr.

<!-- fr:journal kind=finding scope=spec id=sr-f5-resolved created=2026-11-11T12:26:10+00:00 state=fixed resolves=sr-f5 -->
### sr-f5-resolved · finding [fixed] · resolves sr-f5: `docs/reference/cli.md` is both wholly generated and a page with a hand-maintained stamp

§3.D: cli.md gets a generated block only; front matter hand-owned; covers packages/fr/src/fr/cli.py.

<!-- fr:journal kind=finding scope=spec id=sr-f6-resolved created=2026-11-11T12:26:10+00:00 state=fixed resolves=sr-f6 -->
### sr-f6-resolved · finding [fixed] · resolves sr-f6: The new rule does not reach Hermes unless `SHIPPED_RULE_NAMES` is edited

§2 corrected; §3.B names CLAUDE_RULES and SHIPPED_RULE_NAMES.

<!-- fr:journal kind=finding scope=spec id=sr-f7-resolved created=2026-11-11T12:26:10+00:00 state=fixed resolves=sr-f7 -->
### sr-f7-resolved · finding [fixed] · resolves sr-f7: The link rewrite does not say what happens to links to repo files that are not pages

§3.C step 3: one rule for page links, tracked non-page links (blob URL at the built SHA), untracked links (fail) and site routes (left alone).

<!-- fr:journal kind=finding scope=spec id=sr-f8-resolved created=2026-11-11T12:26:10+00:00 state=fixed resolves=sr-f8 -->
### sr-f8-resolved · finding [fixed] · resolves sr-f8: Fallback-page detection misses the renderer's silent degradations

§3.C step 5: explicit --fonts-dir, and failure when a page has no embedded @font-face data URI.

<!-- fr:journal kind=finding scope=spec id=sr-f9-resolved created=2026-11-11T12:26:10+00:00 state=fixed resolves=sr-f9 -->
### sr-f9-resolved · finding [fixed] · resolves sr-f9: Tests the change breaks are not named

R17 keeps the acceptance link, R20 keeps the badges; §3.E lists each test with its new target.

<!-- fr:journal kind=finding scope=spec id=sr-f10-resolved created=2026-11-11T12:26:10+00:00 state=fixed resolves=sr-f10 -->
### sr-f10-resolved · finding [fixed] · resolves sr-f10: R20's 200-line bound, R13's single pin and R16's URLs have no automated check

R13 and R20 now state their tests; §3.E adds the SHA assertion, the 200-line check and test_build_site.py's route assertion.

<!-- fr:journal kind=finding scope=spec id=sr-f11-resolved created=2026-11-11T12:26:10+00:00 state=fixed resolves=sr-f11 -->
### sr-f11-resolved · finding [fixed] · resolves sr-f11: Two acceptance rows cite R6/R8 but their text and scenarios do not exercise them

New row docs-check-default-base-readonly cites R6 and R8 with its own scenario; `## Verification` lists it.

<!-- fr:journal kind=finding scope=spec id=sr-f12-resolved created=2026-11-11T12:26:10+00:00 state=fixed resolves=sr-f12 -->
### sr-f12-resolved · finding [fixed] · resolves sr-f12: The `pages.yml` trigger `docs/**` is broader than R23

R23 and §3.C narrow the trigger to page globs, config, build script, pin and acceptance inputs.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-11T12:26:11+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  docs-check-default-base-readonly: none
  docs-check-flags-uncovered-change: none
  docs-check-structure: none
  docs-currency-every-flow: none
  docs-deliver-refuses-stale-docs: none
  docs-every-skill-has-page: none
  readme-generated-tables: none
  site-builds-from-sources: none
  site-published-from-sources: tester
row_kinds:
  docs-check-default-base-readonly: candidate
  docs-check-flags-uncovered-change: candidate
  docs-check-structure: candidate
  docs-currency-every-flow: none
  docs-deliver-refuses-stale-docs: none
  docs-every-skill-has-page: none
  readme-generated-tables: none
  site-builds-from-sources: none
  site-published-from-sources: live
run_gate: none
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-11-docs-currency-p2 created=2026-11-11T12:29:22+00:00 -->
### phase-split-2026-11-11-docs-currency-p2 · decision · ask: R9-R11 put the gate into deliver, the skills, a shipped rule and CI

Phase 2 serves its own ask (R9-R11), reviewable apart from the engine.

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-11-docs-currency-p2 created=2026-11-11T12:29:24+00:00 -->
### tier-2026-11-11-docs-currency-p2 · decision · hard: phase 2 changes deliver's evidence gate, which every fr-goal run in every repo passes through

A wrong derive refuses every deliver (run_cmd.py _VERIFIABLE_EVIDENCE).

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-11-docs-currency-p3 created=2026-11-11T12:29:25+00:00 -->
### phase-split-2026-11-11-docs-currency-p3 · decision · ask: R12-R17, R23, R24 make the site a build product

Own ask.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-11-docs-currency-p4 created=2026-11-11T12:29:27+00:00 -->
### phase-split-2026-11-11-docs-currency-p4 · decision · ask: R18-R19 a page for every skill

Own ask; also about 2,600 lines of prose, too much to review with the pipeline.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-11-docs-currency-p5 created=2026-11-11T12:29:29+00:00 -->
### phase-split-2026-11-11-docs-currency-p5 · decision · ask: R20-R22 the README front door and generated tables

Own ask.
