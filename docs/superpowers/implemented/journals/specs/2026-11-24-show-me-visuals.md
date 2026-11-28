<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-show-me-visuals

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-24T13:51:45+00:00 input=true -->
### operator-brief · discovery · Operator brief: issue #1641 plus the goal text

Goal as typed: "check whether we have an issue (planned or in-flight) about adding visualizations/diagrams etc in the PR and documentation of super-fr. If not, I'd like to explore how to use something like the show-me skill from humanlayer" — then "first file the issue, for tracking purposes, then start fr goal".

Issue as filed:

# Visual explanations in PRs and specs: a shared 'show-me' vocabulary (structure-diffs, trees, mermaid)

## Problem

Nothing in fr's pipeline helps a reader *see* a change. PR bodies (`fr/record/pr_body.py`) and specs are prose and tables only; the diff tab shows lines, never which boundaries moved. The docs site has hand-authored SVG figures (`scripts/site/figures/`), but specs, PRs and ad-hoc questions get no visuals at all. No existing issue covers this (the `visual` issues, e.g. #779 / #1366, are about UI screenshot *evidence*, not explanation).

## Prior art

HumanLayer's `show-me` skill (humanlayer/skills, MIT, `plugins/show-me/skills/show-me/SKILL.md`): prose only, no dependencies, user-invoked. A menu of views ranked cheapest first — pseudocode, call tree, component tree, annotated file tree, mermaid, **`diff` blocks over structure** (trees, call stacks, state flow), a whole target shape, and HTML only as a last resort. Key rule: "pick the smallest view that makes the key point clear". HumanLayer reuses the same text as a shared reference inside its PR-description and design-discussion skills.

## Proposed scope

One shared visual vocabulary (harness-neutral, text views + mermaid; no HTML/`open` route), used in:

1. **PR body** — an optional section (like `## Review lenses`, not required, never a refusal) with one or two structure-diffs or a mermaid diagram, written at `deliver`. GitHub renders mermaid natively.
2. **Specs** — a design-shape view in the spec (fr-brainstorming / fr-goal), giving the spec-reviewer and operator something faster than prose.
3. **`/fr-show-me`** — an on-demand, user-invoked skill.

Out of scope: the docs site figures (keep hand-authored SVG; mermaid-on-site would need build-time rendering to pass the figure rules).

## Constraints

- Tool/argument neutrality (`fr.harness.prose.scan_prose`) and the OpenCode/Hermes mirrors.
- Third-party privacy: "use real labels" must not pull outside hosts/repos into a public PR.
- Accuracy: a diagram is a claim about the code and must match it.

<!-- fr:journal kind=decision scope=spec id=q1-vocabulary-home created=2026-11-24T13:51:45+00:00 decided_by=operator -->
### q1-vocabulary-home · decision · The vocabulary is a model-invocable skill, fr-show-me

Operator chose a new skill whose SKILL.md is the vocabulary, reachable by fr-goal and fr-brainstorming and mirrored to every harness (over a user-only skill with copies, or a CLI verb).

<!-- fr:journal kind=decision scope=spec id=q2-pr-section created=2026-11-24T13:51:45+00:00 decided_by=operator -->
### q2-pr-section · decision · The PR shape section is fr-rendered and required

Operator chose a required `## Shape of the change`, rendered by fr from the run shape file; a `none — <reason>` shape is the escape (over optional, or agent prose above the marker).

<!-- fr:journal kind=decision scope=spec id=q3-spec-shape created=2026-11-24T13:51:45+00:00 decided_by=operator -->
### q3-spec-shape · decision · Specs carry a required `## Design shape`, with a none-reason escape

Operator chose a required spec section checked by fr, with `none — <reason>` allowed (over optional or absent).

<!-- fr:journal kind=decision scope=spec id=q4-verification created=2026-11-24T13:51:45+00:00 decided_by=operator -->
### q4-verification · decision · Verification: CI plus one post-merge live row gated tester

Unit tests pin renderer, gates and skill text; one live row (a real fr-goal run after merge) gated tester.

<!-- fr:journal kind=decision scope=spec id=q5-accuracy created=2026-11-24T13:51:45+00:00 decided_by=operator -->
### q5-accuracy · decision · Accuracy: fr-spec-reviewer checks the spec shape; lens reviewers see the run shape file

No dedicated lens; the shape file is committed before lens-review so every lens reviewer sees it in the diff.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-11-24T13:57:41+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Committing the shape file does not put it in the lens reviewers' diff (q5, R14)

Raised by the independent spec reviewer.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-11-24T13:57:41+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · fr run adopt --supersede leaves <old-id>.shape.md behind

Raised by the independent spec reviewer.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-11-24T13:57:41+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · R10/R11 leave minimal body, no spec and unreadable spec undecided

Raised by the independent spec reviewer.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-11-24T13:57:41+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · A required section's effect on in-flight runs with an open PR is unstated

Raised by the independent spec reviewer.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-11-24T13:57:41+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · R8 and the Test Plan name spec-review but not spec-plan-review

Raised by the independent spec reviewer.

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-11-24T13:57:41+00:00 state=open review_scope=in -->
### s6 · finding [open] (reviewer: in scope) · §B names the wrong locator for the durable PR body

Raised by the independent spec reviewer.

<!-- fr:journal kind=finding scope=spec id=s7 created=2026-11-24T13:57:41+00:00 state=open review_scope=in -->
### s7 · finding [open] (reviewer: in scope) · The spec's own Design shape omits the agents kind bump, generated mirrors and the explainer

Raised by the independent spec reviewer.

<!-- fr:journal kind=finding scope=spec id=s8 created=2026-11-24T13:57:41+00:00 state=open review_scope=in -->
### s8 · finding [open] (reviewer: in scope) · R14's skill prose has no pre-merge test

Raised by the independent spec reviewer.

<!-- fr:journal kind=review scope=spec id=spec-review-r1 created=2026-11-24T13:57:41+00:00 -->
### spec-review-r1 · review · Independent spec review: 8 findings, all in scope, all fixed

fr-spec-reviewer checked the spec against decisions q1-q5, the codebase (file:line verified for every named helper) and itself; 8 in-scope findings s1-s8.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-24T13:57:41+00:00 lens=security step=spec-review -->
### lens-security-1 · lens · R12 adds an agent-written path to the ops trust exclusion list

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-24T13:57:41+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · New refusals at three resolve points plus archive/adopt moves; in-flight and light-path cases are easy to miss

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-11-24T13:57:41+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Committing the shape file does not put it in the lens reviewers' diff (q5, R14)

Added R16 and §D2: the lens_review brief carries `shape: <path>` and the return rule tells reviewers to check it without listing it under examined; R14, the mermaid and the Test Plan corrected.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-11-24T13:57:41+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: fr run adopt --supersede leaves <old-id>.shape.md behind

Added R17 and §D3: supersede moves the shape file beside _usage_move, refusing before any write when the destination exists; tested under shape-file-archived.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-11-24T13:57:41+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: R10/R11 leave minimal body, no spec and unreadable spec undecided

R10 now names four bodies (no spec, predates, content, none written) and says the section lives in the durable render under minimal; R11 refuses an unreadable spec and never a run with no spec.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-11-24T13:57:41+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: A required section's effect on in-flight runs with an open PR is unstated

Added R18 and §D text: one deliver refusal whose printed edit command is the recovery; a test drives an in-flight run with no spec section.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-11-24T13:57:41+00:00 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: R8 and the Test Plan name spec-review but not spec-plan-review

R8 names every spec-reviewing step, including spec-plan-review on fr-goal-light; the Test Plan tests the light shape.

<!-- fr:journal kind=finding scope=spec id=s6-resolved created=2026-11-24T13:57:41+00:00 state=fixed resolves=s6 -->
### s6-resolved · finding [fixed] · resolves s6: §B names the wrong locator for the durable PR body

§B now defines shape_path as run_path(...).with_name(f'{run_id}.shape.md'), the locator durable_pr_body_path uses.

<!-- fr:journal kind=finding scope=spec id=s7-resolved created=2026-11-24T13:57:41+00:00 state=fixed resolves=s7 -->
### s7-resolved · finding [fixed] · resolves s7: The spec's own Design shape omits the agents kind bump, generated mirrors and the explainer

The shape tree now shows registry.py, agents/__init__.py, lenses/review.py, run/adopt.py, one line of generated mirrors and the explainer; the mermaid shows the lens brief carrying the shape.

<!-- fr:journal kind=finding scope=spec id=s8-resolved created=2026-11-24T13:57:41+00:00 state=fixed resolves=s8 -->
### s8-resolved · finding [fixed] · resolves s8: R14's skill prose has no pre-merge test

The Test Plan adds a text test pinning the fr-goal and fr-brainstorming instructions under row show-me-skill.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-24T13:57:42+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  pr-shape-section: none
  shape-file-archived: none
  show-me-live-run: tester
  show-me-skill: none
  spec-design-shape-gate: none
  spec-reviewer-checks-shape: none
row_kinds:
  pr-shape-section: none
  shape-file-archived: none
  show-me-live-run: live
  show-me-skill: none
  spec-design-shape-gate: none
  spec-reviewer-checks-shape: none
run_gate: developer
run_kind: none
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-24-show-me-visuals-p2 created=2026-11-24T13:59:31+00:00 -->
### phase-split-2026-11-24-show-me-visuals-p2 · decision · ask: the fr-show-me skill, pipeline prose, spec reviewer and docs are a separately reviewable ask (R1-R5, R13-R15) from the engine

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-1 created=2026-11-26T13:29:42+00:00 -->
### test-plan-step-1 · discovery · Test Plan step 1: ran

Step: pre-merge — CI: `tests/unit/test_shape.py` pins the shape-block grammar and the section reader (R6); the skill tests pin `fr-show-me`'s presence, mirrors, neutrality and credit (R1–R5), and a text test pins fr-goal's and fr-brainstorming's design-shape and shape-file instructions (R14) (row `show-me-skill`).

Evidence: ci-ok green on PR #1665 head 6cfff980 (merged as d4da4514); the unit tests named run in CI's sharded test job

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-2 created=2026-11-26T13:29:45+00:00 -->
### test-plan-step-2 · discovery · Test Plan step 2: ran

Step: pre-merge — CI: resolve tests refuse a spec without a valid `## Design shape` at `brainstorm`, at `spec-review` on fr-goal and at `spec-plan-review` on fr-goal-light (R7, R8) (row `spec-design-shape-gate`).

Evidence: ci-ok green on PR #1665 head 6cfff980 (merged as d4da4514); the unit tests named run in CI's sharded test job

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-3 created=2026-11-26T13:29:47+00:00 -->
### test-plan-step-3 · discovery · Test Plan step 3: ran

Step: pre-merge — CI: PR-body and deliver tests cover the section's four bodies, the minimal-body durable render, both refusals and an in-flight run whose spec has no section (R9–R11, R18); lens-review brief tests cover the `shape` key and the return-rule sentence (R16) (row `pr-shape-section`).

Evidence: ci-ok green on PR #1665 head 6cfff980 (merged as d4da4514); the unit tests named run in CI's sharded test job

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-4 created=2026-11-26T13:29:49+00:00 -->
### test-plan-step-4 · discovery · Test Plan step 4: ran

Step: pre-merge — CI: archive, trust and adopt-supersede tests (R12, R17) (row `shape-file-archived`); a text test pins the reviewer's instruction (R13) (row `spec-reviewer-checks-shape`).

Evidence: ci-ok green on PR #1665 head 6cfff980 (merged as d4da4514); the unit tests named run in CI's sharded test job

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-5 created=2026-11-26T13:29:52+00:00 -->
### test-plan-step-5 · discovery · Test Plan step 5: ran

Step: post-merge — operator-driven: run fr-goal on a real goal with the released build; its spec has a `## Design shape` that matches the code, and its PR shows a `## Shape of the change` that matches the diff (R13, R14) (row `show-me-live-run`).

Evidence: walked 2026-11-25: fr-goal run 2026-11-25-feat-wave-plan-file-overlap on released 9.0.0-rc.10 delivered PR #1694 with a matching ## Design shape and ## Shape of the change; row show-me-live-run amended to walked; PR #1665 carries gate:tester-passed
