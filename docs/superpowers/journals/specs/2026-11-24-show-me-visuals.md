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
