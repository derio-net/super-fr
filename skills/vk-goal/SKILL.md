---
name: vk-goal
description: >
  Run a feature goal end-to-end autonomously: brainstorm the context, ask one
  batched Q&A, then spec → review → vk-plan → review → TDD implementation →
  review → single PR, fixing every review finding, with no intermediate operator
  approval gates. ALWAYS use when the operator invokes /vk-goal or /goal with a
  task description. Also use when they say "build this autonomously", "ask your
  questions once then build it", "take this to a PR", hand over a feature with
  instructions to run unattended, mention "auto mode", or ask for the full
  spec-to-PR pipeline in one shot.
---

# vk-goal

One operator touchpoint from goal to reviewed PR: brainstorm context → ONE
batched Q&A → spec → review → vk-plan → review → TDD implementation → review →
single PR. Every review fixes all issues it finds. The superpowers approval
gates catch misunderstanding early; vk-goal front-loads that protection into
the single Q&A — the operator's autonomy instruction (outranking skill
defaults) replaces each pause with a review-and-fix pass. Autonomy isn't
silence on failure: when blocked, stop, state what's blocked and what you
tried, and ask — a wrong guess shipped in a PR costs more than a paused run.

**Announce at start:** "I'm using vk-goal to run this goal autonomously."

## What stays interactive

| Moment | Why |
|---|---|
| The batched Q&A (once, at brainstorm) | Design decisions are operator-owned |
| Multi-project repo location | Access question — only if the filesystem can't answer it |
| Manual phases | Secrets, UI ops, deploys are human-only — see placement policy |
| PR merge | The agent never self-merges |
| Post-merge Test Plan | Proves real deployment; needs the operator's environment |

### 1. Brainstorm with batched Q&A

Invoke `superpowers:brainstorming`, but explore the codebase first, collect
EVERY operator-owned decision, and ask all of them in ONE AskUserQuestion call
(max 4 questions, recommended option first). Include a post-merge Test Plan
question ONLY when the deliverable deploys (a service, bot, infra) — never for
pure code changes. Mid-run stragglers (rare): batch, never drip.

### 2. Spec — then review it

Write `docs/superpowers/specs/<YYYY-MM-DD-slug>-design.md`, then review it
against the Q&A answers AND codebase reality (do the files, helpers, and
services it names exist?). Fix every finding before moving on. If the operator
chose a Test Plan, the spec carries a `## Test Plan` of post-merge steps.

### 3. Multi-project check

For a cross-repo spec (`owner/repo:path` ref form), this session owns ONE
repo's plan and PR. For each other repo: locate its working copy yourself
(sibling dirs, usual project roots); ask for a path or clone permission only
if not found — batched into the Q&A when the shape is known up front. Dispatch
one agent per repo (`isolation: "worktree"`) with the spec ref and this
pipeline from step 4. One plan, one PR per repo.

### 4. Plan — vk-plan, then review it

Invoke `vk-plan`, skipping the section-by-section approval (the spec already
encodes the approved design). Keep v2 plan-as-folder format and TDD-shaped
steps. Review: `vk plan self-review <plan-dir>` must pass; read the phases back
against the spec — all covered, nothing assumed. Fix everything, then implement.

### 5. Manual phases — back-load by default

vk-plan's agentic-purity gate collects manual work into dedicated `[manual]`
phases. vk-goal adds placement policy (a mid-plan manual phase stalls the run):

- **Back-load by default:** ALL manual work in the LAST phase, no agentic
  phase depending on it. The PR ships with that phase deliberately
  unimplemented, marked for the operator, who implements it and pushes to the
  same PR (`vk plan edit --complete-phase N --note` records what was done).
- **Front-load only when agentic work genuinely depends on it.** Then finish
  plan + plan review, open a PR of spec + plan (the manual instructions ARE the
  deliverable), and pause. The operator merges that PR or pushes evidence to
  its branch — recommend which (merge when later work dispatches from it or
  another repo needs it reachable; push when the run continues there). Resume
  ONLY on the operator's go.
- **Multi-repo:** same per repo, but model cross-repo dependencies —
  `depends_on` reaches only within a plan, so ordering lives in the spec and
  PR sequencing (a manual secret in one repo may gate another's phases).

### 6. Implement — vk-execute local mode, TDD, no subagents

Feature branch / worktree (`superpowers:using-git-worktrees`). Run phases via
`vk-execute` in LOCAL mode (plan-dir + phase number) — NOT dispatched: spec and
plan aren't on main yet, so `vk apply --yes` would refuse (reachability gate).
Implement inline, not via subagents — the implementing context needs the Q&A
and spec history. TDD per step (`superpowers:test-driven-development`). Tick
steps and complete phases via `vk plan edit`. Never implement a manual phase.

### 7. Review at milestones — fix everything found

After each milestone (a completed phase, or the full implementation for small
plans), invoke `superpowers:requesting-code-review` over spec + plan + code.
Fix every finding immediately, with tests — that contract makes gate-waiving
safe. Exception: a factually wrong finding gets refuting reasoning recorded
(`superpowers:receiving-code-review`) — never a performative wrong fix, never a
silent drop. Keep the findings+fixes list.

### 8. Deliver — one PR per repo, all artifacts aboard

Verify first (`superpowers:verification-before-completion`): full test-suite
output, self-review pass, steps ticked. PR body: summary + spec/plan paths;
review findings and their fixes (plus any refuted finding); the back-loaded
manual phase marked "unimplemented — operator pushes to this PR"; the Test Plan
verbatim, labeled "post-merge — operator-driven". Stop; the operator merges.

### 9. Post-merge close-out

When the operator reports the merge: drive the Test Plan interactively if
present (agent runs checks, operator confirms what the agent can't reach). Then
confirm phases complete, check `vk spec status`, and archive the plan folder to
`docs/superpowers/archived-plans/` via a housekeeping PR (v2 plans need the
manual move; update the spec table).
