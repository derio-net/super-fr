---
name: fr-goal
description: >
  Run a feature goal end-to-end autonomously: brainstorm, ask one batched
  Q&A, then spec → review → fr-plan → review → TDD implementation → review →
  single PR, fixing every review finding, with no intermediate approval
  gates. ALWAYS use when the operator invokes /fr-goal or /goal, says "build
  this autonomously", "ask your questions once then build it", "take this to
  a PR", hands over a feature to run unattended, mentions "auto mode", or
  asks for the full spec-to-PR pipeline in one shot.
---

# fr-goal

One operator touchpoint from goal to reviewed PR: brainstorm context → ONE
batched Q&A → spec → review → fr-plan → review → TDD implementation → review
→ single PR. Every review fixes all it finds; the operator's autonomy
instruction (outranking skill defaults) replaces each superpowers approval
pause with a review-and-fix pass — that protection front-loads into the Q&A.
When blocked: stop, state what's blocked and what you tried, and ask — a
wrong guess shipped in a PR costs more than a paused run.

**Announce at start:** "I'm using fr-goal to run this goal autonomously."

## What stays interactive

| Moment | Why |
|---|---|
| The batched Q&A (once, at brainstorm) | Design decisions are operator-owned |
| Multi-project repo location | Access question — only if the filesystem can't answer it |
| Manual phases | Secrets, UI ops, deploys are human-only — see placement policy |
| PR merge | The agent never self-merges |
| Post-merge Test Plan | Proves real deployment; needs the operator's environment |

### 1. Brainstorm with batched Q&A — in isolation

Invoke `fr-brainstorming` (runs `fr isolation up` first; no devcontainer
profile → pause for the fr-init interview). Isolation precedes EVERYTHING —
read-only exploration, measurements, and cluster ops included; an operator
"start with X" changes the first work item, never the first action; from the
start ALL commands run via `fr isolation exec`. Explore the workspace,
collect EVERY operator-owned decision, and ask all of them in ONE
AskUserQuestion call (max 4 questions, recommended option first). Include a
post-merge Test Plan question ONLY when the deliverable deploys (a service,
bot, infra) — never for pure code changes. Mid-run stragglers (rare): batch,
never drip.

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

### 4. Plan — fr-plan, then review it

Invoke `fr-plan`, skipping the section-by-section approval (the spec already
encodes the approved design). Keep v2 plan-as-folder format and TDD-shaped
steps. Review: `fr plan self-review <plan-dir>` must pass; read the phases back
against the spec — all covered, nothing assumed. Fix everything, then implement.

### 5. Manual phases — back-load by default

fr-plan's agentic-purity gate collects manual work into dedicated `[manual]`
phases. fr-goal adds placement policy (a mid-plan manual phase stalls the run):

- **Back-load by default:** ALL manual work in the LAST phase, no agentic
  phase depending on it. The PR ships with that phase deliberately
  unimplemented, marked for the operator, who implements it and pushes to the
  same PR (`fr plan edit --complete-phase N --note` records what was done).
- **Front-load only when agentic work genuinely depends on it.** Finish plan
  + plan review, open a PR of spec + plan (the manual instructions ARE the
  deliverable), pause. The operator merges it (when later work dispatches
  from it or another repo needs it reachable) or pushes evidence to its
  branch (when the run continues there). Resume ONLY on the operator's go.
- **Multi-repo:** same per repo, but model cross-repo dependencies —
  `depends_on` reaches only within a plan, so ordering lives in the spec and
  PR sequencing (a manual secret in one repo may gate another's phases).

### 6. Implement — fr-execute local mode, TDD, no subagents

The step-1 isolation workspace is the working copy — every command through
`fr isolation exec`. Run phases via `fr-execute` in LOCAL mode (plan-dir +
phase) — NOT dispatched: spec/plan aren't on main, `fr apply --yes` refuses.
Implement inline, not via subagents — the implementing context needs the Q&A
and spec history. TDD per step (`superpowers:test-driven-development`). Tick
steps and complete phases via `fr plan edit`. Never implement a manual phase.

**The implementing layer pushes the branch ONLY — it never opens the PR.**
This holds whether you implement inline or, for a multi-repo run (step 3),
delegate to a subagent: a builder's mandate ends at "branch pushed." PR
creation belongs to the orchestrator at step 8, *after* step 7's review. A
builder that opens the PR reorders deliver (8) ahead of review (7), and the
operator can merge the complete-looking PR before the fixes exist — they then
push onto a merged branch and orphan from `main` (the #320 merge-race, seen 3×).

**Visibility (after the branch is pushed, before review):** the orchestrator
MAY open a **draft** PR now. A draft is GitHub-unmergeable, so the review
window stays closed and the "Draft" badge is itself the "review pending — do
not merge yet" signal. Draft-from-start is the prescribed default; it never
becomes mergeable until step 8 marks it ready.

### 7. Review at milestones — fix everything found

After each milestone (a completed phase, or full implementation for small
plans), invoke `superpowers:requesting-code-review` over spec + plan + code.
Fix every finding immediately, with tests. A factually wrong finding gets
refuting reasoning recorded (`superpowers:receiving-code-review`) — never a
performative wrong fix, never a silent drop. Keep the findings+fixes list.

### 8. Deliver — one PR per repo, all artifacts aboard

Verify first (`superpowers:verification-before-completion`): full test-suite
output, self-review pass, steps ticked. The PR becomes mergeable ONLY now,
after step 7's fixes are committed: run `gh pr ready` on the draft (or, if no
draft was opened, open the PR fresh). PR body: summary + spec/plan paths;
review findings and their fixes (plus any refuted finding); the back-loaded
manual phase marked "unimplemented — operator pushes to this PR"; the Test Plan
verbatim, labeled "post-merge — operator-driven". Stop; the operator merges.

**Hand-off wording.** Never announce "PR is up" or "ready to merge" until the
fixes are in. While the PR is a draft, say "review pending — do not merge yet";
only after `gh pr ready` say "reviewed and ready to merge." Every push to the
branch is also covered by the pre-push guard (the `fr-merged-pr-push-guard.sh`
hook denies pushing to a MERGED/CLOSED PR's branch) — if it fires, STOP: the
commit would orphan; cherry-pick it onto `main` or open a fresh branch/PR.

### 9. Post-merge close-out

When the operator reports the merge: **first verify the fix actually reached
`main`** before declaring done. Be squash-aware — `git merge-base
--is-ancestor <branch-tip> origin/main` FALSE-NEGATIVES on squash merges (the
squash rewrites SHAs), so check content, not ancestry: `git fetch origin main`,
then confirm the PR is `MERGED` (`gh pr view --json state`) AND the branch's
changes are present in `origin/main` (`git diff --quiet origin/main -- <changed
paths>` shows nothing missing). If anything is missing — the merge-race orphan
— STOP, surface it, and recover (cherry-pick onto `main` / fresh PR) before
proceeding. Only then: drive the Test Plan interactively if present (agent runs
checks, operator confirms what the agent can't reach). Confirm phases complete
(`fr status` nudges), `fr archive <plan-dir>` (gate-checked git mv; spec
follows once all rows are implemented), commit via a housekeeping PR,
`fr isolation down`.
